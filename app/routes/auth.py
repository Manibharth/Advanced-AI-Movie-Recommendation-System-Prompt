from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from app import db, limiter
from app.models.user import User
from app.utils.validators import validate_email, validate_password
import secrets
import re
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
@limiter.limit('10 per hour')
def register():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    email    = (data.get('email')    or '').strip().lower()
    password =  data.get('password', '')
    full_name = (data.get('full_name') or '').strip()

    # ── Validation ────────────────────────────────────────────
    errors = {}
    if not username or len(username) < 3:
        errors['username'] = 'Username must be at least 3 characters'
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        errors['username'] = 'Username may only contain letters, digits, underscores'
    if not validate_email(email):
        errors['email'] = 'Invalid email address'
    if not validate_password(password):
        errors['password'] = 'Password must be 8+ chars with upper, lower, digit'
    if errors:
        return jsonify({'errors': errors}), 422

    # ── Uniqueness ───────────────────────────────────────────
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 409

    # ── Create user ──────────────────────────────────────────
    user = User(
        username=username, email=email,
        full_name=full_name or username,
        verify_token=secrets.token_urlsafe(32),
        preferences={'favorite_genres': [], 'mood': 'excited'},
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    access  = create_access_token(identity=str(user.id))
    refresh = create_refresh_token(identity=str(user.id))

    return jsonify({
        'message': 'Account created successfully',
        'user':    user.to_dict(include_private=True),
        'access_token':  access,
        'refresh_token': refresh,
    }), 201


@auth_bp.route('/login', methods=['POST'])
@limiter.limit('20 per hour')
def login():
    data     = request.get_json() or {}
    login_id = (data.get('email') or data.get('username') or '').strip().lower()
    password =  data.get('password', '')

    if not login_id or not password:
        return jsonify({'error': 'Email/username and password are required'}), 400

    # Accept either email or username
    user = (User.query.filter_by(email=login_id).first() or
            User.query.filter_by(username=login_id).first())

    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    user.last_login = datetime.utcnow()
    db.session.commit()

    access  = create_access_token(identity=str(user.id))
    refresh = create_refresh_token(identity=str(user.id))

    return jsonify({
        'message': 'Login successful',
        'user':    user.to_dict(include_private=True),
        'access_token':  access,
        'refresh_token': refresh,
    })


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    access  = create_access_token(identity=user_id)
    return jsonify({'access_token': access})


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user = User.query.get_or_404(int(get_jwt_identity()))
    return jsonify({'user': user.to_dict(include_private=True)})


@auth_bp.route('/me', methods=['PUT'])
@jwt_required()
def update_me():
    user = User.query.get_or_404(int(get_jwt_identity()))
    data = request.get_json() or {}

    allowed = {'full_name', 'bio', 'avatar_url', 'preferences'}
    for key in allowed:
        if key in data:
            setattr(user, key, data[key])

    db.session.commit()
    return jsonify({'user': user.to_dict(include_private=True)})


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    user = User.query.get_or_404(int(get_jwt_identity()))
    data = request.get_json() or {}
    old_pw = data.get('old_password', '')
    new_pw = data.get('new_password', '')

    if not user.check_password(old_pw):
        return jsonify({'error': 'Current password is incorrect'}), 401
    if not validate_password(new_pw):
        return jsonify({'error': 'New password does not meet requirements'}), 422

    user.set_password(new_pw)
    db.session.commit()
    return jsonify({'message': 'Password updated successfully'})


@auth_bp.route('/forgot-password', methods=['POST'])
@limiter.limit('5 per hour')
def forgot_password():
    email = (request.get_json() or {}).get('email', '').strip().lower()
    user  = User.query.filter_by(email=email).first()
    # Always return 200 to prevent email enumeration
    if user:
        user.reset_token   = secrets.token_urlsafe(32)
        user.reset_expires = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()
        # In production: send email with reset link
    return jsonify({'message': 'If that email exists, a reset link has been sent.'})


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data  = request.get_json() or {}
    token = data.get('token', '')
    new_pw = data.get('password', '')

    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_expires or user.reset_expires < datetime.utcnow():
        return jsonify({'error': 'Invalid or expired reset token'}), 400
    if not validate_password(new_pw):
        return jsonify({'error': 'Password does not meet requirements'}), 422

    user.set_password(new_pw)
    user.reset_token   = None
    user.reset_expires = None
    db.session.commit()
    return jsonify({'message': 'Password reset successfully'})


@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # JWT is stateless; client should discard the token
    return jsonify({'message': 'Logged out successfully'})

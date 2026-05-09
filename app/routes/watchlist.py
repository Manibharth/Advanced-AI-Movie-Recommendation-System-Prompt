from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.watchlist import Watchlist
from app.models.movie import Movie
from datetime import datetime

watchlist_bp = Blueprint('watchlist', __name__)

VALID_STATUS = {'want_to_watch', 'watching', 'watched'}


@watchlist_bp.route('/', methods=['GET'])
@jwt_required()
def get_watchlist():
    user_id = int(get_jwt_identity())
    status  = request.args.get('status')
    q = Watchlist.query.filter_by(user_id=user_id)
    if status and status in VALID_STATUS:
        q = q.filter_by(status=status)
    items = q.order_by(Watchlist.added_at.desc()).all()
    return jsonify({'watchlist': [i.to_dict() for i in items], 'total': len(items)})


@watchlist_bp.route('/', methods=['POST'])
@jwt_required()
def add_to_watchlist():
    user_id  = get_jwt_identity()
    data     = request.get_json() or {}
    movie_id = data.get('movie_id')
    status   = data.get('status', 'want_to_watch')

    if not movie_id:
        return jsonify({'error': 'movie_id is required'}), 400
    if status not in VALID_STATUS:
        return jsonify({'error': f'status must be one of {VALID_STATUS}'}), 422

    Movie.query.get_or_404(movie_id)

    item = Watchlist.query.filter_by(user_id=user_id, movie_id=movie_id).first()
    if item:
        item.status = status
        if status == 'watched' and not item.watched_at:
            item.watched_at = datetime.utcnow()
    else:
        item = Watchlist(user_id=user_id, movie_id=movie_id, status=status)
        db.session.add(item)

    db.session.commit()
    return jsonify({'message': 'Watchlist updated', 'item': item.to_dict()}), 201


@watchlist_bp.route('/<int:movie_id>', methods=['DELETE'])
@jwt_required()
def remove_from_watchlist(movie_id):
    user_id = int(get_jwt_identity())
    item = Watchlist.query.filter_by(user_id=user_id, movie_id=movie_id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({'message': 'Removed from watchlist'})


@watchlist_bp.route('/<int:movie_id>/status', methods=['PATCH'])
@jwt_required()
def update_status(movie_id):
    user_id = int(get_jwt_identity())
    item    = Watchlist.query.filter_by(user_id=user_id, movie_id=movie_id).first_or_404()
    data    = request.get_json() or {}
    status  = data.get('status')

    if status not in VALID_STATUS:
        return jsonify({'error': f'status must be one of {VALID_STATUS}'}), 422

    item.status = status
    if status == 'watched' and not item.watched_at:
        item.watched_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'item': item.to_dict()})


@watchlist_bp.route('/check/<int:movie_id>', methods=['GET'])
@jwt_required()
def check_watchlist(movie_id):
    user_id = int(get_jwt_identity())
    item    = Watchlist.query.filter_by(user_id=user_id, movie_id=movie_id).first()
    return jsonify({'in_watchlist': bool(item), 'status': item.status if item else None})

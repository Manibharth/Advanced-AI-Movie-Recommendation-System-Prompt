from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from functools import wraps
from app import db
from app.models.user import User
from app.models.movie import Movie, Genre
from app.models.rating import Rating, Review
from app.models.search import SearchHistory
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__)


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user = User.query.get(int(get_jwt_identity()))
        if not user or user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def dashboard():
    from sqlalchemy import select
    stats = {
        'total_users':   db.session.scalar(select(func.count()).select_from(User)),
        'total_movies':  db.session.scalar(select(func.count()).select_from(Movie)),
        'total_ratings': db.session.scalar(select(func.count()).select_from(Rating)),
        'total_reviews': db.session.scalar(select(func.count()).select_from(Review)),
        'total_searches':db.session.scalar(select(func.count()).select_from(SearchHistory)),
        'new_users_today': db.session.scalar(
            select(func.count()).select_from(User).where(
                func.date(User.created_at) == func.current_date()
            )
        ),
    }
    top_rated = Movie.query.order_by(Movie.vote_average.desc()).limit(5).all()
    top_searched = (db.session.query(
        SearchHistory.search_query, func.count(SearchHistory.id).label('cnt'))
        .group_by(SearchHistory.search_query)
        .order_by(func.count(SearchHistory.id).desc())
        .limit(5).all())

    return jsonify({
        'stats':        stats,
        'top_rated':    [m.to_dict() for m in top_rated],
        'top_searches': [{'query': r[0], 'count': r[1]} for r in top_searched],
    })


# ── User management ──────────────────────────────────────────
@admin_bp.route('/users', methods=['GET'])
@admin_required
def list_users():
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=25, error_out=False)
    return jsonify({
        'users': [u.to_dict(include_private=True) for u in users.items],
        'total': users.total,
        'pages': users.pages,
    })


@admin_bp.route('/users/<int:uid>', methods=['PATCH'])
@admin_required
def update_user(uid):
    user = User.query.get_or_404(uid)
    data = request.get_json() or {}
    if 'role' in data and data['role'] in ('user', 'admin'):
        user.role = data['role']
    if 'is_verified' in data:
        user.is_verified = bool(data['is_verified'])
    db.session.commit()
    return jsonify({'user': user.to_dict(include_private=True)})


@admin_bp.route('/users/<int:uid>', methods=['DELETE'])
@admin_required
def delete_user(uid):
    user = User.query.get_or_404(uid)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': f'User {uid} deleted'})


# ── Movie management ──────────────────────────────────────────
@admin_bp.route('/movies', methods=['POST'])
@admin_required
def create_movie():
    data = request.get_json() or {}
    required = ['title']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 422

    movie = Movie(
        title        = data['title'],
        overview     = data.get('overview'),
        poster_url   = data.get('poster_url'),
        backdrop_url = data.get('backdrop_url'),
        trailer_key  = data.get('trailer_key'),
        runtime      = data.get('runtime'),
        vote_average = data.get('vote_average', 0),
        vote_count   = data.get('vote_count', 0),
        popularity   = data.get('popularity', 0),
        director     = data.get('director'),
        cast_list    = data.get('cast_list', []),
        keywords     = data.get('keywords', []),
    )
    if data.get('release_date'):
        from datetime import datetime
        try:
            movie.release_date = datetime.strptime(data['release_date'], '%Y-%m-%d').date()
        except ValueError:
            pass

    genre_ids = data.get('genre_ids', [])
    if genre_ids:
        genres = Genre.query.filter(Genre.id.in_(genre_ids)).all()
        movie.genres = genres

    db.session.add(movie)
    db.session.commit()
    return jsonify({'movie': movie.to_dict(detailed=True)}), 201


@admin_bp.route('/movies/<int:mid>', methods=['PUT'])
@admin_required
def update_movie(mid):
    movie = Movie.query.get_or_404(mid)
    data  = request.get_json() or {}
    fields = ['title','overview','poster_url','backdrop_url','trailer_key',
              'runtime','vote_average','vote_count','popularity','director',
              'cast_list','keywords','tagline','language']
    for f in fields:
        if f in data:
            setattr(movie, f, data[f])
    if data.get('genre_ids'):
        genres = Genre.query.filter(Genre.id.in_(data['genre_ids'])).all()
        movie.genres = genres
    db.session.commit()
    return jsonify({'movie': movie.to_dict(detailed=True)})


@admin_bp.route('/movies/<int:mid>', methods=['DELETE'])
@admin_required
def delete_movie(mid):
    movie = Movie.query.get_or_404(mid)
    db.session.delete(movie)
    db.session.commit()
    return jsonify({'message': f'Movie {mid} deleted'})


# ── TMDB sync endpoints ───────────────────────────────────────────────────────

def _movie_service():
    """Return whichever movie service has its API key configured."""
    import os
    from app.services import omdb_service, tmdb_service
    if os.environ.get("TMDB_API_KEY", "").strip():
        return tmdb_service
    return omdb_service


@admin_bp.route('/sync-tmdb', methods=['POST'])
@admin_required
def sync_tmdb():
    """
    Trigger a background sync for every movie in the DB.
    Uses TMDB if TMDB_API_KEY is set, otherwise falls back to OMDb.
    Returns 202 immediately; sync runs in a daemon thread.
    """
    import threading
    from flask import current_app

    svc = _movie_service()
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            result = svc.sync_all_movies()
            app.logger.info("sync_all_movies finished: %s", result)

    thread = threading.Thread(target=_run, daemon=True, name="movie-sync")
    thread.start()

    return jsonify({
        'message': 'Movie sync started in background',
        'status':  'accepted',
    }), 202


@admin_bp.route('/fetch-popular', methods=['POST'])
@admin_required
def fetch_popular():
    """
    Fetch popular movies and add any not already in the DB.
    Accepts an optional JSON body ``{"pages": N}`` (default 3).
    Runs synchronously and returns the result summary when done.
    """
    svc = _movie_service()

    data  = request.get_json(silent=True) or {}
    pages = int(data.get('pages', 3))
    if pages < 1:
        pages = 1
    if pages > 20:
        pages = 20

    result = svc.fetch_popular_movies(pages=pages)

    if 'error' in result:
        return jsonify({'error': result['error']}), 503

    return jsonify({
        'message': 'Popular movies fetch complete',
        'result':  result,
    }), 200

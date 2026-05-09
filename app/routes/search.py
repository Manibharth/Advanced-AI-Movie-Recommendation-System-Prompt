from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app import db, cache
from app.models.movie import Movie
from app.models.search import SearchHistory
from sqlalchemy import or_, func

search_bp = Blueprint('search', __name__)


@search_bp.route('/', methods=['GET'])
def search():
    q       = (request.args.get('q') or '').strip()
    page    = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    if not q:
        return jsonify({'movies': [], 'total': 0, 'query': q})

    # Fulltext or LIKE search
    movies_q = Movie.query.filter(
        or_(
            Movie.title.ilike(f'%{q}%'),
            Movie.overview.ilike(f'%{q}%'),
            Movie.director.ilike(f'%{q}%'),
        )
    ).order_by(Movie.popularity.desc())

    total      = movies_q.count()
    pagination = movies_q.paginate(page=page, per_page=per_page, error_out=False)

    # Log search
    user_id = None
    try:
        verify_jwt_in_request(optional=True)
        user_id = int(get_jwt_identity())
    except Exception:
        pass

    entry = SearchHistory(user_id=user_id, search_query=q, results=total)
    db.session.add(entry)
    db.session.commit()

    return jsonify({
        'query':    q,
        'movies':   [m.to_dict() for m in pagination.items],
        'total':    total,
        'page':     page,
        'pages':    pagination.pages,
        'per_page': per_page,
    })


@search_bp.route('/suggestions', methods=['GET'])
@cache.cached(timeout=60, query_string=True)
def suggestions():
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({'suggestions': []})

    movies = (Movie.query.filter(Movie.title.ilike(f'%{q}%'))
              .order_by(Movie.popularity.desc()).limit(8).all())

    return jsonify({
        'suggestions': [
            {
                'id':           m.id,
                'title':        m.title,
                'year':         m.release_date.year if m.release_date else None,
                'poster_url':   m.poster_url,
                'vote_average': m.vote_average,
            }
            for m in movies
        ]
    })


@search_bp.route('/trending-searches', methods=['GET'])
@cache.cached(timeout=600)
def trending_searches():
    from sqlalchemy import func
    results = (db.session.query(SearchHistory.search_query, func.count(SearchHistory.id).label('cnt'))
               .group_by(SearchHistory.search_query)
               .order_by(func.count(SearchHistory.id).desc())
               .limit(10).all())
    return jsonify({'trending': [{'query': r[0], 'count': r[1]} for r in results]})

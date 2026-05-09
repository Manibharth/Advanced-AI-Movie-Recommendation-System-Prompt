from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from app import db, cache
from app.models.movie import Movie, Genre
from app.models.rating import Rating, Review
from app.models.watchlist import Watchlist
from sqlalchemy import or_, func
from datetime import datetime, timedelta

movies_bp = Blueprint('movies', __name__)

PER_PAGE = 20


def optional_auth():
    """Return current user id or None without raising."""
    try:
        verify_jwt_in_request(optional=True)
        return int(get_jwt_identity())
    except Exception:
        return None


@movies_bp.route('/', methods=['GET'])
@cache.cached(timeout=120, query_string=True)
def list_movies():
    page     = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', PER_PAGE, type=int)
    genre    = request.args.get('genre')
    sort     = request.args.get('sort', 'popularity')
    year     = request.args.get('year', type=int)
    min_rating = request.args.get('min_rating', 0, type=float)

    q = Movie.query

    if genre:
        q = q.join(Movie.genres).filter(Genre.slug == genre)
    if year:
        q = q.filter(func.year(Movie.release_date) == year)
    if min_rating:
        q = q.filter(Movie.vote_average >= min_rating)

    sort_map = {
        'popularity':   Movie.popularity.desc(),
        'rating':       Movie.vote_average.desc(),
        'newest':       Movie.release_date.desc(),
        'oldest':       Movie.release_date.asc(),
        'title':        Movie.title.asc(),
        'vote_count':   Movie.vote_count.desc(),
    }
    q = q.order_by(sort_map.get(sort, Movie.popularity.desc()))

    pagination = q.paginate(page=page, per_page=min(per_page, 100), error_out=False)

    return jsonify({
        'movies':   [m.to_dict() for m in pagination.items],
        'total':    pagination.total,
        'pages':    pagination.pages,
        'page':     page,
        'per_page': per_page,
    })


@movies_bp.route('/<int:movie_id>', methods=['GET'])
def get_movie(movie_id):
    movie   = Movie.query.get_or_404(movie_id)
    user_id = optional_auth()

    data = movie.to_dict(detailed=True)

    if user_id:
        rating    = Rating.query.filter_by(user_id=user_id, movie_id=movie_id).first()
        watchitem = Watchlist.query.filter_by(user_id=user_id, movie_id=movie_id).first()
        data['user_rating']   = rating.score if rating else None
        data['user_liked']    = rating.liked  if rating else None
        data['watchlist_status'] = watchitem.status if watchitem else None

    # Recent reviews
    reviews = (Review.query.filter_by(movie_id=movie_id)
               .order_by(Review.created_at.desc()).limit(10).all())
    data['reviews'] = [r.to_dict() for r in reviews]

    return jsonify({'movie': data})


@movies_bp.route('/trending', methods=['GET'])
@cache.cached(timeout=300)
def trending():
    cutoff = datetime.utcnow() - timedelta(days=30)
    movies = (Movie.query
              .filter(Movie.release_date >= cutoff.date())
              .order_by(Movie.popularity.desc())
              .limit(20).all())
    if len(movies) < 10:
        movies = Movie.query.order_by(Movie.popularity.desc()).limit(20).all()
    return jsonify({'movies': [m.to_dict() for m in movies]})


@movies_bp.route('/top-rated', methods=['GET'])
@cache.cached(timeout=300)
def top_rated():
    movies = (Movie.query
              .filter(Movie.vote_count >= 500)
              .order_by(Movie.vote_average.desc())
              .limit(20).all())
    return jsonify({'movies': [m.to_dict() for m in movies]})


@movies_bp.route('/genres', methods=['GET'])
@cache.cached(timeout=3600)
def get_genres():
    genres = Genre.query.order_by(Genre.name).all()
    return jsonify({'genres': [g.to_dict() for g in genres]})


@movies_bp.route('/genre/<slug>', methods=['GET'])
@cache.cached(timeout=300, query_string=True)
def by_genre(slug):
    genre = Genre.query.filter_by(slug=slug).first_or_404()
    page  = request.args.get('page', 1, type=int)
    movies = (Movie.query.join(Movie.genres)
              .filter(Genre.id == genre.id)
              .order_by(Movie.popularity.desc())
              .paginate(page=page, per_page=PER_PAGE, error_out=False))
    return jsonify({
        'genre':  genre.to_dict(),
        'movies': [m.to_dict() for m in movies.items],
        'total':  movies.total,
        'pages':  movies.pages,
        'page':   page,
    })


@movies_bp.route('/<int:movie_id>/rate', methods=['POST'])
@jwt_required()
def rate_movie(movie_id):
    user_id = int(get_jwt_identity())
    Movie.query.get_or_404(movie_id)
    data  = request.get_json() or {}
    score = data.get('score')
    liked = data.get('liked')

    if score is not None and not (1 <= int(score) <= 10):
        return jsonify({'error': 'Score must be between 1 and 10'}), 422

    rating = Rating.query.filter_by(user_id=user_id, movie_id=movie_id).first()
    if rating:
        if score is not None: rating.score = int(score)
        if liked is not None: rating.liked = liked
    else:
        rating = Rating(user_id=user_id, movie_id=movie_id,
                        score=int(score) if score else 5, liked=liked)
        db.session.add(rating)
    db.session.commit()
    return jsonify({'message': 'Rating saved', 'rating': rating.to_dict()})


@movies_bp.route('/<int:movie_id>/review', methods=['POST'])
@jwt_required()
def add_review(movie_id):
    user_id = int(get_jwt_identity())
    Movie.query.get_or_404(movie_id)
    data    = request.get_json() or {}
    content = (data.get('content') or '').strip()
    spoiler = data.get('spoiler', False)

    if len(content) < 10:
        return jsonify({'error': 'Review must be at least 10 characters'}), 422

    # Simple sentiment analysis
    sentiment = _simple_sentiment(content)

    review = Review(
        user_id=user_id, movie_id=movie_id,
        content=content, spoiler=spoiler, sentiment=sentiment
    )
    db.session.add(review)
    db.session.commit()
    return jsonify({'message': 'Review posted', 'review': review.to_dict()}), 201


@movies_bp.route('/<int:movie_id>/similar', methods=['GET'])
@cache.cached(timeout=600, query_string=True)
def similar_movies(movie_id):
    from app.services.ai_recommender import AIRecommender
    recommender = AIRecommender()
    movies = recommender.get_similar_movies(movie_id, limit=10)
    return jsonify({'movies': movies})


def _simple_sentiment(text: str) -> str:
    positive_words = {'great','excellent','amazing','wonderful','fantastic','brilliant',
                      'outstanding','perfect','love','loved','best','masterpiece','incredible'}
    negative_words = {'bad','terrible','awful','boring','waste','horrible','disappointing',
                      'worst','hate','hated','poor','dull','mediocre'}
    words = set(text.lower().split())
    pos   = len(words & positive_words)
    neg   = len(words & negative_words)
    if pos > neg:   return 'positive'
    if neg > pos:   return 'negative'
    return 'neutral'

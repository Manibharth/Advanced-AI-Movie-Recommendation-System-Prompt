from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.ai_recommender import AIRecommender

rec_bp = Blueprint('recommendations', __name__)
_rec   = AIRecommender()

VALID_MODES = {'netflix','because','trending','mindblowing','anime',
               'underrated','weekend','scifi','horror','mood'}


@rec_bp.route('/', methods=['GET'])
@jwt_required()
def get_recommendations():
    user_id = int(get_jwt_identity())
    mode    = request.args.get('mode', 'netflix')
    limit   = min(request.args.get('limit', 20, type=int), 50)

    if mode not in VALID_MODES:
        mode = 'netflix'

    results = _rec.get_recommendations(user_id=user_id, mode=mode, limit=limit)
    return jsonify({
        'mode':    mode,
        'label':   _rec.REC_MODES.get(mode, mode.title()),
        'movies':  results,
        'total':   len(results),
    })


@rec_bp.route('/all-sections', methods=['GET'])
@jwt_required()
def all_sections():
    user_id = int(get_jwt_identity())
    sections = []
    for mode, label in _rec.REC_MODES.items():
        try:
            movies = _rec.get_recommendations(user_id=user_id, mode=mode, limit=10)
            if movies:
                sections.append({'mode': mode, 'label': label, 'movies': movies})
        except Exception:
            pass
    return jsonify({'sections': sections})


@rec_bp.route('/similar/<int:movie_id>', methods=['GET'])
def get_similar(movie_id):
    limit   = min(request.args.get('limit', 10, type=int), 30)
    results = _rec.get_similar_movies(movie_id, limit=limit)
    return jsonify({'movies': results, 'total': len(results)})

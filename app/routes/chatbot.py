from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from app import db, limiter
from app.models.recommendation import AIFeedback
from app.services.ai_recommender import AIRecommender
import uuid

chatbot_bp = Blueprint('chatbot', __name__)
_rec       = AIRecommender()


@chatbot_bp.route('/message', methods=['POST'])
@limiter.limit('60 per hour')
def send_message():
    # Auth is optional
    user_id = None
    try:
        verify_jwt_in_request(optional=True)
        from flask_jwt_extended import get_jwt_identity
        user_id = int(get_jwt_identity())
    except Exception:
        pass

    data       = request.get_json() or {}
    message    = (data.get('message') or '').strip()
    session_id = data.get('session_id') or str(uuid.uuid4())

    if not message:
        return jsonify({'error': 'Message is required'}), 400
    if len(message) > 500:
        return jsonify({'error': 'Message too long (max 500 chars)'}), 422

    result = _rec.chatbot_suggest(message, user_id=user_id)

    # Log feedback for AI training
    feedback = AIFeedback(
        user_id=user_id,
        session_id=session_id,
        message=message,
        response=result['message'],
    )
    db.session.add(feedback)
    db.session.commit()

    return jsonify({
        'session_id':  session_id,
        'message':     result['message'],
        'suggestions': result['suggestions'],
        'feedback_id': feedback.id,
    })


@chatbot_bp.route('/feedback/<int:feedback_id>', methods=['POST'])
def rate_response(feedback_id):
    feedback = AIFeedback.query.get_or_404(feedback_id)
    data     = request.get_json() or {}
    helpful  = data.get('helpful')
    if helpful is None:
        return jsonify({'error': 'helpful (bool) is required'}), 400
    feedback.helpful = bool(helpful)
    db.session.commit()
    return jsonify({'message': 'Thank you for your feedback!'})


@chatbot_bp.route('/quick-replies', methods=['GET'])
def quick_replies():
    """Suggested prompts shown in the chatbot UI."""
    replies = [
        {'text': '🔥 What\'s trending?',       'query': 'What movies are trending?'},
        {'text': '😂 I want to laugh',          'query': 'Recommend me a funny movie'},
        {'text': '😱 Scare me!',                'query': 'I want a scary horror movie'},
        {'text': '🚀 Sci-Fi adventures',        'query': 'Best sci-fi movies'},
        {'text': '💎 Hidden gems',              'query': 'Show me underrated gems'},
        {'text': '🍿 Weekend binge picks',      'query': 'What should I binge this weekend?'},
        {'text': '❤️ Romantic movies',          'query': 'Recommend a romance movie'},
        {'text': '🧠 Mind-bending films',       'query': 'Show me mind-blowing movies'},
        {'text': '⛩️ Anime recommendations',    'query': 'Best anime movies'},
        {'text': '🏆 Top rated of all time',    'query': 'What are the best movies ever?'},
    ]
    return jsonify({'quick_replies': replies})

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
from flask_mail import Mail
import logging
from logging.handlers import RotatingFileHandler
import os

db      = SQLAlchemy()
jwt     = JWTManager()
limiter = Limiter(key_func=get_remote_address)
cache   = Cache()
mail    = Mail()


def create_app(config_name='default'):
    import os
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'frontend')
    app = Flask(__name__, static_folder=frontend_path, static_url_path='')

    # ── Config ────────────────────────────────────────────────
    from app.config import config
    app.config.from_object(config[config_name])

    # ── Extensions ────────────────────────────────────────────
    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)
    mail.init_app(app)
    CORS(app, resources={r'/api/*': {'origins': app.config['CORS_ORIGINS']}})

    # ── Blueprints ────────────────────────────────────────────
    from app.routes.auth            import auth_bp
    from app.routes.movies          import movies_bp
    from app.routes.recommendations import rec_bp
    from app.routes.watchlist       import watchlist_bp
    from app.routes.admin           import admin_bp
    from app.routes.chatbot         import chatbot_bp
    from app.routes.search          import search_bp

    app.register_blueprint(auth_bp,     url_prefix='/api/auth')
    app.register_blueprint(movies_bp,   url_prefix='/api/movies')
    app.register_blueprint(rec_bp,      url_prefix='/api/recommendations')
    app.register_blueprint(watchlist_bp,url_prefix='/api/watchlist')
    app.register_blueprint(admin_bp,    url_prefix='/api/admin')
    app.register_blueprint(chatbot_bp,  url_prefix='/api/chatbot')
    app.register_blueprint(search_bp,   url_prefix='/api/search')

    # ── SPA Fallback ──────────────────────────────────────────
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        from flask import send_from_directory
        if path and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        return send_from_directory(app.static_folder, 'index.html')

    # ── Logging ───────────────────────────────────────────────
    if not app.debug:
        os.makedirs('logs', exist_ok=True)
        handler = RotatingFileHandler('logs/app.log', maxBytes=10_000_000, backupCount=5)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s %(message)s'
        ))
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)

    # ── JWT Error Handlers ────────────────────────────────────
    @jwt.expired_token_loader
    def expired_token(_jwt_header, _jwt_data):
        return {'error': 'Token has expired'}, 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return {'error': f'Invalid token: {reason}'}, 401

    @jwt.unauthorized_loader
    def missing_token(reason):
        return {'error': 'Authorization required'}, 401

    # ── Generic Error Handlers ────────────────────────────────
    @app.errorhandler(404)
    def not_found(_e):
        return {'error': 'Resource not found'}, 404

    @app.errorhandler(500)
    def server_error(_e):
        app.logger.exception('Internal server error')
        return {'error': 'Internal server error'}, 500

    return app

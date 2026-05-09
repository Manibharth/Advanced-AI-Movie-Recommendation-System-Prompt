import os
from datetime import timedelta
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

class Config:
    # ── Core ──────────────────────────────────────────────────
    SECRET_KEY          = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')
    DEBUG               = False
    TESTING             = False

    # ── Database ──────────────────────────────────────────────
    DB_HOST             = os.getenv('DB_HOST', 'localhost')
    DB_PORT             = int(os.getenv('DB_PORT', 3306))
    DB_NAME             = os.getenv('DB_NAME', 'moviedb')
    DB_USER             = os.getenv('DB_USER', 'root')
    DB_PASSWORD         = os.getenv('DB_PASSWORD', '')
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{os.getenv('DB_USER','root')}:{quote_plus(os.getenv('DB_PASSWORD',''))}@"
        f"{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT',3306)}/{os.getenv('DB_NAME','moviedb')}"
        f"?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_RECYCLE = 300
    SQLALCHEMY_POOL_PRE_PING = True

    # ── JWT ───────────────────────────────────────────────────
    JWT_SECRET_KEY          = os.getenv('JWT_SECRET_KEY', 'jwt-dev-secret')
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # ── External APIs ─────────────────────────────────────────
    TMDB_API_KEY        = os.getenv('TMDB_API_KEY', '')
    TMDB_BASE_URL       = 'https://api.themoviedb.org/3'
    TMDB_IMAGE_BASE     = 'https://image.tmdb.org/t/p/w500'
    OMDB_API_KEY        = os.getenv('OMDB_API_KEY', '')

    # ── OAuth ─────────────────────────────────────────────────
    GOOGLE_CLIENT_ID    = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET= os.getenv('GOOGLE_CLIENT_SECRET', '')
    GITHUB_CLIENT_ID    = os.getenv('GITHUB_CLIENT_ID', '')
    GITHUB_CLIENT_SECRET= os.getenv('GITHUB_CLIENT_SECRET', '')

    # ── Mail ──────────────────────────────────────────────────
    MAIL_SERVER         = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT           = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS        = True
    MAIL_USERNAME       = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD       = os.getenv('MAIL_PASSWORD', '')

    # ── Rate Limiting ─────────────────────────────────────────
    RATELIMIT_DEFAULT   = '200 per day;50 per hour'
    RATELIMIT_STORAGE_URL = 'memory://'

    # ── Cache ─────────────────────────────────────────────────
    CACHE_TYPE          = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 300

    # ── CORS ──────────────────────────────────────────────────
    CORS_ORIGINS        = os.getenv('CORS_ORIGINS', '*')


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_POOL_SIZE    = 10
    SQLALCHEMY_MAX_OVERFLOW = 20


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}

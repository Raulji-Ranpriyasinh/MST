import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration loaded from environment variables."""

    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(32).hex())
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'mysql+pymysql://root:8888@localhost/exam'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    # Session cookie security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_SAMESITE = 'Lax'

    # JWT configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', os.urandom(32).hex())
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 7200))  # 2 hours

    # PDF server configuration
    PDF_SERVER_URL = os.environ.get('PDF_SERVER_URL', 'http://localhost:3000')
    PDF_TOKEN_SECRET = os.environ.get('PDF_TOKEN_SECRET', os.urandom(32).hex())
    PDF_TOKEN_TIMEOUT = int(os.environ.get('PDF_TOKEN_TIMEOUT', 60))  # seconds

    # Flask origin for CORS on Node server
    FLASK_ORIGIN = os.environ.get('FLASK_ORIGIN', 'http://localhost:5000')

    # Rate limiting
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '200 per day')
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

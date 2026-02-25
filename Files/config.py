import os
from dotenv import load_dotenv
from datetime import timedelta

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

    # ----- JWT configuration -----
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.environ.get('JWT_ACCESS_HOURS', 1))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.environ.get('JWT_REFRESH_DAYS', 30))
    )
    JWT_COOKIE_SECURE = os.environ.get(
        'JWT_COOKIE_SECURE', 'False'
    ).lower() == 'true'
    JWT_COOKIE_SAMESITE = 'Lax'
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_ACCESS_CSRF_HEADER_NAME = 'X-CSRF-TOKEN'
    JWT_REFRESH_CSRF_HEADER_NAME = 'X-CSRF-TOKEN'

    # PDF server configuration
    PDF_SERVER_URL = os.environ.get('PDF_SERVER_URL', 'http://localhost:3000')
    PDF_TOKEN_SECRET = os.environ.get('PDF_TOKEN_SECRET', os.urandom(32).hex())
    PDF_TOKEN_TIMEOUT = int(os.environ.get('PDF_TOKEN_TIMEOUT', 60))  # seconds

    # Flask origin for CORS on Node server
    FLASK_ORIGIN = os.environ.get('FLASK_ORIGIN', 'http://localhost:5000')

    # Rate limiting
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '200 per day')
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

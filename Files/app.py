"""Application factory for the MST aptitude/career assessment platform."""

import os

from flask import Flask

from config import Config
from extensions import db, jwt, limiter


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    # Register blueprints
    from routes.auth import auth_bp
    from routes.student import student_bp
    from routes.assessment import assessment_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(assessment_bp)
    app.register_blueprint(admin_bp)

    # Create database tables
    with app.app_context():
        # Import models so SQLAlchemy knows about them
        import models  # noqa: F401
        db.create_all()

    return app


# Allow running directly with `python app.py`
if __name__ == '__main__':
    app = create_app()
    app.run(debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')

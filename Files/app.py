"""Application factory for the MST aptitude/career assessment platform."""

import os

from flask import Flask, jsonify
from flask import request as flask_request

from config import Config
from extensions import db, jwt, limiter, socketio

# In-memory blocklist for revoked JWT tokens (jti values).
# For a multi-process / production deployment, replace with Redis or a DB table.
BLOCKLIST: set[str] = set()


def create_app(config_class=Config):
    """Create and configure the Flask application."""

    AUTHENTICATED_PREFIXES = (
        "/dashboard", "/programmes", "/career_assessment",
        "/aptitude_questionnaire", "/admin_dashboard", "/firm/dashboard"
    )
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    limiter.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")

    # ---- JWT callbacks ------------------------------------------------
    @jwt.token_in_blocklist_loader
    def check_if_token_revoked(_jwt_header, jwt_payload):
        """Return True if the token has been revoked (logged out)."""
        return jwt_payload["jti"] in BLOCKLIST

    @jwt.expired_token_loader
    def expired_token_callback(_jwt_header, _jwt_payload):
        return jsonify({"message": "Token has expired", "error": "token_expired"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({"message": "Invalid token", "error": "invalid_token"}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({"message": "Authentication required", "error": "authorization_required"}), 401

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
        from flask_socketio import join_room

        @socketio.on('join')
        def on_join(data):
            join_room(data['room'])

    @app.after_request
    def add_cache_control(response):
        if flask_request.path.startswith(AUTHENTICATED_PREFIXES):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    return app


if __name__ == '__main__':
    app = create_app()
    socketio.run(app, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')
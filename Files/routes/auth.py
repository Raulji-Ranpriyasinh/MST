"""Authentication routes: login, register, logout for students and admin."""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
)
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, limiter
from models.admin import Admin
from models.student import StudentDetails
from schemas.validation import validate_admin_login, validate_login, validate_registration

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def home():
    return render_template('index.html')


@auth_bp.route('/register', methods=['POST'])
@limiter.limit("10 per minute")
def register():
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    # Server-side validation
    is_valid, errors = validate_registration(data)
    if not is_valid:
        return jsonify({'success': False, 'message': '; '.join(errors)}), 400

    # Check if user already exists
    existing_user = StudentDetails.query.filter_by(email=data['email']).first()
    if existing_user:
        return jsonify({'success': False, 'message': 'Email already registered!'}), 400

    # Hash password
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')

    # Create new user
    new_user = StudentDetails(
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data['email'],
        mobile_number=data['mobile_number'],
        country=data['country'],
        curriculum=data['curriculum'],
        school_name=data['school_name'],
        grade=data['grade'],
        referral_source=data.get('referral_source', ''),
        password=hashed_password,
    )

    db.session.add(new_user)
    db.session.commit()

    # Generate JWT tokens with custom claims
    additional_claims = {
        "role": "student",
        "email": new_user.email,
        "first_name": new_user.first_name,
    }
    access_token = create_access_token(
        identity=str(new_user.id), additional_claims=additional_claims
    )
    refresh_token = create_refresh_token(
        identity=str(new_user.id), additional_claims=additional_claims
    )

    response = jsonify({
        'success': True,
        'message': 'Registered and logged in successfully!',
    })
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
    return response


@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    # Server-side validation
    is_valid, errors = validate_login(data)
    if not is_valid:
        return jsonify({'success': False, 'message': '; '.join(errors)}), 400

    user = StudentDetails.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        additional_claims = {
            "role": "student",
            "email": user.email,
            "first_name": user.first_name,
        }
        access_token = create_access_token(
            identity=str(user.id), additional_claims=additional_claims
        )
        refresh_token = create_refresh_token(
            identity=str(user.id), additional_claims=additional_claims
        )

        response = jsonify({
            'success': True,
            'message': 'Login successful!',
            'redirect': url_for('student.dashboard'),
        })
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, refresh_token)
        return response, 200
    else:
        return jsonify({'success': False, 'message': 'Invalid email or password!'}), 401


@auth_bp.route('/admin_login', methods=['POST'])
@limiter.limit("5 per minute")
def admin_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    admin = Admin.query.filter_by(username=username).first()
    if admin and check_password_hash(admin.password, password):
        additional_claims = {
            "role": "admin",
        }
        access_token = create_access_token(
            identity=str(admin.id), additional_claims=additional_claims
        )
        refresh_token = create_refresh_token(
            identity=str(admin.id), additional_claims=additional_claims
        )

        response = jsonify({
            'success': True,
            'message': 'Admin login successful!',
            'redirect': url_for('admin.admin_dashboard'),
        })
        set_access_cookies(response, access_token)
        set_refresh_cookies(response, refresh_token)
        return response, 200
    else:
        return jsonify({'success': False, 'message': 'Invalid username or password!'}), 401


@auth_bp.route('/admin', methods=['GET'])
def admin_login_page():
    return render_template('adminlogin.html')


@auth_bp.route('/logout', methods=['POST'])
@jwt_required(optional=True)
def logout():
    """Revoke the current access token and clear JWT cookies."""
    token = get_jwt()
    if token:
        from app import BLOCKLIST
        BLOCKLIST.add(token["jti"])
    response = jsonify({"message": "Logged out"})
    unset_jwt_cookies(response)
    return response


@auth_bp.route('/admin_logout', methods=['POST'])
@jwt_required(optional=True)
def admin_logout():
    """Revoke the current access token and clear JWT cookies."""
    token = get_jwt()
    if token:
        from app import BLOCKLIST
        BLOCKLIST.add(token["jti"])
    response = jsonify({"message": "Logged out"})
    unset_jwt_cookies(response)
    return response


@auth_bp.route('/api/v1/token/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Issue a new access token using a valid refresh token."""
    identity = get_jwt_identity()
    claims = get_jwt()
    additional_claims = {
        k: v for k, v in claims.items()
        if k in ("role", "email", "first_name")
    }
    new_access_token = create_access_token(
        identity=identity, additional_claims=additional_claims
    )
    response = jsonify({"refreshed": True})
    set_access_cookies(response, new_access_token)
    return response


@auth_bp.route("/api/v1/session/check")
@jwt_required(optional=True)
def session_check():
    identity = get_jwt_identity()
    if not identity:
        return jsonify({"valid": False}), 401
    return jsonify({"valid": True}), 200

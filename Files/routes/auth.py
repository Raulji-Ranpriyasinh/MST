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
from itsdangerous import BadSignature, SignatureExpired
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, limiter
from models.admin import Admin
from models.consultancy import ConsultancyFirm
from models.student import StudentDetails
from schemas.validation import validate_admin_login, validate_login, validate_registration

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def home():
    return render_template('index.html')


@auth_bp.route('/register/firm/<token>')
def register_with_firm_token(token):
    """Validate an invite token and render the registration page with firm context."""
    from routes.admin import _get_invite_serializer, _INVITE_MAX_AGE

    serializer = _get_invite_serializer()
    try:
        data = serializer.loads(token, salt='firm-invite', max_age=_INVITE_MAX_AGE)
    except SignatureExpired:
        return render_template('removed.html', message='This invite link has expired. Please request a new one from your firm.'), 410
    except BadSignature:
        return render_template('removed.html', message='Invalid invite link.'), 400

    firm_id = data.get('firm_id')
    firm = db.session.get(ConsultancyFirm, firm_id)
    if firm is None or not firm.is_active:
        return render_template('removed.html', message='The firm associated with this invite is no longer available.'), 400

    return render_template('index.html', firm_token=token, firm_name=firm.firm_name)


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

    # Resolve firm_id: invite token takes priority over body
    firm_token = data.get('firm_token')
    firm_id = None
    if firm_token:
        from routes.admin import _get_invite_serializer, _INVITE_MAX_AGE
        serializer = _get_invite_serializer()
        try:
            token_data = serializer.loads(firm_token, salt='firm-invite', max_age=_INVITE_MAX_AGE)
            firm_id = token_data.get('firm_id')
        except (SignatureExpired, BadSignature):
            return jsonify({'success': False, 'message': 'Invalid or expired invite link'}), 400
    else:
        firm_id = data.get('firm_id')

    if firm_id is not None:
        firm = db.session.get(ConsultancyFirm, firm_id)
        if firm is None:
            return jsonify({'success': False, 'message': 'Firm not found'}), 400
        if not firm.is_active:
            return jsonify({'success': False, 'message': 'Firm is not active'}), 400

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
        firm_id=firm_id,
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


@auth_bp.route('/api/v1/firms/active', methods=['GET'])
def list_active_firms():
    """Return a list of active consultancy firms for the registration dropdown.

    NOTE: This endpoint is intentionally kept for backward compatibility but
    the public registration page no longer calls it. Firms are now accessed
    via invite links generated by admins.
    """
    firms = ConsultancyFirm.query.filter_by(is_active=True).order_by(ConsultancyFirm.firm_name).all()
    firms_list = [
        {"id": f.id, "firm_name": f.firm_name}
        for f in firms
    ]
    return jsonify({"success": True, "firms": firms_list})

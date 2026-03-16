"""Authentication routes: login, register, logout for students and admin."""

import logging
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
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
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, limiter
from models.admin import Admin
from models.consultancy import ConsultancyFirm
from models.student import StudentDetails
from schemas.validation import validate_admin_login, validate_login, validate_registration

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


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
    """Issue a new access token using a valid refresh token.

    Preserves all custom claims (role, email, first_name, firm_id, username)
    so the new access token works for students, admins, and firm admins alike.
    """
    identity = get_jwt_identity()
    claims = get_jwt()
    # Preserve all custom claims added at login time
    preserved_keys = ("role", "email", "first_name", "firm_id", "username")
    additional_claims = {
        k: v for k, v in claims.items()
        if k in preserved_keys
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


# ---------------------------------------------------------------------------
# Intern 12 – Student Password Reset
# ---------------------------------------------------------------------------

def _get_student_reset_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _make_student_reset_token(email):
    s = _get_student_reset_serializer()
    return s.dumps(email, salt='student-password-reset')


def _verify_student_reset_token(token, max_age=3600):
    s = _get_student_reset_serializer()
    return s.loads(token, salt='student-password-reset', max_age=max_age)


@auth_bp.route('/auth/forgot-password', methods=['GET'])
def forgot_password_page():
    """Render the forgot-password form for students."""
    return render_template('forgot_password.html', user_type='student')


@auth_bp.route('/auth/forgot-password', methods=['POST'])
@limiter.limit("5 per minute")
def forgot_password():
    """Accept email, generate reset token and send email."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()

    # Always return 200 – do not reveal whether the email exists
    if email:
        user = StudentDetails.query.filter_by(email=email).first()
        if user:
            token = _make_student_reset_token(email)
            reset_url = request.url_root.rstrip('/') + f'/auth/reset-password/{token}'
            _send_student_reset_email(email, reset_url)

    return jsonify({"success": True, "message": "If that email is registered, a reset link has been sent."})


@auth_bp.route('/auth/reset-password/<token>', methods=['GET'])
def reset_password_page(token):
    """Validate token and render the reset form."""
    try:
        _verify_student_reset_token(token)
    except SignatureExpired:
        return render_template('reset_password.html', error='This reset link has expired. Please request a new one.', token=token, user_type='student')
    except BadSignature:
        return render_template('reset_password.html', error='Invalid reset link.', token=token, user_type='student')
    return render_template('reset_password.html', token=token, error=None, user_type='student')


@auth_bp.route('/auth/reset-password/<token>', methods=['POST'])
def reset_password(token):
    """Validate token, update password."""
    try:
        email = _verify_student_reset_token(token)
    except (SignatureExpired, BadSignature):
        return jsonify({"success": False, "message": "Invalid or expired reset link."}), 400

    data = request.get_json(silent=True) or {}
    new_password = data.get('password', '')

    # Validate password strength
    if len(new_password) < 8:
        return jsonify({"success": False, "message": "Password must be at least 8 characters."}), 400
    if not re.search(r'[A-Z]', new_password):
        return jsonify({"success": False, "message": "Password must contain an uppercase letter."}), 400
    if not re.search(r'[a-z]', new_password):
        return jsonify({"success": False, "message": "Password must contain a lowercase letter."}), 400
    if not re.search(r'[0-9]', new_password):
        return jsonify({"success": False, "message": "Password must contain a digit."}), 400

    user = StudentDetails.query.filter_by(email=email).first()
    if user is None:
        return jsonify({"success": False, "message": "Account not found."}), 404

    user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
    db.session.commit()

    return jsonify({"success": True, "message": "Password reset successful. You can now log in."})


def _send_student_reset_email(to_email, reset_url):
    """Send a password-reset email via SMTP."""
    mail_server = current_app.config.get('MAIL_SERVER')
    mail_port = current_app.config.get('MAIL_PORT', 587)
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    mail_sender = current_app.config.get('MAIL_DEFAULT_SENDER', mail_username)

    if not mail_server or not mail_username or not mail_password:
        logger.warning('Mail not configured – cannot send reset email to %s', to_email)
        return

    subject = 'EdgePsych – Password Reset'
    body = (
        f"Hello,\n\n"
        f"We received a request to reset your student account password.\n\n"
        f"Click here to reset: {reset_url}\n\n"
        f"This link expires in 1 hour.\n\n"
        f"If you did not request this, please ignore this email.\n\n"
        f"Best regards,\nEdgePsych"
    )

    msg = MIMEMultipart()
    msg['From'] = mail_sender
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(mail_server, int(mail_port)) as server:
            server.starttls()
            server.login(mail_username, mail_password)
            server.send_message(msg)
        logger.info('Student reset email sent to %s', to_email)
    except Exception as exc:
        logger.error('Failed to send student reset email to %s: %s', to_email, exc)


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

"""Firm authentication and dashboard routes."""

import logging
import os
import re
import smtplib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from PIL import Image
from werkzeug.utils import secure_filename
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
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, limiter, socketio
from models.assessment import CareerQuestion, StudentCareerResponse, AptitudeImgResponse
from models.consultancy import ConsultancyFirm, CreditTransaction, FirmAdmin
from models.student import ExamProcess, StudentDetails, TestStatus, Trackaptitude

logger = logging.getLogger(__name__)

firm_bp = Blueprint("firm", __name__)

# Logo upload configuration
ALLOWED_LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}
LOGO_MAX_WIDTH = 200
LOGO_MAX_HEIGHT = 80
LOGO_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'logos')


def _allowed_logo_file(filename):
    """Return True if the filename has an allowed image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_LOGO_EXTENSIONS


# ---------------------------------------------------------------------------
# Page routes (HTML templates)
# ---------------------------------------------------------------------------

@firm_bp.route("/firm")
def firm_login_page():
    """Render the firm login page."""
    return render_template("firm_login.html")


@firm_bp.route("/firm/<firm_name>")
def firm_branded_login_page(firm_name):
    """Render the firm login page with branding for a specific firm.

    Allows URL-based access like /firm/EPSI instead of the generic /firm page.
    """
    firm = ConsultancyFirm.query.filter(
        db.func.lower(ConsultancyFirm.firm_name) == firm_name.lower()
    ).first()
    if firm is None:
        return render_template("firm_login.html", error="Firm not found"), 404

    return render_template(
        "firm_login.html",
        firm=firm,
    )


@firm_bp.route("/firm/dashboard")
@jwt_required(optional=True)
def firm_dashboard_page():
    """Render the firm dashboard page (client-side rendered)."""
    identity = get_jwt_identity()
    if not identity:
        return redirect(url_for("firm.firm_login_page"))
    claims = get_jwt()
    if claims.get("role") != "firm_admin":
        return redirect(url_for("firm.firm_login_page"))
    return render_template("firm_dashboard.html")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_firm_admin():
    """Return the FirmAdmin for the current JWT, or None."""
    claims = get_jwt()
    if claims.get("role") != "firm_admin":
        return None
    identity = get_jwt_identity()
    if identity is None:
        return None
    return db.session.get(FirmAdmin, int(identity))


# ---------------------------------------------------------------------------
# Phase 4 - Firm Authentication
# ---------------------------------------------------------------------------

@firm_bp.route("/api/v1/firm/login", methods=["POST"])
@limiter.limit("5 per minute")
def firm_login():
    """Authenticate a firm admin with email and password, set session cookies."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password are required"}), 400

    admin = FirmAdmin.query.filter_by(email=email).first()
    if admin is None or not check_password_hash(admin.password, password):
        return jsonify({"success": False, "message": "Invalid email or password"}), 401

    # Build JWT with firm-specific claims
    additional_claims = {
        "role": "firm_admin",
        "firm_id": admin.firm_id,
        "username": admin.username,
    }
    access_token = create_access_token(
        identity=str(admin.id), additional_claims=additional_claims
    )
    refresh_token = create_refresh_token(
        identity=str(admin.id), additional_claims=additional_claims
    )

    response = jsonify({
        "success": True,
        "message": "Firm login successful!",
        "redirect": "/firm/dashboard",
    })
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
    return response, 200


@firm_bp.route("/api/v1/firm/logout", methods=["GET"])
@jwt_required(optional=True)
def firm_logout():
    """Clear session / JWT cookies for the firm admin."""
    token = get_jwt()
    if token:
        from app import BLOCKLIST
        BLOCKLIST.add(token["jti"])
    response = jsonify({"message": "Logged out"})
    unset_jwt_cookies(response)
    return response


# ---------------------------------------------------------------------------
# Phase 5 - Firm Dashboard APIs
# ---------------------------------------------------------------------------

@firm_bp.route("/api/v1/firm/dashboard-data", methods=["GET"])
@jwt_required()
def firm_dashboard_data():
    """Return high-level dashboard data for the authenticated firm."""
    admin = _get_firm_admin()
    if admin is None:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    firm = db.session.get(ConsultancyFirm, admin.firm_id)
    if firm is None:
        return jsonify({"success": False, "message": "Firm not found"}), 404

    # Total students count (list is now served by the paginated endpoint)
    total_students = StudentDetails.query.filter_by(firm_id=firm.id).count()

    # Low credit warning when balance falls to 5 or below
    LOW_CREDIT_THRESHOLD = 5
    low_credit_warning = firm.credit_balance <= LOW_CREDIT_THRESHOLD

    return jsonify({
        "success": True,
        "firm_name": firm.firm_name,
        "credit_balance": firm.credit_balance,
        "total_students": total_students,
        "low_credit_warning": low_credit_warning,
        "logo_url": firm.logo_url,
        "primary_color": firm.primary_color,
        "secondary_color": firm.secondary_color,
    })


@firm_bp.route("/api/v1/firm/credits/transactions", methods=["GET"])
@jwt_required()
def firm_credit_transactions():
    """Return the last 100 credit transactions for the authenticated firm."""
    admin = _get_firm_admin()
    if admin is None:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    transactions = (
        CreditTransaction.query
        .filter_by(firm_id=admin.firm_id)
        .order_by(CreditTransaction.created_at.desc())
        .limit(100)
        .all()
    )

    transactions_list = [
        {
            "id": t.id,
            "student_id": t.student_id,
            "credits_used": t.credits_used,
            "transaction_type": t.transaction_type,
            "description": t.description,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in transactions
    ]

    return jsonify({
        "success": True,
        "transactions": transactions_list,
    })


# ---------------------------------------------------------------------------
# Phase 6 – Paginated Student List (Intern 6)
# ---------------------------------------------------------------------------

@firm_bp.route("/api/v1/firm/students", methods=["GET"])
@jwt_required()
def firm_students_list():
    """Return a paginated list of students belonging to the authenticated firm."""
    admin = _get_firm_admin()
    if admin is None:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    search = request.args.get("search", "", type=str).strip()

    # Clamp per_page to a sensible range
    per_page = max(1, min(per_page, 100))

    query = StudentDetails.query.filter_by(firm_id=admin.firm_id)

    if search:
        like_term = f"%{search}%"
        query = query.filter(
            db.or_(
                StudentDetails.first_name.ilike(like_term),
                StudentDetails.last_name.ilike(like_term),
                StudentDetails.email.ilike(like_term),
            )
        )

    pagination = query.order_by(StudentDetails.id).paginate(
        page=page, per_page=per_page, error_out=False
    )

    total_career_questions = CareerQuestion.query.count()

    students = []
    for s in pagination.items:
        test_status = TestStatus.query.filter_by(user_id=s.id).first()
        exam_progress = ExamProcess.query.filter_by(student_id=s.id).first()

        career_test_completed = False
        aptitude_test_completed = False

        if exam_progress and exam_progress.last_attempted_question_id >= total_career_questions:
            career_test_completed = True
        elif test_status and test_status.career_test_completed:
            career_test_completed = True

        if test_status and test_status.aptitude_test_completed:
            aptitude_test_completed = True

        # Last attempted aptitude category
        track_apt = Trackaptitude.query.filter_by(student_id=s.id).first()
        last_aptitude_category = track_apt.last_category if track_apt else None

        # Last attempted career question number
        last_career_question = None
        if exam_progress:
            last_career_question = exam_progress.last_attempted_question_id

        students.append({
            "id": s.id,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "email": s.email,
            "country": s.country,
            "grade": s.grade,
            "school_name": s.school_name,
            "can_view_career_result": s.can_view_career_result,
            "career_test_completed": career_test_completed,
            "aptitude_test_completed": aptitude_test_completed,
            "last_aptitude_category": last_aptitude_category,
            "last_career_question": last_career_question,
        })

    return jsonify({
        "success": True,
        "students": students,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page,
    })


# ---------------------------------------------------------------------------
# Phase 7 – Toggle Result Access (Intern 4)
# ---------------------------------------------------------------------------

@firm_bp.route("/api/v1/firm/students/<int:student_id>/toggle-result-access", methods=["POST"])
@jwt_required()
def firm_toggle_result_access(student_id):
    """Toggle result access flags for a student belonging to the firm."""
    admin = _get_firm_admin()
    if admin is None:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    student = db.session.get(StudentDetails, student_id)
    if student is None:
        return jsonify({"success": False, "message": "Student not found"}), 404

    if student.firm_id != admin.firm_id:
        return jsonify({"success": False, "message": "Student does not belong to your firm"}), 403

    data = request.get_json(silent=True) or {}
    can_view = data.get("can_view", False)

    student.can_view_career_result = bool(can_view)
    db.session.commit()

    # Push real-time update to the student's room
    socketio.emit(
        "result_access_updated",
        {"can_view": bool(can_view)},
        room=f"student_{student_id}",
    )

    return jsonify({
        "success": True,
        "message": "Result access updated",
        "can_view": bool(can_view),
    })


# ---------------------------------------------------------------------------
# Firm Admin – Reset Student Test
# ---------------------------------------------------------------------------

@firm_bp.route("/api/v1/firm/students/<int:student_id>/reset-test", methods=["POST"])
@jwt_required()
def firm_reset_student_test(student_id):
    """Reset a student's test data so they can retake the assessment.

    Accepts JSON with: test_type = 'career' | 'aptitude' | 'both'
    """
    admin = _get_firm_admin()
    if admin is None:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    student = db.session.get(StudentDetails, student_id)
    if student is None:
        return jsonify({"success": False, "message": "Student not found"}), 404

    if student.firm_id != admin.firm_id:
        return jsonify({"success": False, "message": "Student does not belong to your firm"}), 403

    data = request.get_json(silent=True) or {}
    test_type = data.get("test_type", "both")

    if test_type not in ("career", "aptitude", "both"):
        return jsonify({"success": False, "message": "Invalid test_type. Use 'career', 'aptitude', or 'both'."}), 400

    reset_items = []

    if test_type in ("career", "both"):
        # Delete career responses
        StudentCareerResponse.query.filter_by(student_id=student_id).delete()
        # Reset exam process (career progress tracker)
        exam = ExamProcess.query.filter_by(student_id=student_id).first()
        if exam:
            db.session.delete(exam)
        # Update test status
        ts = TestStatus.query.filter_by(user_id=student_id).first()
        if ts:
            ts.career_test_completed = False
        reset_items.append("career")

    if test_type in ("aptitude", "both"):
        # Delete aptitude responses
        AptitudeImgResponse.query.filter_by(student_id=student_id).delete()
        # Reset aptitude tracker
        track = Trackaptitude.query.filter_by(student_id=student_id).first()
        if track:
            db.session.delete(track)
        # Update test status
        ts = TestStatus.query.filter_by(user_id=student_id).first()
        if ts:
            ts.aptitude_test_completed = False
        reset_items.append("aptitude")

    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Reset: {', '.join(reset_items)} test(s) for student {student_id}",
    })


# ---------------------------------------------------------------------------
# Phase 8 – Firm Admin Report Downloads (Intern 5)
# ---------------------------------------------------------------------------

@firm_bp.route("/api/v1/firm/students/<int:student_id>/report/aptitude", methods=["GET"])
@jwt_required()
def firm_download_aptitude(student_id):
    """Serve the aptitude report page for a student belonging to the firm."""
    admin = _get_firm_admin()
    if admin is None:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    student = db.session.get(StudentDetails, student_id)
    if student is None:
        return jsonify({"success": False, "message": "Student not found"}), 404

    if student.firm_id != admin.firm_id:
        return jsonify({"success": False, "message": "Student does not belong to your firm"}), 403

    # Pass firm branding so the report can display the firm's logo and name
    firm = db.session.get(ConsultancyFirm, admin.firm_id)
    return render_template(
        "aptitudefirst.html",
        student_id=student_id,
        firm_logo_url=firm.logo_url if firm else None,
        firm_name=firm.firm_name if firm else None,
    )


@firm_bp.route("/api/v1/firm/students/<int:student_id>/report/career", methods=["GET"])
@jwt_required()
def firm_download_career(student_id):
    """Serve the career report page for a student belonging to the firm."""
    admin = _get_firm_admin()
    if admin is None:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    student = db.session.get(StudentDetails, student_id)
    if student is None:
        return jsonify({"success": False, "message": "Student not found"}), 404

    if student.firm_id != admin.firm_id:
        return jsonify({"success": False, "message": "Student does not belong to your firm"}), 403

    # Pass firm branding so the report can display the firm's logo and name
    firm = db.session.get(ConsultancyFirm, admin.firm_id)
    return render_template(
        "download_career.html",
        student_id=student_id,
        firm_logo_url=firm.logo_url if firm else None,
        firm_name=firm.firm_name if firm else None,
    )


# ---------------------------------------------------------------------------
# Intern 12 – Firm Admin Password Reset
# ---------------------------------------------------------------------------

def _get_reset_serializer():
    """Return a URLSafeTimedSerializer for password reset tokens."""
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _make_firm_reset_token(email):
    s = _get_reset_serializer()
    return s.dumps(email, salt='firm-password-reset')


def _verify_firm_reset_token(token, max_age=3600):
    s = _get_reset_serializer()
    return s.loads(token, salt='firm-password-reset', max_age=max_age)


@firm_bp.route('/firm/forgot-password', methods=['GET'])
def firm_forgot_password_page():
    """Render the forgot-password form for firm admins."""
    return render_template('forgot_password.html', user_type='firm')


@firm_bp.route('/firm/forgot-password', methods=['POST'])
@limiter.limit("5 per minute")
def firm_forgot_password():
    """Accept email, generate reset token and send email."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()

    # Always return 200 – do not reveal whether the email exists
    if email:
        admin = FirmAdmin.query.filter_by(email=email).first()
        if admin:
            token = _make_firm_reset_token(email)
            reset_url = request.url_root.rstrip('/') + f'/firm/reset-password/{token}'
            _send_reset_email(email, reset_url, 'Firm Admin')

    return jsonify({"success": True, "message": "If that email is registered, a reset link has been sent."})


@firm_bp.route('/firm/reset-password/<token>', methods=['GET'])
def firm_reset_password_page(token):
    """Validate token and render the reset form."""
    try:
        _verify_firm_reset_token(token)
    except SignatureExpired:
        return render_template('reset_password.html', error='This reset link has expired. Please request a new one.', token=token, user_type='firm')
    except BadSignature:
        return render_template('reset_password.html', error='Invalid reset link.', token=token, user_type='firm')
    return render_template('reset_password.html', token=token, error=None, user_type='firm')


@firm_bp.route('/firm/reset-password/<token>', methods=['POST'])
def firm_reset_password(token):
    """Validate token, update password."""
    try:
        email = _verify_firm_reset_token(token)
    except (SignatureExpired, BadSignature):
        return jsonify({"success": False, "message": "Invalid or expired reset link."}), 400

    data = request.get_json(silent=True) or {}
    new_password = data.get('password', '')

    # Validate password strength
    if len(new_password) < 8:
        return jsonify({"success": False, "message": "Password must be at least 8 characters."}), 400
    import re
    if not re.search(r'[A-Z]', new_password):
        return jsonify({"success": False, "message": "Password must contain an uppercase letter."}), 400
    if not re.search(r'[a-z]', new_password):
        return jsonify({"success": False, "message": "Password must contain a lowercase letter."}), 400
    if not re.search(r'[0-9]', new_password):
        return jsonify({"success": False, "message": "Password must contain a digit."}), 400

    admin = FirmAdmin.query.filter_by(email=email).first()
    if admin is None:
        return jsonify({"success": False, "message": "Account not found."}), 404

    admin.password = generate_password_hash(new_password, method='pbkdf2:sha256')
    db.session.commit()

    return jsonify({"success": True, "message": "Password reset successful. You can now log in."})


# ---------------------------------------------------------------------------
# Firm Admin – Invite Link Generation
# ---------------------------------------------------------------------------

@firm_bp.route("/api/v1/firm/invite-link", methods=["POST"])
@jwt_required()
def firm_generate_invite_link():
    """Generate a signed invite token for the firm admin's own firm."""
    admin = _get_firm_admin()
    if admin is None:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    firm = db.session.get(ConsultancyFirm, admin.firm_id)
    if firm is None:
        return jsonify({"success": False, "message": "Firm not found"}), 404
    if not firm.is_active:
        return jsonify({"success": False, "message": "Firm is not active"}), 400

    from routes.admin import _get_invite_serializer
    serializer = _get_invite_serializer()
    token = serializer.dumps({'firm_id': firm.id}, salt='firm-invite')

    invite_url = url_for('auth.register_with_firm_token', token=token, _external=True)

    return jsonify({
        'success': True,
        'token': token,
        'invite_url': invite_url,
        'expires_in_days': 30,
    })


# ---------------------------------------------------------------------------
# Firm Admin – Branding (Logo Upload + Firm Name Update)
# ---------------------------------------------------------------------------

@firm_bp.route("/api/v1/firm/branding", methods=["POST"])
@jwt_required()
def firm_update_branding():
    """Update the firm's logo and/or display name.

    Accepts multipart/form-data with optional fields:
    - logo: image file (png/jpg/jpeg/gif/svg), resized to LOGO_MAX_WIDTH x LOGO_MAX_HEIGHT
    - firm_name: new display name for the firm
    """
    admin = _get_firm_admin()
    if admin is None:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    firm = db.session.get(ConsultancyFirm, admin.firm_id)
    if firm is None:
        return jsonify({"success": False, "message": "Firm not found"}), 404

    updated_fields = []

    # Handle firm name update
    new_firm_name = request.form.get('firm_name', '').strip()
    if new_firm_name:
        # Check for duplicate firm name (excluding current firm)
        existing = ConsultancyFirm.query.filter(
            ConsultancyFirm.firm_name == new_firm_name,
            ConsultancyFirm.id != firm.id,
        ).first()
        if existing:
            return jsonify({"success": False, "message": "Firm name already in use"}), 400
        firm.firm_name = new_firm_name
        updated_fields.append('firm_name')

    # Handle logo upload
    logo_file = request.files.get('logo')
    if logo_file and logo_file.filename:
        if not _allowed_logo_file(logo_file.filename):
            return jsonify({"success": False, "message": "Invalid file type. Allowed: png, jpg, jpeg, gif, svg"}), 400

        # Ensure upload directory exists
        upload_dir = os.path.join(current_app.root_path, LOGO_UPLOAD_FOLDER)
        os.makedirs(upload_dir, exist_ok=True)

        # Delete old logo if it exists
        if firm.logo_url:
            old_path = os.path.join(current_app.root_path, firm.logo_url.lstrip('/'))
            if os.path.exists(old_path):
                os.remove(old_path)

        # Generate unique filename
        ext = logo_file.filename.rsplit('.', 1)[1].lower()
        filename = f"firm_{firm.id}_{uuid.uuid4().hex[:8]}.{ext}"
        filename = secure_filename(filename)
        filepath = os.path.join(upload_dir, filename)

        # Resize image to fixed dimensions (skip resize for SVG)
        if ext == 'svg':
            logo_file.save(filepath)
        else:
            img = Image.open(logo_file)
            img = img.convert('RGBA') if img.mode == 'RGBA' else img.convert('RGB')
            img = img.resize((LOGO_MAX_WIDTH, LOGO_MAX_HEIGHT), Image.LANCZOS)
            img.save(filepath)

        firm.logo_url = f"/{LOGO_UPLOAD_FOLDER}/{filename}"
        updated_fields.append('logo')

    if not updated_fields:
        return jsonify({"success": False, "message": "No changes provided"}), 400

    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Updated: {', '.join(updated_fields)}",
        "firm_name": firm.firm_name,
        "logo_url": firm.logo_url,
    })


def _send_reset_email(to_email, reset_url, user_label):
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
        f"We received a request to reset your {user_label} password.\n\n"
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
        logger.info('Reset email sent to %s', to_email)
    except Exception as exc:
        logger.error('Failed to send reset email to %s: %s', to_email, exc)

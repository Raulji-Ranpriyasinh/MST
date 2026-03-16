"""Admin routes: admin dashboard, career scores, career report, toggle access."""

import json
import re
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash

from extensions import db, socketio
from models.assessment import CareerQuestion, StudentCareerResponse, AptitudeImgResponse
from models.consultancy import ConsultancyFirm, CreditTransaction, FirmAdmin
from models.student import ExamProcess, StudentDetails, TestStatus, Trackaptitude
from sqlalchemy.orm import joinedload
from schemas.validation import validate_firm_creation
from services.scoring import get_career_scores, load_mappings

admin_bp = Blueprint('admin', __name__)


def _is_admin():
    """Return True if the current JWT belongs to an admin."""
    claims = get_jwt()
    return claims.get("role") == "admin"


def _is_admin_or_owner(student_id):
    """Return True if the current JWT belongs to an admin, the student
    themselves, or a firm admin whose firm owns the student."""
    claims = get_jwt()
    role = claims.get("role")
    if role == "admin":
        return True
    identity = get_jwt_identity()
    if role == "student" and identity is not None and int(identity) == student_id:
        return True
    if role == "firm_admin":
        student = db.session.get(StudentDetails, student_id)
        if student and student.firm_id == claims.get("firm_id"):
            return True
    return False


@admin_bp.route('/admin_dashboard')
@jwt_required(optional=True)
def admin_dashboard():
    identity = get_jwt_identity()
    if not identity:
        return redirect(url_for('auth.home'))
    claims = get_jwt()
    if claims.get("role") != "admin":
        return redirect(url_for('auth.home'))

    return render_template('admin_dashboard.html')


# ---------------------------------------------------------------------------
# Paginated Admin Student List API  (Intern 1)
# ---------------------------------------------------------------------------

@admin_bp.route('/api/v1/admin/students', methods=['GET'])
@jwt_required()
def admin_students_list():
    """Return a paginated, filterable list of all students for the admin."""
    if not _is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = max(1, min(per_page, 100))

    # Optional filters
    firm_id = request.args.get('firm_id', type=int)
    country = request.args.get('country', '', type=str).strip()
    is_independent = request.args.get('is_independent', '', type=str).strip().lower()
    curriculum = request.args.get('curriculum', '', type=str).strip()
    school_name = request.args.get('school_name', '', type=str).strip()
    referral_source = request.args.get('referral_source', '', type=str).strip()
    search = request.args.get('search', '', type=str).strip()

    query = StudentDetails.query.options(joinedload(StudentDetails.firm))

    if firm_id is not None:
        query = query.filter(StudentDetails.firm_id == firm_id)
    if is_independent == 'true':
        query = query.filter(StudentDetails.firm_id.is_(None))
    elif is_independent == 'false':
        query = query.filter(StudentDetails.firm_id.isnot(None))
    if country:
        query = query.filter(StudentDetails.country == country)
    if curriculum:
        query = query.filter(StudentDetails.curriculum == curriculum)
    if school_name:
        query = query.filter(StudentDetails.school_name == school_name)
    if referral_source:
        query = query.filter(StudentDetails.referral_source == referral_source)
    if search:
        like_term = f"%{search}%"
        query = query.filter(
            db.or_(
                StudentDetails.first_name.ilike(like_term),
                StudentDetails.last_name.ilike(like_term),
                StudentDetails.email.ilike(like_term),
                StudentDetails.mobile_number.ilike(like_term),
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

        firm_name = "Independent"
        if s.firm is not None:
            firm_name = s.firm.firm_name

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
            "mobile": s.mobile_number,
            "country": s.country,
            "curriculum": s.curriculum,
            "school_name": s.school_name,
            "grade": s.grade,
            "referral_source": s.referral_source,
            "firm_id": s.firm_id,
            "firm_name": firm_name,
            "can_view_career_result": s.can_view_career_result,
            "career_test_completed": career_test_completed,
            "aptitude_test_completed": aptitude_test_completed,
            "last_aptitude_category": last_aptitude_category,
            "last_career_question": last_career_question,
        })

    return jsonify({
        "success": True,
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": pagination.page,
        "students": students,
    })


@admin_bp.route('/get_career_scores/<int:student_id>')
@jwt_required()
def get_career_scores_route(student_id):
    # Only admin or the student themselves can access career scores
    if not _is_admin_or_owner(student_id):
        return jsonify({'error': 'Forbidden'}), 403

    result = get_career_scores(student_id)
    if result is None:
        return jsonify({"error": "Student ID not found or no responses recorded"}), 404
    return jsonify(result)


@admin_bp.route('/career_report/<int:student_id>')
@jwt_required()
def career_report(student_id):
    # Only admin or the student themselves can access
    if not _is_admin_or_owner(student_id):
        return jsonify({'error': 'Forbidden'}), 403

    (
        question_subject_dict,
        question_supporting_subject_dict,
        subject_names_dict,
        subject_question_count,
        subject_question_numbers,
        supporting_subject_question_count,
        supporting_subject_question_numbers,
        supporting_subject_names_dict,
    ) = load_mappings()

    # Fetch student responses
    student_responses = StudentCareerResponse.query.filter_by(
        student_id=student_id
    ).all()
    if not student_responses:
        return jsonify({"error": "Student not found or no responses"}), 404

    # Calculate main subject scores
    subject_scores = {}
    for response in student_responses:
        q_id = response.question_id
        weight = response.response_weight
        if q_id in question_subject_dict:
            for sub_id in question_subject_dict[q_id]:
                subject_scores[sub_id] = subject_scores.get(sub_id, 0) + weight

    subject_scores = {
        sub_id: min((score / (subject_question_count[sub_id] * 2)) * 100, 100)
        if subject_question_count.get(sub_id, 0) > 0
        else 0
        for sub_id, score in subject_scores.items()
    }

    # Get top 9 subjects
    top_subjects = sorted(
        [
            {
                "subject_id": sub_id,
                "field": subject_names_dict.get(sub_id, "Unknown"),
                "score": round(subject_scores[sub_id]),
            }
            for sub_id in subject_scores
            if sub_id in subject_names_dict
        ],
        key=lambda x: x["score"],
        reverse=True,
    )[:9]

    # Load external JSON files
    with open('career_fields.json') as f:
        career_fields = json.load(f)["career_fields"]

    with open('career_field_checklists.json') as f:
        career_checklists = json.load(f)["career_field_checklists"]

    with open('career_supporting.json') as f:
        career_supporting = json.load(f)

    with open('D_A_level.json') as f:
        a_level_data = json.load(f)

    with open('D_IB_level.json') as f:
        ib_level_data = json.load(f)

    # Calculate supporting subject scores
    supporting_scores = {}
    for response in student_responses:
        q_id = response.question_id
        weight = response.response_weight
        if q_id in question_supporting_subject_dict:
            for sup_id in question_supporting_subject_dict[q_id]:
                supporting_scores[sup_id] = supporting_scores.get(sup_id, 0) + weight

    supporting_scores = {
        sup_id: min((score / (supporting_subject_question_count[sup_id] * 2)) * 100, 100)
        if supporting_subject_question_count.get(sup_id, 0) > 0
        else 0
        for sup_id, score in supporting_scores.items()
    }

    # Build final data per top field
    for subject in top_subjects:
        field_name = subject["field"]
        subject["description"] = ""
        subject["careers"] = []
        subject["checklist"] = []
        subject["supporting_subjects"] = []
        subject["a_level_subjects"] = {}
        subject["ib_level_subjects"] = {}

        if field_name in career_fields:
            subject["careers"] = career_fields[field_name]
            subject["description"] = career_fields[field_name][0].get("description", "")

        if field_name in career_checklists:
            subject["checklist"] = career_checklists[field_name]

        if field_name in career_supporting:
            for sub_name, description in career_supporting[field_name].items():
                sup_id = None
                for sid, name in supporting_subject_names_dict.items():
                    if name.lower() == sub_name.lower():
                        sup_id = sid
                        break
                score = round(supporting_scores.get(sup_id, 0)) if sup_id else 0
                subject["supporting_subjects"].append({
                    "subject_id": sup_id,
                    "name": sub_name,
                    "score": score,
                    "description": description,
                })

        for entry in a_level_data:
            if entry["Career Area"].lower() == field_name.lower():
                subject["a_level_subjects"] = entry
                break

        for entry in ib_level_data:
            if entry["Career Area"].lower() == field_name.lower():
                subject["ib_level_subjects"] = entry
                break

    return jsonify({"student_id": student_id, "top_fields": top_subjects})


# ---------------------------------------------------------------------------
# Phase 7 – Admin Firm Management
# ---------------------------------------------------------------------------

@admin_bp.route('/admin/firms', methods=['GET'])
@jwt_required()
def list_firms():
    """Return a list of all consultancy firms."""
    if not _is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    firms = ConsultancyFirm.query.order_by(ConsultancyFirm.id).all()
    firms_list = []
    for f in firms:
        # Fetch the first admin for this firm (if any)
        admin = FirmAdmin.query.filter_by(firm_id=f.id).first()
        firms_list.append({
            "id": f.id,
            "firm_name": f.firm_name,
            "contact_email": f.contact_email,
            "contact_phone": f.contact_phone,
            "credit_balance": f.credit_balance,
            "price_per_assessment": float(f.price_per_assessment),
            "is_active": f.is_active,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "admin_username": admin.username if admin else None,
            "admin_email": admin.email if admin else None,
        })
    return jsonify({"success": True, "firms": firms_list})


@admin_bp.route('/admin/firms', methods=['POST'])
@jwt_required()
def create_firm():
    """Create a new consultancy firm together with its first admin account."""
    if not _is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    # Validate all fields (firm + admin credentials)
    is_valid, errors = validate_firm_creation(data)
    if not is_valid:
        return jsonify({"success": False, "message": "; ".join(errors)}), 400

    firm_name = data["firm_name"].strip()
    contact_email = data["contact_email"].strip()
    contact_phone = (data.get("contact_phone") or "").strip() or None
    price_per_assessment = data.get("price_per_assessment", 0.00)

    admin_username = data["admin_username"].strip()
    admin_email = data["admin_email"].strip()
    admin_password = data["admin_password"]

    # Check for duplicate firm name or contact email
    existing_firm = ConsultancyFirm.query.filter(
        db.or_(
            ConsultancyFirm.firm_name == firm_name,
            ConsultancyFirm.contact_email == contact_email,
        )
    ).first()
    if existing_firm:
        return jsonify({"success": False, "message": "Firm name or contact email already exists"}), 400

    # Check for duplicate admin username or email
    existing_admin = FirmAdmin.query.filter(
        db.or_(
            FirmAdmin.username == admin_username,
            FirmAdmin.email == admin_email,
        )
    ).first()
    if existing_admin:
        return jsonify({"success": False, "message": "Admin username or email already exists"}), 400

    # Create firm
    firm = ConsultancyFirm(
        firm_name=firm_name,
        contact_email=contact_email,
        contact_phone=contact_phone,
        price_per_assessment=price_per_assessment,
    )
    db.session.add(firm)
    db.session.flush()  # get firm.id before committing

    # Create firm admin with hashed password
    hashed_password = generate_password_hash(admin_password, method='pbkdf2:sha256')
    firm_admin = FirmAdmin(
        firm_id=firm.id,
        username=admin_username,
        email=admin_email,
        password=hashed_password,
    )
    db.session.add(firm_admin)
    db.session.commit()

    # Send welcome email to the new firm admin (Intern 15)
    _send_welcome_email(firm, firm_admin, admin_password)

    return jsonify({
        "success": True,
        "message": "Firm and admin account created successfully",
        "firm": {
            "id": firm.id,
            "firm_name": firm.firm_name,
            "contact_email": firm.contact_email,
            "contact_phone": firm.contact_phone,
            "credit_balance": firm.credit_balance,
            "price_per_assessment": float(firm.price_per_assessment),
            "is_active": firm.is_active,
            "created_at": firm.created_at.isoformat() if firm.created_at else None,
            "admin_username": firm_admin.username,
            "admin_email": firm_admin.email,
        },
    }), 201


@admin_bp.route('/admin/firms/<int:firm_id>/credits', methods=['POST'])
@jwt_required()
def add_firm_credits(firm_id):
    """Admin adds credits to a firm's balance."""
    if not _is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    credits = data.get("credits")
    if credits is None or not isinstance(credits, int) or credits <= 0:
        return jsonify({"success": False, "message": "credits must be a positive integer"}), 400

    firm = db.session.get(ConsultancyFirm, firm_id)
    if firm is None:
        return jsonify({"success": False, "message": "Firm not found"}), 404

    firm.credit_balance += credits

    transaction = CreditTransaction(
        firm_id=firm.id,
        credits_used=credits,
        transaction_type='purchase',
        description=data.get("description", f"Admin added {credits} credits"),
    )
    db.session.add(transaction)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"{credits} credits added",
        "credit_balance": firm.credit_balance,
    })


# ---------------------------------------------------------------------------
# Intern 15 – Firm Branding + Welcome Email
# ---------------------------------------------------------------------------

_HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

logger = logging.getLogger(__name__)


def _send_welcome_email(firm, firm_admin, raw_password):
    """Send a welcome email to a newly created firm admin.

    Uses SMTP settings from app config.  If mail is not configured the
    helper logs a warning and returns silently so firm creation is never
    blocked by email delivery.
    """
    mail_server = current_app.config.get('MAIL_SERVER')
    mail_port = current_app.config.get('MAIL_PORT', 587)
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = current_app.config.get('MAIL_PASSWORD')
    mail_sender = current_app.config.get('MAIL_DEFAULT_SENDER', mail_username)

    if not mail_server or not mail_username or not mail_password:
        logger.warning('Mail not configured – skipping welcome email for %s', firm_admin.email)
        return

    login_url = request.url_root.rstrip('/') + '/firm'

    subject = f"Welcome to EdgePsych – {firm.firm_name}"
    body = (
        f"Hello {firm_admin.username},\n\n"
        f"Your firm admin account for {firm.firm_name} has been created.\n\n"
        f"Login URL: {login_url}\n"
        f"Email: {firm_admin.email}\n"
        f"Password: {raw_password}\n\n"
        f"Please change your password after first login.\n\n"
        f"Best regards,\nEdgePsych Admin"
    )

    msg = MIMEMultipart()
    msg['From'] = mail_sender
    msg['To'] = firm_admin.email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP(mail_server, int(mail_port)) as server:
            server.starttls()
            server.login(mail_username, mail_password)
            server.send_message(msg)
        logger.info('Welcome email sent to %s', firm_admin.email)
    except Exception as exc:
        logger.error('Failed to send welcome email to %s: %s', firm_admin.email, exc)


@admin_bp.route('/admin/firms/<int:firm_id>/branding', methods=['PATCH'])
@jwt_required()
def update_firm_branding(firm_id):
    """Update branding fields (logo_url, primary_color, secondary_color) for a firm."""
    if not _is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    firm = db.session.get(ConsultancyFirm, firm_id)
    if firm is None:
        return jsonify({"success": False, "message": "Firm not found"}), 404

    logo_url = data.get('logo_url')
    primary_color = data.get('primary_color')
    secondary_color = data.get('secondary_color')

    # Validate hex colours
    for label, value in [('primary_color', primary_color), ('secondary_color', secondary_color)]:
        if value is not None and value != '' and not _HEX_COLOR_RE.match(value):
            return jsonify({"success": False, "message": f"Invalid {label} format. Use #RRGGBB."}), 400

    if logo_url is not None:
        firm.logo_url = logo_url or None
    if primary_color is not None:
        firm.primary_color = primary_color or None
    if secondary_color is not None:
        firm.secondary_color = secondary_color or None

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Branding updated",
        "firm": {
            "id": firm.id,
            "firm_name": firm.firm_name,
            "logo_url": firm.logo_url,
            "primary_color": firm.primary_color,
            "secondary_color": firm.secondary_color,
        },
    })


# ---------------------------------------------------------------------------
# Phase 8 – Firm Invite-Link Generation
# ---------------------------------------------------------------------------

_INVITE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days in seconds


def _get_invite_serializer():
    """Return a URLSafeTimedSerializer using the app's SECRET_KEY."""
    from flask import current_app
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


@admin_bp.route('/admin/firms/<int:firm_id>/invite-link', methods=['POST'])
@jwt_required()
def generate_invite_link(firm_id):
    """Generate a signed invite token for a firm (admin only)."""
    if not _is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    firm = db.session.get(ConsultancyFirm, firm_id)
    if firm is None:
        return jsonify({'success': False, 'message': 'Firm not found'}), 404
    if not firm.is_active:
        return jsonify({'success': False, 'message': 'Firm is not active'}), 400

    serializer = _get_invite_serializer()
    token = serializer.dumps({'firm_id': firm.id}, salt='firm-invite')

    invite_url = url_for('auth.register_with_firm_token', token=token, _external=True)

    return jsonify({
        'success': True,
        'token': token,
        'invite_url': invite_url,
        'expires_in_days': 30,
    })


@admin_bp.route('/api/v1/admin/students/<int:student_id>/reset-test', methods=['POST'])
@jwt_required()
def admin_reset_student_test(student_id):
    """Reset a student's test data so they can retake the assessment.

    Accepts JSON with: test_type = 'career' | 'aptitude' | 'both'
    """
    if not _is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    student = db.session.get(StudentDetails, student_id)
    if student is None:
        return jsonify({"success": False, "message": "Student not found"}), 404

    data = request.get_json(silent=True) or {}
    test_type = data.get("test_type", "both")

    if test_type not in ("career", "aptitude", "both"):
        return jsonify({"success": False, "message": "Invalid test_type. Use 'career', 'aptitude', or 'both'."}), 400

    reset_items = []

    if test_type in ("career", "both"):
        StudentCareerResponse.query.filter_by(student_id=student_id).delete()
        exam = ExamProcess.query.filter_by(student_id=student_id).first()
        if exam:
            db.session.delete(exam)
        ts = TestStatus.query.filter_by(user_id=student_id).first()
        if ts:
            ts.career_test_completed = False
        reset_items.append("career")

    if test_type in ("aptitude", "both"):
        AptitudeImgResponse.query.filter_by(student_id=student_id).delete()
        track = Trackaptitude.query.filter_by(student_id=student_id).first()
        if track:
            db.session.delete(track)
        ts = TestStatus.query.filter_by(user_id=student_id).first()
        if ts:
            ts.aptitude_test_completed = False
        reset_items.append("aptitude")

    db.session.commit()

    return jsonify({
        "success": True,
        "message": f"Reset: {', '.join(reset_items)} test(s) for student {student_id}",
    })


@admin_bp.route('/toggle_career_access/<int:student_id>', methods=['POST'])
@jwt_required()
def toggle_career_access(student_id):
    if not _is_admin():
        return jsonify({'error': 'Forbidden'}), 403

    student = db.session.execute(
        db.select(StudentDetails).where(StudentDetails.id == student_id)
    ).scalar_one_or_none()

    if student:
        allow = request.form.get('can_view') == 'true'
        student.can_view_career_result = allow
        db.session.commit()
        # Push to student's room
        socketio.emit('result_access_updated', {'can_view': allow}, room=f'student_{student_id}')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return '', 204
    return redirect(url_for('admin.admin_dashboard'))

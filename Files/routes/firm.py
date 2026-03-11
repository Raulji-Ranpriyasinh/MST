"""Firm authentication and dashboard routes."""

import logging

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
from werkzeug.security import check_password_hash

from extensions import db, limiter, socketio
from models.assessment import CareerQuestion
from models.consultancy import ConsultancyFirm, CreditTransaction, FirmAdmin
from models.student import ExamProcess, StudentDetails, TestStatus

logger = logging.getLogger(__name__)

firm_bp = Blueprint("firm", __name__)


# ---------------------------------------------------------------------------
# Page routes (HTML templates)
# ---------------------------------------------------------------------------

@firm_bp.route("/firm")
def firm_login_page():
    """Render the firm login page."""
    return render_template("firm_login.html")


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

    # Reuse the same template used by the student download route
    return render_template("aptitudefirst.html", student_id=student_id)


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

    # Reuse the same template used by the student download route
    return render_template("download_career.html", student_id=student_id)

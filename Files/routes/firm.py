"""Firm authentication and dashboard routes."""

import logging

from flask import Blueprint, jsonify, request
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

from extensions import db, limiter
from models.consultancy import ConsultancyFirm, CreditTransaction, FirmAdmin
from models.student import StudentDetails

logger = logging.getLogger(__name__)

firm_bp = Blueprint("firm", __name__, url_prefix="/api/v1/firm")


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

@firm_bp.route("/login", methods=["POST"])
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


@firm_bp.route("/logout", methods=["GET"])
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

@firm_bp.route("/dashboard-data", methods=["GET"])
@jwt_required()
def firm_dashboard_data():
    """Return high-level dashboard data for the authenticated firm."""
    admin = _get_firm_admin()
    if admin is None:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    firm = db.session.get(ConsultancyFirm, admin.firm_id)
    if firm is None:
        return jsonify({"success": False, "message": "Firm not found"}), 404

    # Fetch students linked to this firm
    students = StudentDetails.query.filter_by(firm_id=firm.id).all()
    students_list = [
        {
            "id": s.id,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "email": s.email,
        }
        for s in students
    ]

    # Low credit warning when balance falls to 5 or below
    LOW_CREDIT_THRESHOLD = 5
    low_credit_warning = firm.credit_balance <= LOW_CREDIT_THRESHOLD

    return jsonify({
        "success": True,
        "firm_name": firm.firm_name,
        "credit_balance": firm.credit_balance,
        "students": students_list,
        "low_credit_warning": low_credit_warning,
    })


@firm_bp.route("/credits/transactions", methods=["GET"])
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

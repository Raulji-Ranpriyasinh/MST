"""Student routes: dashboard, programmes, download pages, student data endpoints."""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required, verify_jwt_in_request

from extensions import db
from models.assessment import CareerQuestion
from models.student import ExamProcess, StudentDetails, TestStatus
from services.scoring import CATEGORY_MAPPING, get_aptitude_results, get_aptitude_scores

student_bp = Blueprint('student', __name__)


def _get_student_identity():
    """Return (user_id: int, claims: dict) from a valid JWT, or (None, {})."""
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None, {}
    identity = get_jwt_identity()
    if identity is None:
        return None, {}
    claims = get_jwt()
    if claims.get("role") != "student":
        return None, {}
    return int(identity), claims


def _check_ownership(student_id):
    """Verify the requesting user owns this student_id or is an admin."""
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return False
    identity = get_jwt_identity()
    if identity is None:
        return False
    claims = get_jwt()
    role = claims.get("role")
    if role == "admin":
        return True
    return role == "student" and int(identity) == student_id


@student_bp.route('/dashboard')
@jwt_required(optional=True)
def dashboard():
    identity = get_jwt_identity()
    if not identity:
        return redirect(url_for('auth.home'))
    claims = get_jwt()
    if claims.get("role") != "student":
        return redirect(url_for('auth.home'))
    user_id = int(identity)
    user_email = claims.get("email", "")
    user_first_name = claims.get("first_name", "")
    return render_template(
        'dashboard.html', email=user_email, user_id=user_id, first_name=user_first_name
    )


@student_bp.route('/programmes')
@jwt_required(optional=True)
def programmes():
    identity = get_jwt_identity()
    if not identity:
        return redirect(url_for('auth.home'))
    claims = get_jwt()
    if claims.get("role") != "student":
        return redirect(url_for('auth.home'))
    user_id = int(identity)
    user_email = claims.get("email", "")
    user_first_name = claims.get("first_name", "")

    test_status = TestStatus.query.filter_by(user_id=user_id).first()

    # Check career question progress
    exam_progress = ExamProcess.query.filter_by(student_id=user_id).first()
    career_test_completed = False

    total_career_questions = CareerQuestion.query.count()
    if exam_progress and exam_progress.last_attempted_question_id >= total_career_questions:
        career_test_completed = True
    elif test_status:
        career_test_completed = test_status.career_test_completed

    # Get student details to fetch can_view_career_result
    student = db.session.execute(
        db.select(StudentDetails).where(StudentDetails.id == user_id)
    ).scalar_one_or_none()

    can_view_career_result = False
    if student:
        can_view_career_result = student.can_view_career_result

    return render_template(
        'programmers.html',
        email=user_email,
        user_id=user_id,
        first_name=user_first_name,
        career_completed=career_test_completed,
        aptitude_completed=test_status.aptitude_test_completed if test_status else False,
        can_view_career_result=can_view_career_result,
    )


@student_bp.route('/download_aptitude/<int:student_id>')
@jwt_required(optional=True)
def download_aptitude(student_id):
    # Authorization check: only the student themselves or admin can access
    if not _check_ownership(student_id):
        return jsonify({'error': 'Forbidden'}), 403
    return render_template('aptitudefirst.html', student_id=student_id)


@student_bp.route('/download_career/<int:student_id>')
@jwt_required(optional=True)
def download_career(student_id):
    # Authorization check: only the student themselves or admin can access
    if not _check_ownership(student_id):
        return jsonify({'error': 'Forbidden'}), 403
    return render_template('download_career.html', student_id=student_id)


@student_bp.route('/get_student_data/<int:student_id>', methods=['GET'])
@jwt_required(optional=True)
def get_student_data(student_id):
    # Authorization check
    if not _check_ownership(student_id):
        return jsonify({'error': 'Forbidden'}), 403

    result = get_aptitude_scores(student_id)
    if result is None:
        return jsonify({"error": "Student not found"}), 404
    if result["scores"] is None:
        return jsonify({
            "student_id": student_id,
            "name": result["name"],
            "scores": "No responses found",
        }), 404
    return jsonify(result)


@student_bp.route('/get_results', methods=['GET', 'POST'])
@jwt_required(optional=True)
def get_results():
    student_id = request.json.get('student_id') if request.json else None
    if not student_id:
        return jsonify({"error": "Student ID is required"}), 400

    # Authorization check
    if not _check_ownership(student_id):
        return jsonify({'error': 'Forbidden'}), 403

    data = get_aptitude_results(student_id)
    return jsonify(data)


@student_bp.route('/get_student_dataa', methods=['POST'])
@jwt_required(optional=True)
def get_student_dataa():
    data = request.json
    student_id = data.get('student_id')

    # Authorization check
    if not _check_ownership(student_id):
        return jsonify({'error': 'Forbidden'}), 403

    student = db.session.get(StudentDetails, student_id)
    if not student:
        return jsonify({"error": "Student not found"}), 404
    full_name = f"{student.first_name} {student.last_name}"
    return jsonify({"student_id": student_id, "name": full_name})

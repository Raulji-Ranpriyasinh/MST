"""Student routes: dashboard, programmes, download pages, student data endpoints."""

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from extensions import db
from models.student import ExamProcess, StudentDetails, TestStatus
from services.scoring import CATEGORY_MAPPING, get_aptitude_results, get_aptitude_scores

student_bp = Blueprint('student', __name__)


def _require_student_login():
    """Check if a student is logged in via session. Returns user_id or None."""
    return session.get('user_id')


def _check_ownership(student_id):
    """Verify the requesting user owns this student_id or is an admin."""
    user_id = session.get('user_id')
    admin_id = session.get('admin_id')
    return user_id == student_id or admin_id is not None


@student_bp.route('/dashboard')
def dashboard():
    user_id = _require_student_login()
    if not user_id:
        return redirect(url_for('auth.home'))
    user_email = session.get('user_email')
    user_first_name = session.get('user_first_name')
    return render_template(
        'dashboard.html', email=user_email, user_id=user_id, first_name=user_first_name
    )


@student_bp.route('/programmes')
def programmes():
    user_id = _require_student_login()
    if not user_id:
        return redirect(url_for('auth.home'))

    test_status = TestStatus.query.filter_by(user_id=user_id).first()
    user_email = session.get('user_email')
    user_first_name = session.get('user_first_name')

    # Check career question progress
    exam_progress = ExamProcess.query.filter_by(student_id=user_id).first()
    career_test_completed = False

    if exam_progress and exam_progress.last_attempted_question_id >= 300:
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
def download_aptitude(student_id):
    # Authorization check: only the student themselves or admin can access
    if not _check_ownership(student_id):
        return jsonify({'error': 'Forbidden'}), 403
    return render_template('aptitudefirst.html', student_id=student_id)


@student_bp.route('/download_career/<int:student_id>')
def download_career(student_id):
    # Authorization check: only the student themselves or admin can access
    if not _check_ownership(student_id):
        return jsonify({'error': 'Forbidden'}), 403
    return render_template('download_career.html', student_id=student_id)


@student_bp.route('/get_student_data/<int:student_id>', methods=['GET'])
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

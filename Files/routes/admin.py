"""Admin routes: admin dashboard, career scores, career report, toggle access."""

import json

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from extensions import db, socketio
from models.assessment import CareerQuestion, StudentCareerResponse
from models.student import ExamProcess, StudentDetails, TestStatus
from services.scoring import get_career_scores, load_mappings

admin_bp = Blueprint('admin', __name__)


def _is_admin():
    """Return True if the current JWT belongs to an admin."""
    claims = get_jwt()
    return claims.get("role") == "admin"


def _is_admin_or_owner(student_id):
    """Return True if the current JWT belongs to an admin or the student themselves."""
    claims = get_jwt()
    role = claims.get("role")
    if role == "admin":
        return True
    identity = get_jwt_identity()
    return role == "student" and identity is not None and int(identity) == student_id


@admin_bp.route('/admin_dashboard')
@jwt_required(optional=True)
def admin_dashboard():
    identity = get_jwt_identity()
    if not identity:
        return redirect(url_for('auth.home'))
    claims = get_jwt()
    if claims.get("role") != "admin":
        return redirect(url_for('auth.home'))

    students = StudentDetails.query.all()

    students_with_tests = []
    for student in students:
        test_status = TestStatus.query.filter_by(user_id=student.id).first()
        exam_progress = ExamProcess.query.filter_by(student_id=student.id).first()

        career_test_completed = False
        aptitude_test_completed = False

        total_career_questions = CareerQuestion.query.count()
        if exam_progress and exam_progress.last_attempted_question_id >= total_career_questions:
            career_test_completed = True
        elif test_status and test_status.career_test_completed:
            career_test_completed = True

        if test_status and test_status.aptitude_test_completed:
            aptitude_test_completed = True

        student.career_test_completed = career_test_completed
        student.aptitude_test_completed = aptitude_test_completed

        students_with_tests.append(student)

    unique_countries = {student.country for student in students if student.country}
    unique_curriculums = {student.curriculum for student in students if student.curriculum}
    unique_schools = {student.school_name for student in students if student.school_name}
    unique_referrals = {
        student.referral_source for student in students if student.referral_source
    }

    return render_template(
        'admin_dashboard.html',
        students=students_with_tests,
        unique_countries=unique_countries,
        unique_curriculums=unique_curriculums,
        unique_schools=unique_schools,
        unique_referrals=unique_referrals,
    )


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

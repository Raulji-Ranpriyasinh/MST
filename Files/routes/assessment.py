"""Assessment routes: career questions, aptitude questions, response submission."""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from extensions import db
from models.assessment import (
    AptitudeAllQuestions,
    AptitudeImgResponse,
    AptitudeTextQuestions,
    CareerQuestion,
    StudentCareerResponse,
)
from models.student import ExamProcess, TestStatus, Trackaptitude

assessment_bp = Blueprint('assessment', __name__)


@assessment_bp.route('/career_assessment')
@jwt_required(optional=True)
def career_assessment():
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
        'career_assessment.html',
        email=user_email,
        user_id=user_id,
        first_name=user_first_name,
    )


@assessment_bp.route('/aptitude_questionnaire')
@jwt_required(optional=True)
def aptitude_questionnaire():
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
        'aptitude_questionnaire.html',
        email=user_email,
        user_id=user_id,
        first_name=user_first_name,
    )


@assessment_bp.route('/career_questions', methods=['GET'])
@jwt_required()
def career_questions():
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({'success': False, 'message': 'User not logged in'}), 401

    student_id = int(get_jwt_identity())

    # Get last attempted question from ExamProcess table
    exam_progress = ExamProcess.query.filter_by(student_id=student_id).first()

    if exam_progress:
        next_question_id = exam_progress.last_attempted_question_id + 1
    else:
        next_question_id = 1

    # Fetch the next question
    question = CareerQuestion.query.filter_by(question_number=next_question_id).first()

    if not question:
        return jsonify({'success': False, 'message': 'No more questions available'}), 404

    total_questions = CareerQuestion.query.count()

    return jsonify({
        'success': True,
        'question_number': question.question_number,
        'question_text': question.question,
        'total_questions': total_questions,
    })


@assessment_bp.route('/submit_response', methods=['POST'])
@jwt_required()
def submit_response():
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({'success': False, 'message': 'User not logged in'}), 401

    data = request.json
    student_id = int(get_jwt_identity())
    first_name = claims.get("first_name", "")
    email = claims.get("email", "")

    question_id = data.get('question_id')

    question = CareerQuestion.query.filter_by(
        question_number=question_id
    ).first()
    if not question:
        return jsonify({'success': False, 'message': 'Invalid question ID'}), 400

    # Deduplication: prevent duplicate responses for the same question
    existing = StudentCareerResponse.query.filter_by(
        student_id=student_id,
        question_id=question_id,
    ).first()
    if existing:
        return jsonify({'success': True, 'message': 'Already recorded'}), 200

    # Save response
    new_response = StudentCareerResponse(
        student_id=student_id,
        first_name=first_name,
        email=email,
        question_id=data['question_id'],
        response_weight=data['response_weight'],
    )
    db.session.add(new_response)

    # Update last attempted question in ExamProcess table
    exam_progress = ExamProcess.query.filter_by(student_id=student_id).first()

    if exam_progress:
        exam_progress.last_attempted_question_id = data['question_id']
    else:
        exam_progress = ExamProcess(
            student_id=student_id,
            email=email,
            firstname=first_name,
            last_attempted_question_id=data['question_id'],
        )
        db.session.add(exam_progress)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Response saved!'})


@assessment_bp.route('/aptitudegetquestion', methods=['GET'])
def aptitudegetquestion():
    try:
        # Fetch all unique categories dynamically
        categories = db.session.query(AptitudeAllQuestions.category).distinct().all()
        categories_list = [c[0] for c in categories]

        all_questions = {}

        for category in categories_list:
            questions = (
                AptitudeAllQuestions.query.filter_by(category=category)
                .order_by(db.func.rand())
                .limit(30)
                .all()
            )

            all_questions[category] = [
                {
                    'id': q.id,
                    'question_text': q.question_text,
                    'question_image_url': (
                        url_for('static', filename=q.question_image, _external=True)
                        if q.question_image
                        else None
                    ),
                    'option_a_text': q.option_a_text,
                    'option_a_image_url': (
                        url_for('static', filename=q.option_a_image, _external=True)
                        if q.option_a_image
                        else None
                    ),
                    'option_b_text': q.option_b_text,
                    'option_b_image_url': (
                        url_for('static', filename=q.option_b_image, _external=True)
                        if q.option_b_image
                        else None
                    ),
                    'option_c_text': q.option_c_text,
                    'option_c_image_url': (
                        url_for('static', filename=q.option_c_image, _external=True)
                        if q.option_c_image
                        else None
                    ),
                    'option_d_text': q.option_d_text,
                    'option_d_image_url': (
                        url_for('static', filename=q.option_d_image, _external=True)
                        if q.option_d_image
                        else None
                    ),
                    'category': q.category,
                }
                for q in questions
            ]

        return jsonify({'questions_by_category': all_questions})

    except Exception as e:
        return jsonify({'error': 'Database error', 'message': str(e)}), 500


@assessment_bp.route('/submit_category_responses', methods=['POST'])
@jwt_required()
def submit_category_responses():
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({"success": False, "message": "Not logged in"}), 401

    data = request.get_json()
    student_id = int(get_jwt_identity())
    category = data.get('category')
    responses = data.get('responses')

    try:
        # Count expected questions for this category from the DB
        expected_count = AptitudeAllQuestions.query.filter_by(
            category=category
        ).count()

        answered_count = 0
        for question_id_str, selected_option in responses.items():
            question_id = int(question_id_str)
            question = AptitudeAllQuestions.query.filter_by(id=question_id).first()
            if not question:
                continue

            if selected_option is None or selected_option == "0":
                is_correct = 0
            else:
                is_correct = 1 if selected_option == question.correct_option else 0
                answered_count += 1

            existing_response = AptitudeImgResponse.query.filter_by(
                student_id=student_id, question_id=question_id
            ).first()

            if existing_response:
                existing_response.selected_option = selected_option
                existing_response.is_correct = is_correct
            else:
                new_response = AptitudeImgResponse(
                    student_id=student_id,
                    question_id=question_id,
                    selected_option=selected_option,
                    is_correct=is_correct,
                    category=category,
                )
                db.session.add(new_response)

        # Determine if category is complete (all expected questions answered)
        is_complete = answered_count >= expected_count

        # Update Trackaptitude
        track = Trackaptitude.query.filter_by(student_id=student_id).first()
        if not track:
            track = Trackaptitude(student_id=student_id, last_category=category)
            db.session.add(track)
        else:
            track.last_category = category

        # Update TestStatus if last category
        if track.last_category.upper() == 'SPATIAL':
            test_status = TestStatus.query.filter_by(user_id=student_id).first()
            if not test_status:
                test_status = TestStatus(user_id=student_id)
                db.session.add(test_status)
            test_status.aptitude_test_completed = True

        db.session.commit()
        return jsonify({
            "success": True,
            "complete": is_complete,
            "answered": answered_count,
            "expected": expected_count,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)})

    finally:
        db.session.close()


@assessment_bp.route('/aptitudetextgetquestion', methods=['GET'])
@jwt_required()
def aptitudetextgetquestion():
    try:
        claims = get_jwt()
        if claims.get("role") != "student":
            return jsonify({'error': 'User not logged in'}), 401

        student_id = int(get_jwt_identity())

        categories = db.session.query(
            AptitudeTextQuestions.aptitudecategory
        ).distinct().all()
        categories_list = [c[0] for c in categories]

        all_text_questions = {}

        for category in categories_list:
            questions = (
                AptitudeTextQuestions.query.filter_by(aptitudecategory=category)
                .order_by(db.func.rand())
                .limit(30)
                .all()
            )
            all_text_questions[category] = [q.to_dict() for q in questions]

        # Fetch last attempted category
        track = Trackaptitude.query.filter_by(student_id=student_id).first()
        last_category = track.last_category if track else None

        if not all_text_questions:
            return jsonify({
                'message': 'No questions found',
                'questions_by_category': {},
                'last_category': last_category,
            }), 404

        return jsonify({
            'questions_by_category': all_text_questions,
            'last_category': last_category,
        })

    except Exception as e:
        return jsonify({'error': 'Database error', 'message': str(e)}), 500


@assessment_bp.route('/get_last_category', methods=['GET'])
@jwt_required()
def get_last_category():
    claims = get_jwt()
    if claims.get("role") != "student":
        return jsonify({'success': False, 'message': 'User not logged in'}), 401

    student_id = int(get_jwt_identity())
    track = Trackaptitude.query.filter_by(student_id=student_id).first()

    if track:
        return jsonify({'success': True, 'last_category': track.last_category})
    else:
        return jsonify({'success': True, 'last_category': None})

"""Server-side scoring and result calculation logic.

All scoring weights, category mappings, and result computations
live here — never in frontend JavaScript.
"""

from collections import defaultdict

from extensions import db
from models.assessment import (
    AptitudeAllQuestions,
    AptitudeImgResponse,
    QuestionSubject,
    QuestionSupportingSubject,
    StudentCareerResponse,
    Subject,
    SupportingSubject,
)
from models.student import StudentDetails


CATEGORY_MAPPING = {
    "SPATIAL": "Spatial Reasoning",
    "ABSTRACT": "Abstract Reasoning",
    "NUMEBERS": "Numerical Reasoning",
    "Verbal": "Verbal Reasoning",
    "arithmetic": "Arithmetic Calculation",
    "spellingmistake": "Spelling Mistake",
    "workingQA": "Working Quickly and Accurately",
}


def load_mappings():
    """Load question-subject and supporting-subject mappings from the database."""
    question_subject_dict = {}
    subject_question_count = {}
    subject_question_numbers = {}

    for entry in QuestionSubject.query.all():
        q_num = entry.question_number
        sub_id = entry.subject_id
        question_subject_dict.setdefault(q_num, []).append(sub_id)
        subject_question_count[sub_id] = subject_question_count.get(sub_id, 0) + 1
        subject_question_numbers.setdefault(sub_id, []).append(q_num)

    question_supporting_subject_dict = {}
    supporting_subject_question_count = {}
    supporting_subject_question_numbers = {}

    for entry in QuestionSupportingSubject.query.all():
        q_num = entry.question_number
        sup_id = entry.supporting_id
        question_supporting_subject_dict.setdefault(q_num, []).append(sup_id)
        supporting_subject_question_count[sup_id] = (
            supporting_subject_question_count.get(sup_id, 0) + 1
        )
        supporting_subject_question_numbers.setdefault(sup_id, []).append(q_num)

    subject_names_dict = {
        sub.subject_id: sub.subject_name for sub in Subject.query.all()
    }
    supporting_subject_names_dict = {
        sup.supporting_id: sup.supporting_subject_name
        for sup in SupportingSubject.query.all()
    }

    return (
        question_subject_dict,
        question_supporting_subject_dict,
        subject_names_dict,
        subject_question_count,
        subject_question_numbers,
        supporting_subject_question_count,
        supporting_subject_question_numbers,
        supporting_subject_names_dict,
    )


def get_aptitude_scores(student_id):
    """Compute aptitude scores for a student. Returns dict with name and scores."""
    student = db.session.get(StudentDetails, student_id)
    if not student:
        return None

    full_name = f"{student.first_name} {student.last_name}"
    scores = {category: 0 for category in CATEGORY_MAPPING.values()}

    responses = (
        db.session.query(AptitudeImgResponse.is_correct, AptitudeAllQuestions.category)
        .join(
            AptitudeAllQuestions,
            AptitudeImgResponse.question_id == AptitudeAllQuestions.id,
        )
        .filter(AptitudeImgResponse.student_id == student_id)
        .all()
    )

    if not responses:
        return {"student_id": student_id, "name": full_name, "scores": None}

    for is_correct, category in responses:
        mapped_category = CATEGORY_MAPPING.get(category, category)
        if mapped_category in scores:
            scores[mapped_category] += is_correct

    sorted_scores = dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))
    return {"student_id": student_id, "name": full_name, "scores": sorted_scores}


def get_aptitude_results(student_id):
    """Compute per-category aptitude results (total, correct, accuracy)."""
    results = (
        db.session.query(
            AptitudeAllQuestions.category,
            db.func.count(AptitudeImgResponse.question_id).label("total_questions"),
            db.func.sum(
                db.case((AptitudeImgResponse.is_correct == 1, 1), else_=0)
            ).label("correct_answers"),
        )
        .join(
            AptitudeImgResponse,
            AptitudeAllQuestions.id == AptitudeImgResponse.question_id,
        )
        .filter(AptitudeImgResponse.student_id == student_id)
        .group_by(AptitudeAllQuestions.category)
        .all()
    )

    data = [
        {
            "category": CATEGORY_MAPPING.get(r[0], r[0]),
            "total": r[1],
            "correct": r[2] if r[2] is not None else 0,
        }
        for r in results
    ]
    data.sort(key=lambda x: x['correct'], reverse=True)
    return data


def get_career_scores(student_id):
    """Compute career interest scores for a student."""
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

    # Build main subject -> supporting subject mapping
    main_supporting_subject_map = defaultdict(set)
    for qid, main_sub_ids in question_subject_dict.items():
        supporting_ids = question_supporting_subject_dict.get(qid, [])
        for main_sub in main_sub_ids:
            main_supporting_subject_map[main_sub].update(supporting_ids)
    main_supporting_subject_map = {k: list(v) for k, v in main_supporting_subject_map.items()}

    # Fetch student responses
    student_responses = StudentCareerResponse.query.filter_by(student_id=student_id).all()
    if not student_responses:
        return None

    # Score dictionaries
    subject_scores = {}
    supporting_subject_scores = {}

    for response in student_responses:
        question_id = response.question_id
        weight = response.response_weight

        if question_id in question_subject_dict:
            for subject_id in question_subject_dict[question_id]:
                subject_scores[subject_id] = subject_scores.get(subject_id, 0) + weight

        if question_id in question_supporting_subject_dict:
            for supporting_id in question_supporting_subject_dict[question_id]:
                supporting_subject_scores[supporting_id] = (
                    supporting_subject_scores.get(supporting_id, 0) + weight
                )

    # Normalize main subjects
    subject_scores = {
        sub_id: min((score / (subject_question_count[sub_id] * 2)) * 100, 100)
        if subject_question_count.get(sub_id, 0) > 0
        else 0
        for sub_id, score in subject_scores.items()
    }

    # Normalize supporting subjects
    supporting_subject_scores = {
        sup_id: min(
            (score / (supporting_subject_question_count[sup_id] * 2)) * 100, 100
        )
        if supporting_subject_question_count.get(sup_id, 0) > 0
        else 0
        for sup_id, score in supporting_subject_scores.items()
    }

    # Build subjects list with overall match score
    subjects_list = []
    for sub in subject_scores:
        if sub in subject_names_dict:
            main_score = min(round(subject_scores[sub]), 100)
            related_supporting_ids = main_supporting_subject_map.get(sub, [])
            related_scores = [
                supporting_subject_scores.get(sid, 0) for sid in related_supporting_ids
            ]

            if related_scores:
                overall_score = round(
                    (main_score + sum(related_scores)) / (1 + len(related_scores))
                )
            else:
                overall_score = main_score

            subjects_list.append(
                {
                    "name": subject_names_dict[sub],
                    "score": main_score,
                    "overall_match_score": overall_score,
                    "total_questions": subject_question_count.get(sub, 0),
                    "questions": subject_question_numbers.get(sub, []),
                }
            )

    subjects_list.sort(key=lambda x: x["score"], reverse=True)

    supporting_subjects_list = [
        {
            "name": supporting_subject_names_dict[sup],
            "score": min(round(supporting_subject_scores[sup]), 100),
            "total_questions": supporting_subject_question_count.get(sup, 0),
            "questions": supporting_subject_question_numbers.get(sup, []),
        }
        for sup in supporting_subject_scores
        if sup in supporting_subject_names_dict
    ]

    return {
        "subjects": subjects_list,
        "supporting_subjects": supporting_subjects_list,
    }

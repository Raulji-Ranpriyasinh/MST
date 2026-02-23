from extensions import db


class StudentDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    mobile_number = db.Column(db.String(20), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    curriculum = db.Column(db.String(100), nullable=False)
    school_name = db.Column(db.String(255), nullable=False)
    grade = db.Column(db.String(50), nullable=False)
    referral_source = db.Column(db.String(255))
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    can_view_career_result = db.Column(db.Boolean, default=False)


class ExamProcess(db.Model):
    __tablename__ = 'exam_process'

    student_id = db.Column(db.Integer, primary_key=True, unique=True)
    email = db.Column(db.String(255), nullable=False)
    firstname = db.Column(db.String(255), nullable=False)
    last_attempted_question_id = db.Column(db.Integer, nullable=False, default=1)
    timestamp = db.Column(
        db.TIMESTAMP,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    def __init__(self, student_id, email, firstname, last_attempted_question_id):
        self.student_id = student_id
        self.email = email
        self.firstname = firstname
        self.last_attempted_question_id = last_attempted_question_id


class TestStatus(db.Model):
    __tablename__ = 'test_status'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('student_details.id', ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    career_test_completed = db.Column(db.Boolean, default=False, nullable=False)
    aptitude_test_completed = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return (
            f"<TestStatus(user_id={self.user_id}, "
            f"career_test={self.career_test_completed}, "
            f"aptitude_test={self.aptitude_test_completed})>"
        )


class Trackaptitude(db.Model):
    student_id = db.Column(db.Integer, nullable=False, primary_key=True)
    last_category = db.Column(db.String(50), nullable=False)

from extensions import db


class CareerQuestion(db.Model):
    __tablename__ = 'careerquestion'
    question_number = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question = db.Column(db.Text, nullable=False)


class AptitudeImgQuestions(db.Model):
    __tablename__ = 'aptitudeimgquestions'
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String(500), nullable=False)
    question_image = db.Column(db.String(500), nullable=False)
    option_a_image = db.Column(db.String(500), nullable=False)
    option_b_image = db.Column(db.String(500), nullable=False)
    option_c_image = db.Column(db.String(500), nullable=False)
    option_d_image = db.Column(db.String(500), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)
    category = db.Column(db.String(50), nullable=False)


class AptitudeImgResponse(db.Model):
    __tablename__ = 'aptitudeimgresponse'

    response_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey('student_details.id'),
        nullable=False,
        index=True,
    )
    email = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    question_id = db.Column(
        db.Integer,
        db.ForeignKey('aptitudeallquestions_new.id'),
        nullable=False,
        index=True,
    )
    selected_option = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    response_time = db.Column(db.DateTime, default=db.func.now())
    category = db.Column(db.String(50), nullable=False)


class StudentCareerResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    question_id = db.Column(db.Integer, nullable=False)
    response_weight = db.Column(db.Integer, nullable=False)


class AptitudeTextQuestions(db.Model):
    __tablename__ = 'aptitude_questions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    aptitudecategory = db.Column(db.String(50), nullable=False)
    question = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)

    def to_dict(self):
        """Convert object to dictionary for JSON response."""
        return {
            'id': self.id,
            'category': self.aptitudecategory,
            'question_text': self.question,
            'option_a': self.option_a,
            'option_b': self.option_b,
            'option_c': self.option_c,
            'option_d': self.option_d,
            'correct_option': self.correct_option,
        }


class AptitudeAllQuestions(db.Model):
    __tablename__ = 'aptitudeallquestions_new'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(100), nullable=False)
    question_text = db.Column(db.Text, nullable=True)
    question_image = db.Column(db.String(255), nullable=True)
    option_a_text = db.Column(db.String(255), nullable=True)
    option_a_image = db.Column(db.String(255), nullable=True)
    option_b_text = db.Column(db.String(255), nullable=True)
    option_b_image = db.Column(db.String(255), nullable=True)
    option_c_text = db.Column(db.String(255), nullable=True)
    option_c_image = db.Column(db.String(255), nullable=True)
    option_d_text = db.Column(db.String(255), nullable=True)
    option_d_image = db.Column(db.String(255), nullable=True)
    correct_option = db.Column(db.String(1), nullable=False)

    def __repr__(self):
        return f"<AptitudeQuestion id={self.id} category={self.category}>"


class QuestionSubject(db.Model):
    __tablename__ = 'question_subject'
    question_number = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, primary_key=True)


class QuestionSupportingSubject(db.Model):
    __tablename__ = 'question_supporting_subject'
    question_number = db.Column(db.Integer, primary_key=True)
    supporting_id = db.Column(db.Integer, primary_key=True)


class Subject(db.Model):
    __tablename__ = 'subjects'
    subject_id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(255))


class SupportingSubject(db.Model):
    __tablename__ = 'supporting_subjects'
    supporting_id = db.Column(db.Integer, primary_key=True)
    supporting_subject_name = db.Column(db.String(255))

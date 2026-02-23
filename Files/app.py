from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import mysql.connector
import random
import time
app = Flask(__name__)
import json

# Secret key for session management
app.secret_key = 'your_secret_key'
#------------------------------------------
# # Database Configuration
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://admin:Edgespych12345@myappdb.cer0aq8cezxb.us-east-1.rds.amazonaws.com:3306/myappdb'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:8888@localhost/exam'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_recycle": 280,
    "pool_pre_ping": True
}

#Helo

db = SQLAlchemy(app)

#Admin Model
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

# Define StudentDetails Model
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

   
class CareerQuestion(db.Model):
    __tablename__ = 'careerquestion'  # Match the exact MySQL table name
    question_number = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question = db.Column(db.Text, nullable=False)  # Match the column name in MySQL
    
# aptitude question

class AptitudeImgQuestions(db.Model):
    __tablename__ = 'aptitudeimgquestions'
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.String(500), nullable=False)  # ✅ Added question text
    question_image = db.Column(db.String(500), nullable=False)
    option_a_image = db.Column(db.String(500), nullable=False)
    option_b_image = db.Column(db.String(500), nullable=False)
    option_c_image = db.Column(db.String(500), nullable=False)
    option_d_image = db.Column(db.String(500), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)
    category = db.Column(db.String(50), nullable=False)


class AptitudeImgResponse(db.Model):
    __tablename__ = 'aptitudeimgresponse'

    response_id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # ✅ Match DB column name
    #id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_details.id'), nullable=False, index=True)
    email = db.Column(db.String(100), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('aptitudeallquestions_new.id'), nullable=False, index=True)
    selected_option = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    response_time = db.Column(db.DateTime, default=db.func.now())  # ✅ Added response time
    category = db.Column(db.String(50), nullable=False)
#-------------------------------------------------------------------------------
#----------------------------------------------------------------------------------------
class StudentCareerResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    question_id = db.Column(db.Integer, nullable=False)  # Foreign Key reference if needed
    response_weight = db.Column(db.Integer, nullable=False)  # 2 for Yes, 1 for Maybe, 0 for No
#-------------------------------------------------------------------------------------------------
class ExamProcess(db.Model):
    __tablename__ = 'exam_process'  # Matches your table name

    student_id = db.Column(db.Integer, primary_key=True, unique=True)  # Unique student entry
    email = db.Column(db.String(255), nullable=False)
    firstname = db.Column(db.String(255), nullable=False)
    last_attempted_question_id = db.Column(db.Integer, nullable=False, default=1)
    timestamp = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def __init__(self, student_id, email, firstname, last_attempted_question_id):
        self.student_id = student_id
        self.email = email
        self.firstname = firstname
        self.last_attempted_question_id = last_attempted_question_id




class AptitudeTextQuestions(db.Model):
    __tablename__ = 'aptitude_questions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    aptitudecategory = db.Column(db.String(50), nullable=False)
    question = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)  # Stores 'A', 'B', 'C', or 'D'

    def to_dict(self):
        """Convert object to dictionary for JSON response"""
        return {
            'id': self.id,
            'category': self.aptitudecategory,
            'question_text': self.question,
            'option_a': self.option_a,
            'option_b': self.option_b,
            'option_c': self.option_c,
            'option_d': self.option_d,
            'correct_option': self.correct_option
        }
    
class AptitudeAllQuestions(db.Model):
    __tablename__ = 'aptitudeallquestions_new'  # Change if needed

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

class TestStatus(db.Model):
    __tablename__ = 'test_status'  # Your table name

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('student_details.id', ondelete="CASCADE"), nullable=False, unique=True)
    career_test_completed = db.Column(db.Boolean, default=False, nullable=False)
    aptitude_test_completed = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<TestStatus(student_id={self.student_id}, career_test={self.career_test_completed}, aptitude_test={self.aptitude_test_completed})>"


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

class Trackaptitude(db.Model):
    
    student_id = db.Column(db.Integer, nullable=False, primary_key=True)
    last_category = db.Column(db.String(50), nullable=False)
    


# Create tables
with app.app_context():
    db.create_all()

# Home route to serve index.html
@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register', methods=['POST'])
def register():
    data = request.json

    # Check if user already exists
    existing_user = StudentDetails.query.filter_by(email=data['email']).first()
    if existing_user:
        return jsonify({'success': False, 'message': 'Email already registered!'}), 400

    # Hash password
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')

    # Create new user
    new_user = StudentDetails(
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data['email'],
        mobile_number=data['mobile_number'],
        country=data['country'],
        curriculum=data['curriculum'],
        school_name=data['school_name'],
        grade=data['grade'],
        referral_source=data.get('referral_source', ''),
        password=hashed_password
    )

    # Save to DB
    db.session.add(new_user)
    db.session.commit()

    # Log in the user (set session)
    session['user_id'] = new_user.id
    session['user_email'] = new_user.email
    session['user_first_name'] = new_user.first_name

    return jsonify({'success': True, 'message': 'Registered and logged in successfully!'})


# Login API with redirection to dashboard
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = StudentDetails.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        session['user_id'] = user.id  # Store user ID in session
        session['user_email'] = user.email  # Store user email in session
        session['user_first_name'] = user.first_name  # Store student first name in session
        return jsonify({'success': True, 'message': 'Login successful!', 'redirect': url_for('dashboard')}), 200
    else:
        return jsonify({'success': False, 'message': 'Invalid email or password!'}), 401

# Admin Login Route
@app.route('/admin_login', methods=['POST'])
def admin_login():
    data = request.json
    admin = Admin.query.filter_by(username=data['username'], password=data['password']).first()
    if admin:
        session['admin_id'] = admin.id
        return jsonify({'success': True, 'message': 'Admin login successful!', 'redirect': url_for('admin_dashboard')}), 200
    else:
        return jsonify({'success': False, 'message': 'Invalid username or password!'}), 401

@app.route('/admin', methods=['GET'])
def admin_login_page():
    return render_template('adminlogin.html')


# Dashboard route
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    user_id = session.get('user_id')  # Retrieve student ID from session
    user_email = session.get('user_email')  # Retrieve email from session
    user_first_name = session.get('user_first_name')
    return render_template('dashboard.html', email=user_email, user_id=user_id,first_name=user_first_name)

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('home'))
    
    students = StudentDetails.query.all()

    # Attach test statuses to each student
    students_with_tests = []
    for student in students:
        test_status = TestStatus.query.filter_by(user_id=student.id).first()
        exam_progress = ExamProcess.query.filter_by(student_id=student.id).first()

        # Check career and aptitude test completion
        career_test_completed = False
        aptitude_test_completed = False

        if exam_progress and exam_progress.last_attempted_question_id >= 300:
            career_test_completed = True
        elif test_status and test_status.career_test_completed:
            career_test_completed = True

        if test_status and test_status.aptitude_test_completed:
            aptitude_test_completed = True

        # Add extra fields to the student object (temporary attributes)
        student.career_test_completed = career_test_completed
        student.aptitude_test_completed = aptitude_test_completed

        students_with_tests.append(student)

    # Extract unique values for filters
    unique_countries = {student.country for student in students if student.country}
    unique_curriculums = {student.curriculum for student in students if student.curriculum}
    unique_schools = {student.school_name for student in students if student.school_name}
    unique_referrals = {student.referral_source for student in students if student.referral_source}

    return render_template('admin_dashboard.html',
                           students=students_with_tests,
                           unique_countries=unique_countries,
                           unique_curriculums=unique_curriculums,
                           unique_schools=unique_schools,
                           unique_referrals=unique_referrals)



# Admin Logout
@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_id', None)
    return redirect(url_for('home'))
                         
@app.route('/programmes')
def programmes():
    user_id = session.get('user_id')  # Get user_id from session

    test_status = TestStatus.query.filter_by(user_id=user_id).first()  # Test completion flags
    user_email = session.get('user_email')  
    user_first_name = session.get('user_first_name')

    # --- Check career question progress ---
    exam_progress = ExamProcess.query.filter_by(student_id=user_id).first()
    career_test_completed = False

    if exam_progress and exam_progress.last_attempted_question_id >= 300:
        career_test_completed = True
    elif test_status:
        # Fallback if already stored in TestStatus
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
        can_view_career_result=can_view_career_result
    )



#----------------------------------------------------------
# Career Assessment Page
@app.route('/career_assessment')
def career_assessment():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    user_id = session.get('user_id')  # Retrieve student ID from session
    user_email = session.get('user_email')  # Retrieve email from session
    user_first_name = session.get('user_first_name')
    return render_template('career_assessment.html', email=user_email, user_id=user_id,first_name=user_first_name)

#----------------------------------------------------
#Add aptiude page///////////////////////////////////////////////////////////////////////////////////////
@app.route('/aptitude_questionnaire')
def aptitude_questionnaire():
    if 'user_id' not in session:
        return redirect(url_for('home'))
    user_id = session.get('user_id')  # Retrieve student ID from session
    user_email = session.get('user_email')  # Retrieve email from session
    user_first_name = session.get('user_first_name')
    return render_template('aptitude_questionnaire.html',email=user_email, user_id=user_id,first_name=user_first_name)

#Main////////////////////////////////////////////////////////////////////////

#////////////////////////////////////////////////////////////////////////////////////////////
@app.route('/career_questions', methods=['GET'])
def career_questions():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'}), 401

    student_id = session.get('user_id')

    # Get last attempted question from ExamProcess table
    exam_progress = ExamProcess.query.filter_by(student_id=student_id).first()

    if exam_progress:
        next_question_id = exam_progress.last_attempted_question_id + 1  # Resume from next question
    else:
        next_question_id = 1  # Start from the first question
    


    # Fetch the next question
    question = CareerQuestion.query.filter_by(question_number=next_question_id).first()

    if not question:
        return jsonify({'success': False, 'message': 'No more questions available'}), 404

    return jsonify({
        'success': True,
        'question_number': question.question_number,
        'question_text': question.question
    })




#--------------------------------------------------------------------------------------------

#--------------------------------------------------------------
@app.route('/submit_response', methods=['POST'])
def submit_response():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'}), 401

    data = request.json
    student_id = session.get('user_id')
    first_name = session.get('user_first_name')
    email = session.get('user_email')

    question = CareerQuestion.query.filter_by(question_number=data.get('question_id')).first()
    if not question:
        return jsonify({'success': False, 'message': 'Invalid question ID'}), 400

    # Save response
    new_response = StudentCareerResponse(
        student_id=student_id,
        first_name=first_name,
        email=email,
        question_id=data['question_id'],
        response_weight=data['response_weight']
    )
    db.session.add(new_response)

    # Update last attempted question in ExamProcess table
    exam_progress = ExamProcess.query.filter_by(student_id=student_id).first()
    
    if exam_progress:
        exam_progress.last_attempted_question_id = data['question_id']  # Update last attempted question
    else:
        exam_progress = ExamProcess(
            student_id=student_id,
            email=email,
            firstname=first_name,
            last_attempted_question_id=data['question_id']
        )
        db.session.add(exam_progress)

    db.session.commit()

    return jsonify({'success': True, 'message': 'Response saved!'})



#/////////////////////////////////////////////////////////////////////////////////////////Demo//////////////////////
@app.route('/aptitudegetquestion', methods=['GET'])
def aptitudegetquestion():
    try:
        with app.app_context():
            # Fetch all unique categories dynamically
            categories = db.session.query(AptitudeAllQuestions.category).distinct().all()
            categories_list = [c[0] for c in categories]  # Convert to list
            
            print("Fetched Categories:", categories_list)  # Debugging

            # Dictionary to store questions categorized by category
            all_questions = {}

            for category in categories_list:
                # Fetch 30 random unique questions per category
                questions = (
                    AptitudeAllQuestions.query
                    .filter_by(category=category)
                    .order_by(db.func.rand())  # Random order
                    .limit(30)  # Limit to 30 per category
                    .all()
                )

                # Store questions in a dictionary categorized by category
                all_questions[category] = [
                    {
                        'id': q.id,
                        'question_text': q.question_text,
                        'question_image_url': url_for('static', filename=q.question_image, _external=True) if q.question_image else None,
                        'option_a_text': q.option_a_text,
                        'option_a_image_url': url_for('static', filename=q.option_a_image, _external=True) if q.option_a_image else None,
                        'option_b_text': q.option_b_text,
                        'option_b_image_url': url_for('static', filename=q.option_b_image, _external=True) if q.option_b_image else None,
                        'option_c_text': q.option_c_text,
                        'option_c_image_url': url_for('static', filename=q.option_c_image, _external=True) if q.option_c_image else None,
                        'option_d_text': q.option_d_text,
                        'option_d_image_url': url_for('static', filename=q.option_d_image, _external=True) if q.option_d_image else None,
                        'category': q.category
                    }
                    for q in questions
                ]

        return jsonify({'questions_by_category': all_questions})

    except Exception as e:
        print(f"Error: {e}")  # Log the error
        return jsonify({'error': 'Database error', 'message': str(e)}), 500


@app.route('/submit_category_responses', methods=['POST'])
def submit_category_responses():
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Not logged in"}), 401

    data = request.get_json()
    student_id = session['user_id']
    category = data.get('category')
    responses = data.get('responses')

    try:
        for question_id_str, selected_option in responses.items():
            question_id = int(question_id_str)
            question = AptitudeAllQuestions.query.filter_by(id=question_id).first()
            if not question:
                continue

            # Always treat unanswered as incorrect
            if selected_option is None or selected_option == "0":
                is_correct = 0
            else:
                is_correct = 1 if selected_option == question.correct_option else 0

            existing_response = AptitudeImgResponse.query.filter_by(
                student_id=student_id, question_id=question_id).first()

            if existing_response:
                existing_response.selected_option = selected_option
                existing_response.is_correct = is_correct
            else:
                new_response = AptitudeImgResponse(
                    student_id=student_id,
                    question_id=question_id,
                    selected_option=selected_option,
                    is_correct=is_correct,
                    category=category
                )
                db.session.add(new_response)

        # ✅ Always update Trackaptitude even if no responses were given
        track = Trackaptitude.query.filter_by(student_id=student_id).first()
        if not track:
            track = Trackaptitude(student_id=student_id, last_category=category)
            db.session.add(track)
        else:
            track.last_category = category

        # ✅ Update TestStatus (if not exists, create it)
        if track.last_category.upper() == 'SPATIAL':
            test_status = TestStatus.query.filter_by(user_id=student_id).first()
            if not test_status:
                test_status = TestStatus(user_id=student_id)
                db.session.add(test_status)

            test_status.aptitude_test_completed = True

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)})

    finally:
        db.session.close()


@app.route('/aptitudetextgetquestion', methods=['GET'])
def aptitudetextgetquestion():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'User not logged in'}), 401

        student_id = session['user_id']
        
        with app.app_context():
            # Fetch all unique categories dynamically
            categories = db.session.query(AptitudeTextQuestions.aptitudecategory).distinct().all()
            categories_list = [c[0] for c in categories]  # Convert to list
            
            print("Fetched Categories:", categories_list)  # Debugging

            all_text_questions = {}

            for category in categories_list:
                print(f"Fetching questions for category: {category}")  # Debugging
                
                questions = (
                    AptitudeTextQuestions.query
                    .filter_by(aptitudecategory=category)
                    .order_by(db.func.rand())  # Random order
                    .limit(30)
                    .all()
                )

                print(f"Questions fetched for {category}: {len(questions)}")  # Debugging
                all_text_questions[category] = [q.to_dict() for q in questions]

            # 🔁 Fetch last attempted category from Trackaptitude
            track = Trackaptitude.query.filter_by(student_id=student_id).first()
            last_category = track.last_category if track else None

        if not all_text_questions:
            return jsonify({'message': 'No questions found', 'questions_by_category': {}, 'last_category': last_category}), 404

        return jsonify({
            'questions_by_category': all_text_questions,
            'last_category': last_category
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': 'Database error', 'message': str(e)}), 500

@app.route('/get_last_category', methods=['GET'])
def get_last_category():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'User not logged in'}), 401

    student_id = session['user_id']
    track = Trackaptitude.query.filter_by(student_id=student_id).first()

    if track:
        return jsonify({'success': True, 'last_category': track.last_category})
    else:
        return jsonify({'success': True, 'last_category': None})

#---------------------------------------------------------------------------------------

@app.route('/debug_static_paths')
def debug_static_paths():
    question = AptitudeImgQuestions.query.first()
    return jsonify({
        'question_image_url': url_for('static', filename=f"question_images/{question.question_image}"),
        'option_a_image_url': url_for('static', filename=f"options/{question.option_a_image}"),
        'option_b_image_url': url_for('static', filename=f"options/{question.option_b_image}"),
        'option_c_image_url': url_for('static', filename=f"options/{question.option_c_image}"),
        'option_d_image_url': url_for('static', filename=f"options/{question.option_d_image}"),
    })


#---------------------------------------------------/////////////////////******************///////////////////----------------------------

category_mapping = {
    "SPATIAL": "Spatial Reasoning",
    "ABSTRACT": "Abstract Reasoning",
    "NUMEBERS": "Numerical Reasoning",
    "Verbal": "Verbal Reasoning",
    "arithmetic": "Arithmetic Calculation",
    "spellingmistake": "Spelling Mistake",
    "workingQA": "Working Quickly and Accurately",
}
@app.route('/get_student_data/<int:student_id>', methods=['GET'])
def get_student_data(student_id):
    student = db.session.get(StudentDetails, student_id)
    if not student:
        return jsonify({"error": "Student not found"}), 404

    full_name = f"{student.first_name} {student.last_name}"
    scores = {category: 0 for category in category_mapping.values()}  # Initialize score dict

    responses = (
        db.session.query(AptitudeImgResponse.is_correct, AptitudeAllQuestions.category)
        .join(AptitudeAllQuestions, AptitudeImgResponse.question_id == AptitudeAllQuestions.id)
        .filter(AptitudeImgResponse.student_id == student_id)
        .all()
    )

    if not responses:
        return jsonify({"student_id": student_id, "name": full_name, "scores": "No responses found"}), 404

    for is_correct, category in responses:
        mapped_category = category_mapping.get(category, category)
        if mapped_category in scores:
            scores[mapped_category] += is_correct  # Count correct responses
    sorted_scores = dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))
    print("✅ Sorted scores:", sorted_scores)
    return jsonify({"student_id": student_id, "name": full_name, "scores": sorted_scores})

@app.route('/get_results', methods=['GET', 'POST'])
def get_results():
    print("🚀 get_results API was called!")  # Debugging
    student_id = request.json.get('student_id')
    if not student_id:
        return jsonify({"error": "Student ID is required"}), 400

    results = db.session.query(
        AptitudeAllQuestions.category,
        db.func.count(AptitudeImgResponse.question_id).label("total_questions"),
        db.func.sum(db.case((AptitudeImgResponse.is_correct == 1, 1), else_=0)).label("correct_answers")
    ).join(AptitudeImgResponse, AptitudeAllQuestions.id == AptitudeImgResponse.question_id).filter(AptitudeImgResponse.student_id == student_id).group_by(AptitudeAllQuestions.category).all()

    data = [{
        "category": category_mapping.get(r[0], r[0]),  # Map categories if needed
        "total": r[1],
        "correct": r[2] if r[2] is not None else 0  # Replace None with 0
    } for r in results]
    data.sort(key=lambda x: x['correct'], reverse=True)
    print("✅ Data sent to frontend:", data)  # Debugging
    return jsonify(data)

@app.route('/download_aptitude/<int:student_id>')
def download_aptitude(student_id):
    return render_template('aptitudefirst.html', student_id=student_id)

@app.route('/download_career/<int:student_id>')
def download_career(student_id):
    return render_template('download_career.html', student_id=student_id)



@app.route('/get_student_dataa', methods=['POST'])
def get_student_dataa():
    data = request.json
    student_id = data.get('student_id')
    student = db.session.get(StudentDetails, student_id)
    if not student:
        return jsonify({"error": "Student not found"}), 404
    full_name = f"{student.first_name} {student.last_name}"
    return jsonify({"student_id": student_id, "name": full_name})




def load_mappings():
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
        supporting_subject_question_count[sup_id] = supporting_subject_question_count.get(sup_id, 0) + 1
        supporting_subject_question_numbers.setdefault(sup_id, []).append(q_num)
    subject_names_dict = {sub.subject_id: sub.subject_name for sub in Subject.query.all()}
    supporting_subject_names_dict = {sup.supporting_id: sup.supporting_subject_name for sup in SupportingSubject.query.all()}

    return (
        question_subject_dict, question_supporting_subject_dict,
        subject_names_dict, subject_question_count, subject_question_numbers,
        supporting_subject_question_count, supporting_subject_question_numbers,
        supporting_subject_names_dict  # ✅ **Newly Added**
    )


@app.route('/get_career_scores/<int:student_id>')
def get_career_scores(student_id):
    # Load mappings
    (
        question_subject_dict, question_supporting_subject_dict,
        subject_names_dict, subject_question_count, subject_question_numbers,
        supporting_subject_question_count, supporting_subject_question_numbers,
        supporting_subject_names_dict
    ) = load_mappings()

    # Build main subject → supporting subject mapping
    from collections import defaultdict
    main_supporting_subject_map = defaultdict(set)

    for qid, main_sub_ids in question_subject_dict.items():
        supporting_ids = question_supporting_subject_dict.get(qid, [])
        for main_sub in main_sub_ids:
            main_supporting_subject_map[main_sub].update(supporting_ids)

    # Convert sets to lists
    main_supporting_subject_map = {k: list(v) for k, v in main_supporting_subject_map.items()}

    # Fetch student responses
    student_responses = StudentCareerResponse.query.filter_by(student_id=student_id).all()
    if not student_responses:
        return jsonify({"error": "Student ID not found or no responses recorded"}), 404

    # Score dictionaries
    subject_scores = {}
    supporting_subject_scores = {}

    # Calculate scores
    for response in student_responses:
        question_id = response.question_id
        weight = response.response_weight

        if question_id in question_subject_dict:
            for subject_id in question_subject_dict[question_id]:
                subject_scores[subject_id] = subject_scores.get(subject_id, 0) + weight

        if question_id in question_supporting_subject_dict:
            for supporting_id in question_supporting_subject_dict[question_id]:
                supporting_subject_scores[supporting_id] = supporting_subject_scores.get(supporting_id, 0) + weight

    # Normalize main subjects
    subject_scores = {
        sub_id: min((score / (subject_question_count[sub_id] * 2)) * 100,100)
        if subject_question_count.get(sub_id, 0) > 0 else 0
        for sub_id, score in subject_scores.items()
    }

    # Normalize supporting subjects
    supporting_subject_scores = {
        sup_id: min((score / (supporting_subject_question_count[sup_id] * 2)) * 100,100)
        if supporting_subject_question_count.get(sup_id, 0) > 0 else 0
        for sup_id, score in supporting_subject_scores.items()
    }

    # Convert main subjects to list and add overall match score
    subjects_list = []
    for sub in subject_scores:
        if sub in subject_names_dict:
            main_score = min(round(subject_scores[sub]), 100)


            # Get supporting subjects related to this main subject
            related_supporting_ids = main_supporting_subject_map.get(sub, [])

            # Get their scores (default 0 if not answered)
            related_scores = [supporting_subject_scores.get(sid, 0) for sid in related_supporting_ids]

            # Calculate overall match score
            if related_scores:
                overall_score = round((main_score + sum(related_scores)) / (1 + len(related_scores)))

                #overall_score = round((sum(related_scores)) / (len(related_scores)), 2)
            else:
                overall_score = main_score

            subjects_list.append({
                "name": subject_names_dict[sub],
                "score": main_score,
                "overall_match_score": overall_score,
                "total_questions": subject_question_count.get(sub, 0),
                "questions": subject_question_numbers.get(sub, [])
            })

    # Sort main subjects by overall match score
    #subjects_list.sort(key=lambda x: x["overall_match_score"], reverse=True)
    subjects_list.sort(key=lambda x: x["score"], reverse=True)
    # Prepare supporting subject list
    supporting_subjects_list = [
        {
            "name": supporting_subject_names_dict[sup],
            "score": min(round(supporting_subject_scores[sup]), 100),

            "total_questions": supporting_subject_question_count.get(sup, 0),
            "questions": supporting_subject_question_numbers.get(sup, [])
        }
        for sup in supporting_subject_scores if sup in supporting_subject_names_dict
    ]

    return jsonify({
        "subjects": subjects_list,
        "supporting_subjects": supporting_subjects_list
    })

@app.route('/career_report/<int:student_id>')
def career_report(student_id):
    # Load mappings
    (
        question_subject_dict, question_supporting_subject_dict,
        subject_names_dict, subject_question_count, subject_question_numbers,
        supporting_subject_question_count, supporting_subject_question_numbers,
        supporting_subject_names_dict
    ) = load_mappings()

    # Fetch student responses
    student_responses = StudentCareerResponse.query.filter_by(student_id=student_id).all()
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
        if subject_question_count.get(sub_id, 0) > 0 else 0
        for sub_id, score in subject_scores.items()
    }

    # Get top 9 subjects
    top_subjects = sorted(
        [
            {
                "subject_id": sub_id,
                "field": subject_names_dict.get(sub_id, "Unknown"),
                "score": round(subject_scores[sub_id])

            }
            for sub_id in subject_scores if sub_id in subject_names_dict
        ],
        key=lambda x: x["score"],
        reverse=True
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
        if supporting_subject_question_count.get(sup_id, 0) > 0 else 0
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

        # Add description and careers
        if field_name in career_fields:
            subject["careers"] = career_fields[field_name]
            subject["description"] = career_fields[field_name][0].get("description", "")

        # Add checklist
        if field_name in career_checklists:
            subject["checklist"] = career_checklists[field_name]

        # Add supporting subjects from career_supporting.json
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
                    "description": description
                })

        # Add A-level subjects
        for entry in a_level_data:
            if entry["Career Area"].lower() == field_name.lower():
                subject["a_level_subjects"] = entry
                break

        # Add IB-level subjects
        for entry in ib_level_data:
            if entry["Career Area"].lower() == field_name.lower():
                subject["ib_level_subjects"] = entry
                break

    return jsonify({
        "student_id": student_id,
        "top_fields": top_subjects
    })


@app.route('/toggle_career_access/<int:student_id>', methods=['POST'])
def toggle_career_access(student_id):
    student = db.session.execute(
        db.select(StudentDetails).where(StudentDetails.id == student_id)
    ).scalar_one_or_none()

    if student:
        allow = request.form.get('can_view') == 'true'
        student.can_view_career_result = allow
        db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return '', 204  # No Content
    return redirect(url_for('admin_dashboard'))


#--------------------------------------------------------------------------------------------
# Logout API
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)

"""Authentication routes: login, register, logout for students and admin."""

from datetime import timedelta

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from flask_jwt_extended import create_access_token
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, limiter
from models.admin import Admin
from models.student import StudentDetails
from schemas.validation import validate_admin_login, validate_login, validate_registration

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def home():
    return render_template('index.html')


@auth_bp.route('/register', methods=['POST'])
@limiter.limit("10 per minute")
def register():
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    # Server-side validation
    is_valid, errors = validate_registration(data)
    if not is_valid:
        return jsonify({'success': False, 'message': '; '.join(errors)}), 400

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
        password=hashed_password,
    )

    db.session.add(new_user)
    db.session.commit()

    # Set session
    session['user_id'] = new_user.id
    session['user_email'] = new_user.email
    session['user_first_name'] = new_user.first_name

    # Generate JWT token
    access_token = create_access_token(
        identity=new_user.id, expires_delta=timedelta(hours=2)
    )

    return jsonify({
        'success': True,
        'message': 'Registered and logged in successfully!',
        'access_token': access_token,
    })


@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    # Server-side validation
    is_valid, errors = validate_login(data)
    if not is_valid:
        return jsonify({'success': False, 'message': '; '.join(errors)}), 400

    user = StudentDetails.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        session['user_id'] = user.id
        session['user_email'] = user.email
        session['user_first_name'] = user.first_name

        # Generate JWT token
        access_token = create_access_token(
            identity=user.id, expires_delta=timedelta(hours=2)
        )

        return jsonify({
            'success': True,
            'message': 'Login successful!',
            'redirect': url_for('student.dashboard'),
            'access_token': access_token,
        }), 200
    else:
        return jsonify({'success': False, 'message': 'Invalid email or password!'}), 401


@auth_bp.route('/admin_login', methods=['POST'])
@limiter.limit("5 per minute")
def admin_login():
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    # Server-side validation
    is_valid, errors = validate_admin_login(data)
    if not is_valid:
        return jsonify({'success': False, 'message': '; '.join(errors)}), 400

    # Query admin by username only, then verify password hash
    admin = Admin.query.filter_by(username=data['username']).first()
    if admin and check_password_hash(admin.password, data['password']):
        session['admin_id'] = admin.id
        return jsonify({
            'success': True,
            'message': 'Admin login successful!',
            'redirect': url_for('admin.admin_dashboard'),
        }), 200
    else:
        return jsonify({'success': False, 'message': 'Invalid username or password!'}), 401


@auth_bp.route('/admin', methods=['GET'])
def admin_login_page():
    return render_template('adminlogin.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.home'))


@auth_bp.route('/admin_logout')
def admin_logout():
    session.pop('admin_id', None)
    return redirect(url_for('auth.home'))

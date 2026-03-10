"""Server-side validation schemas.

Password validation split:
- Frontend validation (JavaScript) = UX convenience and immediate feedback only.
  The confirm-password match check is handled client-side because the backend
  receives only one password field.
- Backend validation (this module) = security enforcement. These checks MUST
  remain even when equivalent client-side validation exists, because any
  JavaScript check can be bypassed via DevTools or direct API calls.
"""

import re


def validate_registration(data):
    """Validate registration input server-side. Returns (is_valid, error_message)."""
    errors = []

    # Required fields
    required = [
        'first_name', 'last_name', 'email', 'mobile_number',
        'country', 'curriculum', 'school_name', 'grade', 'password',
    ]
    for field in required:
        if not data.get(field) or not str(data[field]).strip():
            errors.append(f'{field} is required.')

    if errors:
        return False, errors

    # Email format
    email = data.get('email', '')
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        errors.append('Invalid email format.')

    # Mobile number: exactly 10 digits
    mobile = data.get('mobile_number', '')
    if not re.match(r'^\d{10}$', mobile):
        errors.append('Mobile number must be exactly 10 digits.')

    # Password: at least 8 characters (security enforcement — never remove even
    # when client-side validation exists, as JS checks can be bypassed via DevTools)
    password = data.get('password', '')
    if len(password) < 8:
        errors.append('Password must be at least 8 characters.')

    # Name length
    for field in ['first_name', 'last_name']:
        value = data.get(field, '')
        if len(value) > 100:
            errors.append(f'{field} must not exceed 100 characters.')
        if len(value) < 1:
            errors.append(f'{field} must not be empty.')

    # Country / school name length
    if len(data.get('country', '')) > 100:
        errors.append('Country must not exceed 100 characters.')
    if len(data.get('school_name', '')) > 255:
        errors.append('School name must not exceed 255 characters.')

    # Curriculum must be one of the allowed values
    allowed_curricula = ['IB', 'Cambridge', 'American', 'Other']
    if data.get('curriculum') not in allowed_curricula:
        errors.append(f'Curriculum must be one of: {", ".join(allowed_curricula)}.')

    if errors:
        return False, errors

    return True, []


def validate_login(data):
    """Validate login input server-side. Returns (is_valid, error_message)."""
    errors = []

    if not data.get('email') or not str(data['email']).strip():
        errors.append('Email is required.')

    if not data.get('password'):
        errors.append('Password is required.')

    if errors:
        return False, errors

    return True, []


def validate_admin_login(data):
    """Validate admin login input server-side. Returns (is_valid, error_message)."""
    errors = []

    if not data.get('username') or not str(data['username']).strip():
        errors.append('Username is required.')

    if not data.get('password'):
        errors.append('Password is required.')

    if errors:
        return False, errors

    return True, []


def validate_firm_creation(data):
    """Validate firm creation input (firm details + admin credentials).

    Returns (is_valid, errors_list).
    """
    errors = []

    # --- Firm fields ---
    firm_name = (data.get('firm_name') or '').strip()
    contact_email = (data.get('contact_email') or '').strip()

    if not firm_name:
        errors.append('Firm name is required.')
    elif len(firm_name) > 255:
        errors.append('Firm name must not exceed 255 characters.')

    if not contact_email:
        errors.append('Firm contact email is required.')

    # --- Admin credential fields ---
    admin_username = (data.get('admin_username') or '').strip()
    admin_email = (data.get('admin_email') or '').strip()
    admin_password = data.get('admin_password') or ''

    if not admin_username:
        errors.append('Admin username is required.')
    elif len(admin_username) < 3:
        errors.append('Admin username must be at least 3 characters.')
    elif len(admin_username) > 100:
        errors.append('Admin username must not exceed 100 characters.')
    elif not re.match(r'^[a-zA-Z0-9._-]+$', admin_username):
        errors.append('Admin username may only contain letters, digits, dots, hyphens, and underscores.')

    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not admin_email:
        errors.append('Admin email is required.')
    elif not re.match(email_pattern, admin_email):
        errors.append('Invalid admin email format.')

    if not admin_password:
        errors.append('Admin password is required.')
    else:
        if len(admin_password) < 8:
            errors.append('Admin password must be at least 8 characters.')
        if not re.search(r'[A-Z]', admin_password):
            errors.append('Admin password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', admin_password):
            errors.append('Admin password must contain at least one lowercase letter.')
        if not re.search(r'[0-9]', admin_password):
            errors.append('Admin password must contain at least one digit.')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-]', admin_password):
            errors.append('Admin password must contain at least one special character.')

    if errors:
        return False, errors

    return True, []

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

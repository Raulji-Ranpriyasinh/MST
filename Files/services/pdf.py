"""PDF token generation and verification for secure PDF endpoint."""

import hashlib
import hmac
import secrets
import time

from flask import current_app


def generate_pdf_token(student_id):
    """Generate a short-lived signed token for PDF generation.

    Returns a dict with token and expiry timestamp.
    """
    token = secrets.token_hex(32)
    expiry = int(time.time()) + current_app.config['PDF_TOKEN_TIMEOUT']
    payload = f"{token}:{student_id}:{expiry}"
    secret = current_app.config['PDF_TOKEN_SECRET']
    signature = hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return {
        "token": token,
        "student_id": student_id,
        "expiry": expiry,
        "signature": signature,
    }


def verify_pdf_token(token, student_id, expiry, signature):
    """Verify a PDF token is valid and not expired.

    Returns True if valid, False otherwise.
    """
    # Check expiry
    if int(time.time()) > int(expiry):
        return False

    # Recompute signature
    payload = f"{token}:{student_id}:{expiry}"
    secret = current_app.config['PDF_TOKEN_SECRET']
    expected_signature = hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)

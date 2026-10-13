import re
import secrets
from functools import wraps
from flask import session, redirect, url_for, flash, request, abort, g
from werkzeug.security import generate_password_hash, check_password_hash
from database import query_db, execute_db


def hash_password(password):
    """Hash password securely using Werkzeug (scrypt/pbkdf2)."""
    return generate_password_hash(password)


def verify_password(password, password_hash):
    """Verify plain password against stored hash."""
    return check_password_hash(password_hash, password)


def get_user_by_id(user_id):
    """Fetch user record by ID."""
    query = "SELECT * FROM users WHERE id = ?"
    return query_db(query, (user_id,), one=True)


def get_user_by_email(email):
    """Fetch user record by email (case-insensitive)."""
    query = "SELECT * FROM users WHERE email = ? COLLATE NOCASE"
    return query_db(query, (email.strip().lower(),), one=True)


def authenticate(email, password):
    """
    Authenticate user credentials.
    Returns (user_dict, None) on success or (None, error_message) on failure.
    """
    if not email or not password:
        return None, "Please provide both email and password."

    user = get_user_by_email(email)
    if not user:
        return None, "Invalid email or password."

    if not verify_password(password, user["password_hash"]):
        return None, "Invalid email or password."

    if user["status"] != "active":
        return None, "Your account is suspended. Please contact the library administrator."

    return user, None


def register_member(name, email, password, phone=None):
    """
    Register a new member with validation.
    Returns (user_id, None) on success or (None, error_message).
    """
    name = (name or "").strip()
    email = (email or "").strip().lower()
    password = password or ""
    phone = (phone or "").strip()

    if not name or len(name) < 2:
        return None, "Full name must be at least 2 characters long."

    email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    if not re.match(email_regex, email):
        return None, "Please provide a valid email address."

    if len(password) < 6:
        return None, "Password must be at least 6 characters long."

    existing = get_user_by_email(email)
    if existing:
        return None, "An account with this email address already exists."

    pw_hash = hash_password(password)
    res = execute_db(
        """
        INSERT INTO users (name, email, password_hash, role, status, phone, max_loans)
        VALUES (?, ?, ?, 'member', 'active', ?, 3)
        """,
        (name, email, pw_hash, phone or None),
    )
    return res["lastrowid"], None


def login_user(user):
    """Establish authenticated user session and rotate session ID for fixation protection."""
    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    session["user_role"] = user["role"]
    session["csrf_token"] = generate_csrf_token()


def logout_user():
    """Clear user session completely."""
    session.clear()


def generate_csrf_token():
    """Generate or retrieve a cryptographically secure CSRF token for the session."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


def validate_csrf_token():
    """
    Validate CSRF token on modifying HTTP methods.
    Checks form data or X-CSRF-Token header against session.
    """
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        session_token = session.get("csrf_token")
        submitted_token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if not session_token or not submitted_token or not secrets.compare_digest(session_token, submitted_token):
            abort(400, description="Invalid or missing CSRF token.")


def get_current_user():
    """Get the currently logged-in user record or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(user_id)


def login_required(f):
    """Decorator requiring an active user session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator requiring administrator role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        if session.get("user_role") != "admin":
            flash("Access denied. Administrator privileges required.", "danger")
            return redirect(url_for("member.dashboard"))
        return f(*args, **kwargs)
    return decorated_function


def member_required(f):
    """Decorator requiring authenticated user (admin or member)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

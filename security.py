"""Login helpers: validation rules, login_required and CSRF protection."""
import re
import secrets
from functools import wraps

from flask import abort, redirect, request, session, url_for

STUDENT_ID_PATTERN = re.compile(r"^2\d{6}$")

# Changes every time the app starts, so a restart always sends students back to sign in.
BOOT_ID = secrets.token_hex(8)


def valid_student_id(value):
    """A CSU ID here is seven digits beginning with 2."""
    return bool(STUDENT_ID_PATTERN.match(value or ""))


def password_meets_policy(value):
    """Conventional rules: 8+ characters with upper, lower, number and symbol."""
    value = value or ""
    rules = (r"[A-Z]", r"[a-z]", r"\d", r"[^A-Za-z0-9]")
    return len(value) >= 8 and all(re.search(rule, value) for rule in rules)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "student_id" not in session or session.get("boot") != BOOT_ID:
            session.pop("student_id", None)
            if request.path.startswith("/api/"):
                abort(401)
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def check_csrf():
    """Reject state-changing requests without the session's CSRF token.
    Forms send it as a hidden field; JavaScript sends it in X-CSRF-Token."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
        if not sent or sent != session.get("_csrf"):
            abort(400, description="Your session expired. Refresh the page and try again.")

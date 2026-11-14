"""Sign in and sign out."""
from datetime import timedelta

from flask import (Blueprint, current_app, flash, make_response, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash

from db import get_db, query_one
from security import BOOT_ID, valid_student_id

bp = Blueprint("auth", __name__)


def _safe_next(target):
    """Only allow redirects to pages inside this site."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("dashboard.index")


@bp.route("/")
def root():
    # The site always opens to sign in.
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET" and "student_id" in session:
        # Opening the sign-in page ends any earlier session, so the site always starts here.
        session.clear()

    cookie_name = current_app.config["REMEMBER_COOKIE"]
    # The cookie holds "ID:launch". It only counts for the current launch of the app,
    # so the sign-in page starts blank each time the app is opened.
    saved_id, _, saved_boot = request.cookies.get(cookie_name, "").partition(":")
    remembered_id = saved_id if valid_student_id(saved_id) and saved_boot == BOOT_ID else ""

    # A remembered visitor is greeted by name; everyone else gets the general welcome.
    returning = None
    if remembered_id:
        returning = query_one("SELECT first_name FROM students WHERE student_id = ?", (remembered_id,))

    form = {"student_id": remembered_id, "remember": bool(remembered_id)}
    errors = {}

    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"
        form = {"student_id": student_id, "remember": remember}

        if not student_id:
            errors["student_id"] = "Enter your ID."
        elif not valid_student_id(student_id):
            errors["student_id"] = "Your ID is the 7-digit number on your Viking Card."
        if not password:
            errors["password"] = "Enter your password."

        if not errors:
            student = query_one("SELECT * FROM students WHERE student_id = ?", (student_id,))
            if student is None or not check_password_hash(student["password_hash"], password):
                errors["form"] = "That ID and password don't match. Check both and try again."
            else:
                session.clear()
                session.permanent = False  # cleared when the browser closes
                session["student_id"] = student["student_id"]
                session["boot"] = BOOT_ID
                session["just_signed_in"] = True

                db = get_db()
                db.execute(
                    "UPDATE students SET remember_me = ?, last_login_at = datetime('now') WHERE student_id = ?",
                    (1 if remember else 0, student_id),
                )
                db.commit()

                response = make_response(redirect(_safe_next(request.args.get("next"))))
                if remember:
                    response.set_cookie(
                        cookie_name, f"{student_id}:{BOOT_ID}",
                        max_age=int(timedelta(days=current_app.config["REMEMBER_DAYS"]).total_seconds()),
                        httponly=True, samesite="Lax",
                    )
                else:
                    response.delete_cookie(cookie_name)
                return response

    status = 401 if errors.get("form") else (400 if errors else 200)
    return render_template("login.html", form=form, errors=errors, returning=returning,
                           remembered=bool(remembered_id)), status


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You've signed out. See you soon, Viking!", "success")
    return redirect(url_for("auth.login"))

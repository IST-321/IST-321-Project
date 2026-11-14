"""Orientation checklist, progress and new student resources.

Statuses are kept in Viking Hub's database and changed by the student here.
"""
from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for

from alerts import add_alert, project_now
from db import get_db, query_all, query_one
from security import login_required

bp = Blueprint("orientation", __name__)

STATUSES = ["Not started", "In progress", "Complete"]

RESOURCES = [
    {"icon": "flag", "title": "Orientation dates and registration",
     "text": "Register for New Student Orientation in your applicant portal. Fall orientations run May through August, and spring orientations run November through January.",
     "label": "Orientation", "url": "https://www.csuohio.edu/orientation/orientation"},
    {"icon": "ship", "title": "Viking Voyage",
     "text": "The online Blackboard course every new student completes. Fall and summer students finish it by the Friday before classes begin.",
     "label": "Viking Voyage", "url": "https://www.csuohio.edu/fye/viking-voyage"},
    {"icon": "calendar", "title": "Academic advising",
     "text": "Find your advisor and book appointments in Starfish. Starfish is offline Saturdays from 6:00 PM to 11:59 PM for CampusNet updates.",
     "label": "Starfish for students", "url": "https://www.csuohio.edu/successprograms/starfish-student"},
    {"icon": "book", "title": "Getting ready to register",
     "text": "Registration happens in CampusNet. Earlier orientation dates mean a better choice of classes.",
     "label": "CampusNet", "url": "https://campusnet.csuohio.edu/"},
    {"icon": "info", "title": "New student next steps",
     "text": "CSU's welcome guide walks you through everything to do before your first day of classes.",
     "label": "CSU welcome page", "url": "https://www.csuohio.edu/welcome"},
    {"icon": "map", "title": "Find your way",
     "text": "Use the campus map to find classrooms, offices and campus services before your first week.",
     "label": "Open the campus map", "endpoint": "campus_map.index"},
]

DIRECTORY = [
    ("Enrollment and records", [
        {"name": "All-In-1 Enrollment Services", "text": "Admissions, financial aid, registration and student accounts in one place.",
         "where": "Berkman Hall, Room 116", "phone": "216-687-5411", "email": "allin1@csuohio.edu"},
        {"name": "Viking Card Office", "text": "Your student ID card, replacements and the Online Card Office.",
         "where": "Berkman Hall, Room 112", "phone": "216-875-9888", "email": "vcard.office@csuohio.edu"},
    ]),
    ("Academic support", [
        {"name": "Student Success Programs (Starfish)", "text": "Help finding your advisor, success coach and support services.",
         "where": "Berkman Hall, Room 110", "phone": "216-687-5391", "email": "starfishsupport@csuohio.edu"},
        {"name": "Center for eLearning", "text": "Help with Blackboard and online courses, including Viking Voyage.",
         "where": "Rhodes Tower, Room 201", "phone": "216-687-3960", "email": "elearning@csuohio.edu"},
        {"name": "Michael Schwartz Library", "text": "Study space, research help and laptop loan stations.",
         "where": "Rhodes Tower", "phone": "216-687-2478"},
    ]),
    ("Health, safety and well-being", [
        {"name": "Counseling Center", "text": "Confidential counseling and well-being support for students.",
         "where": "Mather Mansion"},
        {"name": "Health and Wellness Services", "text": "Campus health services for students.",
         "where": "College of Health building"},
        {"name": "Campus Safety and University Police", "text": "Campus safety and police services.",
         "where": "1840 Chester Avenue"},
    ]),
    ("Campus life and services", [
        {"name": "Student Center", "text": "Viking Marketplace, Viking Outfitters campus store, dining and ATM.",
         "where": "2121 Euclid Avenue"},
        {"name": "Center for International Services and Programs", "text": "Orientation and support for international students.",
         "phone": "216-687-3910"},
        {"name": "Technology help", "text": "Help with your CSU account, password and campus technology.",
         "phone": "216-687-5050"},
    ]),
]


def _resolve(link):
    """Links may be full URLs or Flask endpoints for pages inside Viking Hub."""
    if not link:
        return None, False
    if link.startswith("http"):
        return link, True
    return url_for(link), False


def progress_summary(student_id):
    rows = query_all(
        "SELECT status, COUNT(*) AS n FROM orientation_progress WHERE student_id = ? GROUP BY status", (student_id,)
    )
    counts = {s: 0 for s in STATUSES}
    for r in rows:
        counts[r["status"]] = r["n"]
    total = sum(counts.values())
    done = counts["Complete"]
    percent = round(done / total * 100) if total else 0
    if percent == 100:
        message = "Welcome aboard, Viking! Every orientation step is complete."
    elif percent >= 50:
        message = "More than halfway there. Finish your recommended steps to reach shore."
    elif percent > 0:
        message = "You're on your way. Pick up the next step below."
    else:
        message = "Start with the first step below."
    return {"total": total, "complete": done, "in_progress": counts["In progress"],
            "not_started": counts["Not started"], "percent": percent, "message": message}


def _resources():
    return [{**r, "url": r.get("url") or url_for(r["endpoint"])} for r in RESOURCES]


def orientation_done(sid):
    p = progress_summary(sid)
    return bool(p["total"]) and p["percent"] == 100


@bp.route("/orientation")
@login_required
def index():
    sid = session["student_id"]
    # Once every step is complete, Orientation is retired and its resources move to their own page
    if orientation_done(sid):
        return redirect(url_for("orientation.resources_page"))
    rows = query_all(
        """SELECT t.*, p.status FROM orientation_tasks t
           JOIN orientation_progress p ON p.task_id = t.id AND p.student_id = ?
           ORDER BY t.position""",
        (sid,),
    )
    groups = {}
    for r in rows:
        url, external = _resolve(r["link_url"])
        groups.setdefault(r["category"], []).append({**dict(r), "url": url, "external": external})
    return render_template(
        "orientation.html", title="Orientation", groups=groups, statuses=STATUSES,
        progress=progress_summary(sid), resources=_resources(), directory=DIRECTORY,
    )


@bp.route("/resources")
@login_required
def resources_page():
    return render_template("resources.html", title="Resources", resources=_resources(), directory=DIRECTORY)


@bp.route("/api/orientation/<int:task_id>", methods=["POST"])
@login_required
def set_status(task_id):
    sid = session["student_id"]
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in STATUSES:
        abort(400, description="Choose Not started, In progress or Complete.")
    task = query_one(
        """SELECT t.title, t.requirement, p.status FROM orientation_tasks t
           JOIN orientation_progress p ON p.task_id = t.id AND p.student_id = ? WHERE t.id = ?""",
        (sid, task_id),
    )
    if task is None:
        abort(404, description="That task wasn't found.")
    if task["requirement"] == "Required":
        abort(403, description="Required steps are updated by CSU when you complete them.")
    db = get_db()
    db.execute(
        "UPDATE orientation_progress SET status = ?, updated_at = ? WHERE student_id = ? AND task_id = ?",
        (status, project_now().isoformat(timespec="minutes"), sid, task_id),
    )
    if status == "Complete" and task["status"] != "Complete":
        summary = progress_summary(sid)
        body = (f"{task['title']} is marked complete. You're {summary['percent']}% of the way through orientation."
                if summary["percent"] < 100 else "Every orientation step is complete. Welcome aboard, Viking!")
        link = "orientation.index" if summary["percent"] < 100 else "orientation.resources_page"
        add_alert(sid, "orientation", "Orientation task completed", body, "flag", link)
    db.commit()
    return jsonify(progress=progress_summary(sid), status=status)

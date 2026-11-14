"""Mobile Campus equipment lending.

Equipment types, policies, hours and contacts come from CSU's Mobile Campus page.
Inventory counts and requests are Viking Hub sample data: requests are saved here
and are not sent to Mobile Campus.
"""
from datetime import date, timedelta

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session

from alerts import add_alert, day_label, previewing, project_now, project_today, real_today
from db import get_db, query_all, query_one
from formatting import nice_date
from security import login_required

bp = Blueprint("mobile_campus", __name__)

INFO = {
    "where": "Student Center, Room 128A",
    "phone": "216-687-2180",
    "email": "mobilecampus@csuohio.edu",
    "url": "https://www.csuohio.edu/services-for-students/mobile-campus",
    "hours": [("Monday to Thursday", "8 AM to 8 PM"), ("Friday", "8 AM to 6 PM"),
              ("Saturday", "8 AM to 5 PM"), ("Sunday", "Closed")],
}
POLICIES = [
    "Loans are free for registered CSU students in good standing, first come, first served.",
    "Register once by completing the Mobile Campus Agreement in the ServiceNow portal.",
    "Most loans last the whole semester. A small number of devices are kept for 7 day loans.",
    "No new loans during academic breaks, and everything goes back at the end of the semester.",
    "Damaged or unreturned equipment can be charged to your student account, up to $2,000.",
    "Laptops are re-imaged when they come back, so save your work to OneDrive.",
    "If a device is lost or stolen, report it to CSU Police and tell Mobile Campus right away.",
]
SEMESTER_END = "2026-12-12"
CLOSED = {"2026-11-26", "2026-11-27", "2026-11-28"}  # Thanksgiving break


def pickup_days(week_only=False):
    """Pickup days are limited to the rest of the current week (through Friday), so devices
    aren't held for long for a student who might not come. On a Saturday, only that day."""
    d = real_today()
    if d.weekday() == 6:  # Sunday: closed, so the coming week
        d += timedelta(days=1)
    last = d if d.weekday() == 5 else d + timedelta(days=4 - d.weekday())
    out = []
    while d <= last:
        if d.isoformat() not in CLOSED:
            out.append(d.isoformat())
        d += timedelta(days=1)
    # Days before the one the app is showing have already gone by
    return [x for x in out if x >= project_today().isoformat()] if not week_only else out


def _equipment():
    return [dict(r) for r in query_all("SELECT * FROM equipment ORDER BY id")]


def _requests(sid):
    return [dict(r) for r in query_all(
        """SELECT r.*, e.name, e.kind FROM equipment_requests r JOIN equipment e ON e.id = r.equipment_id
           WHERE r.student_id = ? AND r.status != 'Canceled' ORDER BY r.pickup_date""", (sid,))]


def request_lock():
    """Requests follow the real week. Previewing a day outside it locks new requests."""
    days = pickup_days(week_only=True)
    if previewing() and not (days and project_today().isoformat() <= days[-1]):
        last = date.fromisoformat(days[-1]) if days else real_today()
        return (f"Equipment requests are only for this week, through {day_label(last)}. "
                f"You're previewing {day_label(project_today())}, so go back to November 12 to request a device.")
    return None


def _state(sid):
    return {"equipment": _equipment(), "requests": _requests(sid), "locked": request_lock()}


@bp.route("/mobile-campus")
@login_required
def index():
    sid = session["student_id"]
    return render_template(
        "mobile_campus.html", title="Mobile Campus", info=INFO, policies=POLICIES,
        state=_state(sid), days=pickup_days(), semester_end=SEMESTER_END,
    )


@bp.route("/api/mobile-campus/requests", methods=["POST"])
@login_required
def add_request():
    sid = session["student_id"]
    lock = request_lock()
    if lock:
        abort(409, description=lock)
    data = request.get_json(silent=True) or {}
    item = query_one("SELECT * FROM equipment WHERE id = ?", (data.get("equipment_id"),))
    if not item:
        abort(400, description="Choose a device to borrow.")
    loan = data.get("loan_type")
    if loan not in ("Semester", "7 day"):
        abort(400, description="Choose a loan length.")
    pickup = data.get("pickup_date")
    if pickup not in pickup_days():
        abort(400, description="Choose a pickup day when Mobile Campus is open.")
    if not data.get("agreement"):
        abort(400, description="Confirm you've completed the Mobile Campus Agreement.")
    if query_one("""SELECT 1 FROM equipment_requests r JOIN equipment e ON e.id = r.equipment_id
                    WHERE r.student_id = ? AND e.kind = ? AND r.status IN ('Requested', 'Checked out')""",
                 (sid, item["kind"])):
        abort(409, description=f"You already have a {item['kind'].lower()} on loan or requested.")
    pool = item["seven_day"] if loan == "7 day" else item["available"] - item["seven_day"]
    if pool <= 0:
        abort(409, description=f"No {item['name']} units are free for a {loan.lower()} loan right now.")
    due = (date.fromisoformat(pickup) + timedelta(days=7)).isoformat() if loan == "7 day" else SEMESTER_END
    db = get_db()
    db.execute(
        """INSERT INTO equipment_requests (student_id, equipment_id, loan_type, pickup_date, due_date, status, note, created_at)
           VALUES (?, ?, ?, ?, ?, 'Requested', ?, ?)""",
        (sid, item["id"], loan, pickup, due, (str(data.get("note") or "").strip()[:200] or None),
         project_now().isoformat(timespec="minutes")),
    )
    # "available" counts every free unit; "seven_day" is the part of it kept for 7 day loans
    db.execute("UPDATE equipment SET available = available - 1 WHERE id = ?", (item["id"],))
    if loan == "7 day":
        db.execute("UPDATE equipment SET seven_day = seven_day - 1 WHERE id = ?", (item["id"],))
    add_alert(sid, "campus", "Mobile Campus request saved",
              f"Pick up your {item['name']} in Student Center 128A on {nice_date(pickup, '%A, %B %d')}. Bring your Viking Card.",
              "laptop", "mobile_campus.index")
    db.commit()
    return jsonify(_state(sid))


@bp.route("/api/mobile-campus/requests/<int:req_id>/cancel", methods=["POST"])
@login_required
def cancel_request(req_id):
    sid = session["student_id"]
    r = query_one("SELECT * FROM equipment_requests WHERE id = ? AND student_id = ?", (req_id, sid))
    if not r:
        abort(404, description="That request wasn't found.")
    if r["status"] != "Requested":
        abort(409, description="Only requests that haven't been picked up can be canceled. Return checked out equipment to Mobile Campus.")
    db = get_db()
    db.execute("UPDATE equipment_requests SET status = 'Canceled' WHERE id = ?", (req_id,))
    db.execute("UPDATE equipment SET available = available + 1 WHERE id = ?", (r["equipment_id"],))
    if r["loan_type"] == "7 day":
        db.execute("UPDATE equipment SET seven_day = seven_day + 1 WHERE id = ?", (r["equipment_id"],))
    db.commit()
    return jsonify(_state(sid))

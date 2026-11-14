"""Lift Up Vikes food pantry.

Pantry details come from CSU's Lift Up Vikes pages. CSU runs the pantry as walk-in
shopping in 15-minute turns; Viking Hub lets a student plan a visit by reserving
one of those turns. Reservations are saved in Viking Hub only.
"""
import hashlib
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session

from alerts import day_label, project_now, project_today, real_today
from db import get_db, query_all, query_one
from security import login_required

bp = Blueprint("lift_up_vikes", __name__)

INFO = {
    "where": "Berkman Hall, Room 122",
    "resource_room": "Berkman Hall, Room 148",
    "phone": "216-687-5105",
    "email": "liftupvikes@csuohio.edu",
    "url": "https://csuohio.edu/liftupvikes/food-pantry",
}
# Fall 2026 hours: weekday -> (open, close)
HOURS = {1: ("13:00", "18:00"), 2: ("12:00", "17:00"), 3: ("13:00", "18:00"), 4: ("12:00", "17:00")}
HOURS_TEXT = [("Monday", "Closed"), ("Tuesday", "1 PM to 6 PM"), ("Wednesday", "12 PM to 5 PM"),
              ("Thursday", "1 PM to 6 PM"), ("Friday", "12 PM to 5 PM"), ("Saturday and Sunday", "Closed")]
HOW_IT_WORKS = [
    "Shopping is choice style: you pick what you need.",
    "Shoppers go in 15-minute turns, eight at a time. Please don't bring extra people.",
    "If the line is longer than 20 people, come back a little later.",
    "Bring reusable shopping bags.",
    "The pantry is for students who are experiencing food insecurity or need extra support.",
]
LINKS = [
    {"label": "Pantry FAQs", "url": "https://csuohio.edu/liftupvikes/faq", "icon": "info"},
    {"label": "Resource Center", "url": "https://csuohio.edu/liftupvikes/resource-center-information", "icon": "building"},
    {"label": "Fowler Emergency Fund", "url": "https://csuohio.edu/liftupvikes/fowler-emergency-fund", "icon": "card"},
    {"label": "Find food near you", "url": "https://www.greaterclevelandfoodbank.org/get-help/find-food", "icon": "map"},
]
CLOSED = {"2026-11-26", "2026-11-27"}  # Thanksgiving break
PER_TURN = 8
DAYS_AHEAD = 14
MAX_UPCOMING = 2


def _others(day, time):
    """How many other shoppers have each turn. Fixed per turn, so every launch looks the same."""
    h = int(hashlib.md5(f"{day} {time}".encode()).hexdigest(), 16)
    return h % 7 if h % 5 else PER_TURN  # some turns are already full


def _mine(sid):
    return [dict(r) for r in query_all(
        """SELECT * FROM pantry_appointments WHERE student_id = ? AND status = 'Booked'
           ORDER BY appt_date, appt_time""", (sid,))]


def availability(sid):
    now = project_now()
    start = project_today()
    booked = {(a["appt_date"], a["appt_time"]) for a in _mine(sid)}
    last = real_today() + timedelta(days=DAYS_AHEAD - 1)  # the booking window runs from the real today
    days = []
    for i in range(DAYS_AHEAD):
        d = start + timedelta(days=i)
        if d > last:
            break
        key = d.isoformat()
        if d.weekday() not in HOURS or key in CLOSED:
            continue
        open_t, close_t = HOURS[d.weekday()]
        t = datetime.combine(d, datetime.strptime(open_t, "%H:%M").time())
        end = datetime.combine(d, datetime.strptime(close_t, "%H:%M").time())
        slots = []
        while t < end:
            hm = t.strftime("%H:%M")
            if t > now:
                taken = _others(key, hm) + (1 if (key, hm) in booked else 0)
                slots.append({"time": hm, "left": max(0, PER_TURN - taken), "mine": (key, hm) in booked})
            t += timedelta(minutes=15)
        if slots:
            days.append({"date": key, "slots": slots})
    return days


def booking_lock():
    last = real_today() + timedelta(days=DAYS_AHEAD - 1)
    if project_today() > last:
        return (f"Visits can be planned up to two weeks ahead, through {day_label(last)}. "
                f"You're previewing {day_label(project_today())}, so go back to November 12 to plan a visit.")
    return None


def _state(sid):
    lock = booking_lock()
    return {"days": [] if lock else availability(sid), "appointments": _mine(sid), "locked": lock}


@bp.route("/lift-up-vikes")
@login_required
def index():
    sid = session["student_id"]
    return render_template(
        "lift_up_vikes.html", title="Lift Up Vikes", info=INFO, hours=HOURS_TEXT, how=HOW_IT_WORKS,
        links=LINKS, state=_state(sid), per_turn=PER_TURN,
    )


@bp.route("/api/lift-up-vikes/appointments", methods=["POST"])
@login_required
def book():
    sid = session["student_id"]
    lock = booking_lock()
    if lock:
        abort(409, description=lock)
    data = request.get_json(silent=True) or {}
    day, time = data.get("date"), data.get("time")
    slot = next((s for d in availability(sid) if d["date"] == day for s in d["slots"] if s["time"] == time), None)
    if not slot:
        abort(400, description="Choose an open time.")
    if slot["mine"]:
        abort(409, description="You already have that time.")
    if slot["left"] <= 0:
        abort(409, description="That turn just filled up. Choose another time.")
    mine = _mine(sid)
    if any(a["appt_date"] == day for a in mine):
        abort(409, description="You already have a visit planned that day.")
    if len(mine) >= MAX_UPCOMING:
        abort(409, description=f"You can plan up to {MAX_UPCOMING} visits at a time. Cancel one to choose another.")
    db = get_db()
    db.execute("INSERT INTO pantry_appointments (student_id, appt_date, appt_time, status, created_at) VALUES (?, ?, ?, 'Booked', ?)",
               (sid, day, time, project_now().isoformat(timespec="minutes")))
    db.commit()
    return jsonify(_state(sid))


@bp.route("/api/lift-up-vikes/appointments/<int:appt_id>/cancel", methods=["POST"])
@login_required
def cancel(appt_id):
    sid = session["student_id"]
    if not query_one("SELECT 1 FROM pantry_appointments WHERE id = ? AND student_id = ? AND status = 'Booked'", (appt_id, sid)):
        abort(404, description="That visit wasn't found.")
    db = get_db()
    db.execute("UPDATE pantry_appointments SET status = 'Canceled' WHERE id = ?", (appt_id,))
    db.commit()
    return jsonify(_state(sid))

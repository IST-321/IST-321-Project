"""Book a space: Michael Schwartz Library rooms and Rec Center group fitness.

Room reservations and class sign-ups are kept in Viking Hub to plan your week. They
don't reserve anything in the library's or the Rec Center's own systems.
"""
import hashlib
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, jsonify, render_template, request, session

from alerts import add_alert, day_label, project_now, project_today, real_today
from db import get_db, query_all, query_one
from security import login_required

bp = Blueprint("spaces", __name__)

WINDOW_DAYS = 7          # today and the next 6 days
MAX_ROOMS = 2            # upcoming room reservations at a time

LIBRARY = {
    "name": "Michael Schwartz Library",
    "where": "Rhodes Tower, 1860 East 22nd Street",
    "help_desk": "216-687-2479",
    "main": "216-687-2478",
    "hours_text": ["Monday to Thursday, 8 AM to 8 PM", "Friday, 8 AM to 5 PM", "Saturday, closed", "Sunday, 1 PM to 8 PM"],
    "hours_url": "https://library.csuohio.edu/information/hours.html",
    "rooms_url": "https://researchguides.csuohio.edu/inquirylaunchgame/libraryrooms",
}
LIB_HOURS = {0: ("08:00", "20:00"), 1: ("08:00", "20:00"), 2: ("08:00", "20:00"), 3: ("08:00", "20:00"),
             4: ("08:00", "17:00"), 6: ("13:00", "20:00")}  # Saturday closed

ROOMS = [
    {"id": "collab", "name": "Student Collaboration Room", "where": "Rhodes Tower 402", "lengths": [1, 2], "units": 1,
     "who": "Groups", "text": "A larger room for group projects, with space to spread out and work together."},
    {"id": "practice", "name": "Presentation Practice Room", "where": "Rhodes Tower 304", "lengths": [1], "units": 1,
     "who": "Groups or one person", "needs_course": True,
     "text": "Rehearse a class presentation. The library asks for the course and instructor, so we do too."},
    {"id": "video", "name": "Video conference room", "where": "Michael Schwartz Library", "lengths": [1], "units": 4,
     "who": "One person", "text": "A quiet room for Zoom or Teams calls, interviews and online meetings."},
]
ROOM_BY_ID = {r["id"]: r for r in ROOMS}
WALK_IN = [
    {"name": "Virginia McFrederick Group Study Center", "where": "Rhodes Tower 100A to 100E",
     "text": "First come, first served. Check out a key at the Library Help Desk with your Viking Card; at least 3 students in the group need to be there."},
    {"name": "Group project rooms (4)", "where": "Michael Schwartz Library",
     "text": "First come, first served for groups of at least 2."},
    {"name": "Fourth floor group study", "where": "Rhodes Tower, 4th floor",
     "text": "The whole floor is open seating for group study."},
]

REC = {
    "name": "Recreation Center",
    "where": "2420 Chester Avenue",
    "phone": "216-802-3200",
    "hours_text": ["Monday to Thursday, 5:20 AM to 10 PM", "Friday, 5:20 AM to 9 PM", "Saturday and Sunday, 9:10 AM to 5 PM"],
    "site": "https://www.csurec.com/",
    "fitness": "https://csurec.com/classes/group-fitness/",
}
REC_HOURS = {0: ("05:20", "22:00"), 1: ("05:20", "22:00"), 2: ("05:20", "22:00"), 3: ("05:20", "22:00"),
             4: ("05:20", "21:00"), 5: ("09:10", "17:00"), 6: ("09:10", "17:00")}
# How busy the Rec usually is, by hour (0 to 100). Weekdays peak after classes let out.
WEEKDAY_CROWD = {5: 22, 6: 38, 7: 46, 8: 34, 9: 28, 10: 30, 11: 44, 12: 56, 13: 46, 14: 44, 15: 60, 16: 80, 17: 92, 18: 86,
                 19: 70, 20: 48, 21: 28}
WEEKEND_CROWD = {9: 30, 10: 46, 11: 56, 12: 62, 13: 56, 14: 48, 15: 38, 16: 26}


def _hash(*parts):
    return int(hashlib.md5(" ".join(map(str, parts)).encode()).hexdigest(), 16)


def _fmt(hhmm):
    h, m = map(int, hhmm.split(":"))
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def _add_minutes(hhmm, minutes):
    t = datetime.strptime(hhmm, "%H:%M") + timedelta(minutes=minutes)
    return t.strftime("%H:%M")


def window():
    """Days that can be booked: from the day shown in the app to a week after the real today."""
    last = real_today() + timedelta(days=WINDOW_DAYS - 1)
    d = project_today()
    out = []
    while d <= last:
        out.append(d)
        d += timedelta(days=1)
    return out, last


def booking_lock():
    days, last = window()
    if not days:
        return (f"Spaces can be booked up to a week ahead, through {day_label(last)}. "
                f"You're previewing {day_label(project_today())}, so go back to November 12 to book.")
    return None


# ---------------------------------------------------------------------------
# Library rooms
# ---------------------------------------------------------------------------
def _mine(sid):
    rows = query_all("""SELECT * FROM room_bookings WHERE student_id = ? AND status = 'Reserved' AND book_date >= ?
                        ORDER BY book_date, start_time""", (sid, project_today().isoformat()))
    return [{**dict(r), "room_name": ROOM_BY_ID[r["room"]]["name"], "where": ROOM_BY_ID[r["room"]]["where"]} for r in rows]


def _taken(room, day, hour, sid):
    """How many of a room's units are already reserved at an hour: other students (fixed pattern) plus this student."""
    others = _hash(room["id"], day, hour) % (room["units"] + 2)
    others = min(room["units"], others if others <= room["units"] else 0)
    if hour in ("12:00", "13:00", "16:00") and room["units"] == 1:  # busy times of day
        others = 1 if _hash(room["id"], day, "busy") % 2 else others
    mine = query_one("""SELECT COUNT(*) AS n FROM room_bookings WHERE room = ? AND book_date = ? AND status = 'Reserved'
                        AND start_time <= ? AND end_time > ?""", (room["id"], day, hour, hour))["n"]
    return min(room["units"], others + mine)


def room_slots(sid):
    """For each room and day, the hours you could start a booking and how many units are free."""
    now = project_now()
    days, _ = window()
    out = {}
    for room in ROOMS:
        out[room["id"]] = []
        for d in days:
            hours = LIB_HOURS.get(d.weekday())
            if not hours:
                out[room["id"]].append({"date": d.isoformat(), "closed": True, "slots": []})
                continue
            open_h, close_h = int(hours[0][:2]), int(hours[1][:2])
            slots = []
            for h in range(open_h, close_h):
                hh = f"{h:02d}:00"
                if d == now.date() and h <= now.hour:
                    continue  # already started
                free = room["units"] - _taken(room, d.isoformat(), hh, sid)
                slots.append({"time": hh, "free": free})
            out[room["id"]].append({"date": d.isoformat(), "closed": False, "slots": slots})
    return out


def rooms_state(sid):
    lock = booking_lock()
    return {"slots": {} if lock else room_slots(sid), "mine": _mine(sid), "locked": lock}


# ---------------------------------------------------------------------------
# Rec Center
# ---------------------------------------------------------------------------
def crowd(day):
    d = date.fromisoformat(day)
    curve = WEEKEND_CROWD if d.weekday() >= 5 else WEEKDAY_CROWD
    open_t, close_t = REC_HOURS[d.weekday()]
    out = []
    for h in range(int(open_t[:2]), int(close_t[:2])):
        base = curve.get(h, 20)
        value = max(5, min(100, base + (_hash("rec", day, h) % 11) - 5))
        out.append({"hour": h, "value": value, "level": "Quiet" if value < 35 else "Moderate" if value < 65 else "Busy"})
    return out


def rec_state(sid):
    lock = booking_lock()
    days, _ = window()
    classes = query_all("SELECT * FROM rec_classes ORDER BY weekday, start_time")
    mine = {(r["class_id"], r["class_date"]): r["id"] for r in query_all(
        "SELECT * FROM rec_signups WHERE student_id = ?", (sid,))}
    now = project_now()
    sessions = []
    for d in days:
        for c in classes:
            if c["weekday"] != d.weekday():
                continue
            day = d.isoformat()
            end = _add_minutes(c["start_time"], c["minutes"])
            if d == now.date() and c["start_time"] <= now.strftime("%H:%M"):
                continue
            from routes.schedule import conflicts_for
            clashes = [x for x in conflicts_for(sid, day, c["start_time"], end) if not x["canceled"]
                       and not x["title"].startswith(c["name"])]
            sessions.append({"class_id": c["id"], "date": day, "start": c["start_time"], "end": end, "name": c["name"],
                             "room": c["room"], "minutes": c["minutes"], "description": c["description"],
                             "signup": mine.get((c["id"], day)), "conflicts": clashes})
    return {"days": [d.isoformat() for d in days], "sessions": sessions, "locked": lock,
            "crowd": {d.isoformat(): crowd(d.isoformat()) for d in days},
            "now": {"date": now.date().isoformat(), "hour": now.hour}}


@bp.route("/book-a-space")
@login_required
def index():
    sid = session["student_id"]
    tab = "rec" if request.args.get("tab") == "rec" else "library"
    return render_template("book_space.html", title="Book a space", tab=tab, rooms=ROOMS, walk_in=WALK_IN,
                           library=LIBRARY, rec=REC, rooms_state=rooms_state(sid), rec_state=rec_state(sid),
                           max_rooms=MAX_ROOMS)


@bp.route("/api/spaces/rooms", methods=["POST"])
@login_required
def book_room():
    sid = session["student_id"]
    lock = booking_lock()
    if lock:
        abort(409, description=lock)
    data = request.get_json(silent=True) or {}
    room = ROOM_BY_ID.get(data.get("room"))
    if room is None:
        abort(400, description="Choose a room.")
    day, start = data.get("date"), data.get("time")
    try:
        hours = int(data.get("hours", 1))
    except (TypeError, ValueError):
        hours = 0
    if hours not in room["lengths"]:
        abort(400, description="Choose how long you need the room.")
    slots = room_slots(sid)[room["id"]]
    today_slots = next((d for d in slots if d["date"] == day), None)
    if not today_slots or today_slots["closed"]:
        abort(400, description="Choose a day the library is open.")
    free = {s["time"]: s["free"] for s in today_slots["slots"]}
    needed = [f"{int(start[:2]) + i:02d}:00" for i in range(hours)] if start and start[:2].isdigit() else []
    if not needed or any(free.get(h, 0) <= 0 for h in needed):
        abort(409, description="That time isn't open anymore. Choose another.")
    details = None
    if room.get("needs_course"):
        course = " ".join(str(data.get("course", "")).split())[:40]
        instructor = " ".join(str(data.get("instructor", "")).split())[:60]
        if not course or not instructor:
            abort(400, description="Add the course and instructor for the presentation.")
        details = f"{course}, {instructor}"
    mine = _mine(sid)
    if len(mine) >= MAX_ROOMS:
        abort(409, description=f"You can hold up to {MAX_ROOMS} room reservations at a time. Cancel one to book another.")
    end = f"{int(start[:2]) + hours:02d}:00"
    from routes.schedule import conflicts_for
    clashes = [c for c in conflicts_for(sid, day, start, end) if not c["canceled"]]
    if clashes and not data.get("confirm"):
        return jsonify(needs_confirm=True, conflicts=clashes)
    unit = next(u for u in range(1, room["units"] + 1)
                if not query_one("""SELECT 1 FROM room_bookings WHERE room = ? AND unit = ? AND book_date = ? AND status = 'Reserved'
                                    AND start_time < ? AND end_time > ?""", (room["id"], u, day, end, start)))
    label = room["name"] + (f" {unit}" if room["units"] > 1 else "")
    db = get_db()
    note = "Reserved in Viking Hub. Bring your Viking Card to the Library Help Desk."
    ev = db.execute(
        """INSERT INTO events (student_id, kind, title, event_date, start_time, end_time, location, notes)
           VALUES (?, 'personal', ?, ?, ?, ?, ?, ?)""", (sid, label, day, start, end, room["where"], note))
    db.execute(
        """INSERT INTO room_bookings (student_id, room, unit, book_date, start_time, end_time, details, event_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (sid, room["id"], unit, day, start, end, details, ev.lastrowid, project_now().isoformat(timespec="minutes")))
    add_alert(sid, "campus", "Library room reserved",
              f"{label}, {day_label(date.fromisoformat(day))} from {_fmt(start)} to {_fmt(end)}. Bring your Viking Card to the Library Help Desk.",
              "calendar", "spaces.index")
    db.commit()
    return jsonify(state=rooms_state(sid), message=f"{label} reserved")


@bp.route("/api/spaces/rooms/<int:booking_id>/cancel", methods=["POST"])
@login_required
def cancel_room(booking_id):
    sid = session["student_id"]
    b = query_one("SELECT * FROM room_bookings WHERE id = ? AND student_id = ? AND status = 'Reserved'", (booking_id, sid))
    if b is None:
        abort(404, description="That reservation was already canceled.")
    db = get_db()
    db.execute("UPDATE room_bookings SET status = 'Canceled' WHERE id = ?", (booking_id,))
    if b["event_id"]:
        db.execute("DELETE FROM events WHERE id = ? AND student_id = ?", (b["event_id"], sid))
    db.commit()
    return jsonify(state=rooms_state(sid), message="Reservation canceled")


@bp.route("/api/spaces/rec", methods=["POST"])
@login_required
def add_rec():
    sid = session["student_id"]
    lock = booking_lock()
    if lock:
        abort(409, description=lock)
    data = request.get_json(silent=True) or {}
    session_ = next((s for s in rec_state(sid)["sessions"]
                     if s["class_id"] == data.get("class_id") and s["date"] == data.get("date")), None)
    if session_ is None:
        abort(400, description="Choose a class that hasn't started yet.")
    if session_["signup"]:
        abort(409, description="That class is already on your schedule.")
    if session_["conflicts"] and not data.get("confirm"):
        return jsonify(needs_confirm=True, conflicts=session_["conflicts"])
    db = get_db()
    ev = db.execute(
        """INSERT INTO events (student_id, kind, title, event_date, start_time, end_time, location, notes)
           VALUES (?, 'personal', ?, ?, ?, ?, ?, ?)""",
        (sid, f"{session_['name']} at the Rec", session_["date"], session_["start"], session_["end"],
         f"Recreation Center, {session_['room']}", "Free group fitness class. Bring your Viking Card."))
    db.execute("INSERT INTO rec_signups (student_id, class_id, class_date, event_id) VALUES (?, ?, ?, ?)",
               (sid, session_["class_id"], session_["date"], ev.lastrowid))
    db.commit()
    return jsonify(state=rec_state(sid), message=f"{session_['name']} added to your schedule")


@bp.route("/api/spaces/rec/<int:signup_id>", methods=["DELETE"])
@login_required
def remove_rec(signup_id):
    sid = session["student_id"]
    s = query_one("SELECT * FROM rec_signups WHERE id = ? AND student_id = ?", (signup_id, sid))
    if s is None:
        abort(404, description="That class was already removed.")
    db = get_db()
    if s["event_id"]:
        db.execute("DELETE FROM events WHERE id = ? AND student_id = ?", (s["event_id"], sid))
    db.execute("DELETE FROM rec_signups WHERE id = ?", (signup_id,))
    db.commit()
    return jsonify(state=rec_state(sid), message="Class removed from your schedule")

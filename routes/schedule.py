"""Schedule planner: classes, assignments, personal events and Blackboard calendar import.

The planner gives an overview of a student's week. It does not register for
classes; that stays in CampusNet.
"""
import re
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session

from alerts import project_today
from db import get_db, query_all, query_one
from security import login_required

bp = Blueprint("schedule", __name__)

TERM = {"name": "Fall 2026", "start": "2026-08-24", "end": "2026-12-12"}
DAY_LETTERS = "MTWRFSU"
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
# CSU's common hour: no classes meet Tuesdays and Thursdays from 11:30 AM to 12:30 PM,
# so clubs and campus events can. (CSU course scheduling grid)
COMMON_HOUR = {"days": "TR", "start": "11:30", "end": "12:30"}
LINKS = [
    {"label": "Blackboard", "text": "Course materials and coursework",
     "url": "https://www.csuohio.edu/center-for-elearning/blackboard-login", "icon": "laptop"},
    {"label": "Starfish", "text": "Advising appointments and your Success Network",
     "url": "https://www.csuohio.edu/successprograms/starfish-student", "icon": "calendar"},
    {"label": "CampusNet", "text": "Registration and official academic records",
     "url": "https://campusnet.csuohio.edu/", "icon": "book"},
]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def schedule_data(sid):
    from walking import walk_config
    return {
        "walk": walk_config(sid),
        "term": TERM,
        "common_hour": COMMON_HOUR,
        "today": project_today().isoformat(),
        "default_today": current_app.config["PROJECT_DATE"],
        "classes": [dict(r) for r in query_all("SELECT * FROM courses WHERE student_id = ? ORDER BY code", (sid,))],
        "cancellations": [dict(r) for r in query_all(
            """SELECT c.course_id, c.class_date FROM class_cancellations c
               JOIN courses k ON k.id = c.course_id WHERE k.student_id = ?""", (sid,))],
        "assignments": [dict(r) for r in query_all(
            "SELECT * FROM assignments WHERE student_id = ? ORDER BY due_date, due_time", (sid,))],
        # "booked" marks library rooms and Rec classes, which are changed from Book a space
        "events": [dict(r) for r in query_all(
            """SELECT e.*, (EXISTS (SELECT 1 FROM room_bookings b WHERE b.event_id = e.id AND b.status = 'Reserved')
                            OR EXISTS (SELECT 1 FROM rec_signups s WHERE s.event_id = e.id)) AS booked
               FROM events e WHERE e.student_id = ? ORDER BY e.event_date, e.start_time""", (sid,))],
    }


def _overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def conflicts_for(sid, day, start, end, ignore_source=None):
    """Classes and scheduled events that overlap a time on a given day (YYYY-MM-DD)."""
    d = date.fromisoformat(day)
    letter = DAY_LETTERS[d.weekday()]
    out = []
    if TERM["start"] <= day <= TERM["end"]:
        canceled = {r["course_id"] for r in query_all(
            """SELECT c.course_id FROM class_cancellations c JOIN courses k ON k.id = c.course_id
               WHERE k.student_id = ? AND c.class_date = ?""", (sid, day))}
        for c in query_all("SELECT * FROM courses WHERE student_id = ? AND delivery = 'In person'", (sid,)):
            if letter in (c["days"] or "") and _overlaps(start, end, c["start_time"], c["end_time"]):
                out.append({"kind": "class", "title": c["code"], "start": c["start_time"], "end": c["end_time"],
                            "location": c["location"], "canceled": c["id"] in canceled})
    for e in query_all(
            """SELECT * FROM events WHERE student_id = ? AND event_date = ? AND start_time IS NOT NULL
               AND (source_id IS NULL OR source_id != ?)""", (sid, day, ignore_source or -1)):
        if _overlaps(start, end, e["start_time"], e["end_time"] or e["start_time"]):
            out.append({"kind": "event", "title": e["title"], "start": e["start_time"], "end": e["end_time"],
                        "location": e["location"], "canceled": False})
    return out


def _bad(message):
    abort(400, description=message)


def _text(data, key, label, required=True, limit=120):
    value = " ".join(str(data.get(key) or "").split())
    if required and not value:
        _bad(f"Enter {label}.")
    if len(value) > limit:
        _bad(f"Keep {label} under {limit} characters.")
    return value or None


def _date(data, key, label="a date"):
    value = str(data.get(key) or "")
    try:
        date.fromisoformat(value)
    except ValueError:
        _bad(f"Choose {label}.")
    return value


def _time(data, key, label, required=True):
    value = str(data.get(key) or "")
    if not value and not required:
        return None
    if not TIME_RE.match(value):
        _bad(f"Choose {label}.")
    return value


def _owned(table, item_id, sid):
    row = query_one(f"SELECT * FROM {table} WHERE id = ? AND student_id = ?", (item_id, sid))
    if row is None:
        abort(404, description="That item wasn't found.")
    return row


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
@bp.route("/schedule")
@login_required
def index():
    return render_template("schedule.html", title="Schedule", data=schedule_data(session["student_id"]), links=LINKS,
                           export_parts=EXPORT_PARTS)


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------
def _class_fields(data):
    code = _text(data, "code", "a course code", limit=20).upper()
    if not re.match(r"^[A-Z]{2,4} ?\d{3}[A-Z]?$", code):
        _bad("Use a course code like ENG 102.")
    code = re.sub(r"^([A-Z]+)\s?(\d)", r"\1 \2", code)
    delivery = data.get("delivery")
    if delivery not in ("In person", "Online"):
        _bad("Choose in person or online.")
    professor = _text(data, "professor", "the professor's name", limit=60)
    if delivery == "Online":
        return code, delivery, None, None, None, None, professor
    days = "".join(d for d in DAY_LETTERS if d in str(data.get("days") or ""))
    if not days:
        _bad("Choose the days the class meets.")
    start = _time(data, "start_time", "a start time")
    end = _time(data, "end_time", "an end time")
    if end <= start:
        _bad("The class has to end after it starts.")
    if any(d in days for d in COMMON_HOUR["days"]) and _overlaps(start, end, COMMON_HOUR["start"], COMMON_HOUR["end"]):
        _bad("Classes don't meet during common hour, Tuesdays and Thursdays from 11:30 AM to 12:30 PM.")
    location = _text(data, "location", "a building and room", limit=80)
    return code, delivery, days, start, end, location, professor


@bp.route("/api/schedule/data")
@login_required
def data_api():
    return jsonify(data=schedule_data(session["student_id"]))


@bp.route("/api/schedule/classes", methods=["POST"])
@login_required
def add_class():
    sid = session["student_id"]
    fields = _class_fields(request.get_json(silent=True) or {})
    _unique_code(sid, fields[0])
    db = get_db()
    db.execute(
        """INSERT INTO courses (student_id, code, delivery, days, start_time, end_time, location, professor)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (sid, *fields))
    db.commit()
    return jsonify(data=schedule_data(sid), message=f"{fields[0]} added")


def _unique_code(sid, code, ignore_id=None):
    if query_one("SELECT 1 FROM courses WHERE student_id = ? AND lower(code) = lower(?) AND id != ?", (sid, code, ignore_id or -1)):
        _bad(f"{code} is already on your schedule.")


@bp.route("/api/schedule/classes/<int:item_id>", methods=["PUT", "DELETE"])
@login_required
def change_class(item_id):
    sid = session["student_id"]
    row = _owned("courses", item_id, sid)
    db = get_db()
    if request.method == "DELETE":
        db.execute("DELETE FROM courses WHERE id = ?", (item_id,))
        db.commit()
        return jsonify(data=schedule_data(sid), message=f"{row['code']} removed from your schedule")
    fields = _class_fields(request.get_json(silent=True) or {})
    _unique_code(sid, fields[0], item_id)
    db.execute(
        """UPDATE courses SET code = ?, delivery = ?, days = ?, start_time = ?, end_time = ?, location = ?, professor = ?
           WHERE id = ?""", (*fields, item_id))
    if fields[0] != row["code"]:
        # A renamed class keeps its assignments and grade tracker. Grade data left over from an
        # earlier class with the new code (no longer on the schedule) is cleared first.
        for r in query_all("SELECT id FROM grade_categories WHERE student_id = ? AND course_code = ?", (sid, fields[0])):
            db.execute("DELETE FROM grade_items WHERE category_id = ?", (r["id"],))
        db.execute("DELETE FROM grade_categories WHERE student_id = ? AND course_code = ?", (sid, fields[0]))
        db.execute("DELETE FROM grade_courses WHERE student_id = ? AND course_code = ?", (sid, fields[0]))
        for table in ("assignments", "grade_categories", "grade_courses"):
            db.execute(f"UPDATE {table} SET course_code = ? WHERE student_id = ? AND course_code = ?", (fields[0], sid, row["code"]))
    db.commit()
    return jsonify(data=schedule_data(sid), message=f"{fields[0]} updated")


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------
def _assignment_fields(data):
    course = _text(data, "course_code", "a course", limit=20)
    title = _text(data, "title", "an assignment title", limit=100)
    due_date = _date(data, "due_date", "a due date")
    due_time = _time(data, "due_time", "a due time")
    completed = 1 if data.get("completed") else 0
    return course, title, due_date, due_time, completed


@bp.route("/api/schedule/assignments", methods=["POST"])
@login_required
def add_assignment():
    sid = session["student_id"]
    fields = _assignment_fields(request.get_json(silent=True) or {})
    db = get_db()
    db.execute(
        "INSERT INTO assignments (student_id, course_code, title, due_date, due_time, completed) VALUES (?, ?, ?, ?, ?, ?)",
        (sid, *fields))
    db.commit()
    return jsonify(data=schedule_data(sid), message="Assignment added")


@bp.route("/api/schedule/assignments/<int:item_id>", methods=["PUT", "DELETE", "PATCH"])
@login_required
def change_assignment(item_id):
    sid = session["student_id"]
    row = _owned("assignments", item_id, sid)
    db = get_db()
    if request.method == "DELETE":
        db.execute("DELETE FROM assignments WHERE id = ?", (item_id,))
        msg = "Assignment deleted"
    elif request.method == "PATCH":  # toggle completion
        done = 0 if row["completed"] else 1
        db.execute("UPDATE assignments SET completed = ? WHERE id = ?", (done, item_id))
        msg = "Marked complete" if done else "Marked not complete"
    else:
        fields = _assignment_fields(request.get_json(silent=True) or {})
        db.execute(
            "UPDATE assignments SET course_code = ?, title = ?, due_date = ?, due_time = ?, completed = ? WHERE id = ?",
            (*fields, item_id))
        msg = "Assignment updated"
    db.commit()
    return jsonify(data=schedule_data(sid), message=msg)


# ---------------------------------------------------------------------------
# Personal events
# ---------------------------------------------------------------------------
def _event_fields(data):
    title = _text(data, "title", "an event name", limit=100)
    event_date = _date(data, "event_date", "a date")
    start = _time(data, "start_time", "a start time", required=False)
    end = _time(data, "end_time", "an end time", required=False)
    if start and end and end <= start:
        _bad("The event has to end after it starts.")
    if end and not start:
        _bad("Add a start time, or leave both times empty for an all-day event.")
    location = _text(data, "location", "a location", required=False, limit=80)
    notes = _text(data, "notes", "notes", required=False, limit=300)
    return title, event_date, start, end, location, notes


@bp.route("/api/schedule/events", methods=["POST"])
@login_required
def add_event():
    sid = session["student_id"]
    fields = _event_fields(request.get_json(silent=True) or {})
    db = get_db()
    db.execute(
        """INSERT INTO events (student_id, kind, title, event_date, start_time, end_time, location, notes)
           VALUES (?, 'personal', ?, ?, ?, ?, ?, ?)""", (sid, *fields))
    db.commit()
    return jsonify(data=schedule_data(sid), message="Event added")


@bp.route("/api/schedule/events/<int:item_id>", methods=["PUT", "DELETE"])
@login_required
def change_event(item_id):
    sid = session["student_id"]
    _owned("events", item_id, sid)
    db = get_db()
    booked = query_one("SELECT 1 FROM room_bookings WHERE event_id = ? AND status = 'Reserved'", (item_id,)) or \
        query_one("SELECT 1 FROM rec_signups WHERE event_id = ?", (item_id,))
    if request.method == "DELETE":
        # Removing a library room or Rec class from the schedule cancels it in Book a space too
        db.execute("UPDATE room_bookings SET status = 'Canceled', event_id = NULL WHERE event_id = ?", (item_id,))
        db.execute("DELETE FROM rec_signups WHERE event_id = ?", (item_id,))
        db.execute("DELETE FROM events WHERE id = ?", (item_id,))
        msg = "Reservation canceled and removed from your schedule" if booked else "Event removed from your schedule"
    elif booked:
        abort(409, description="Change library rooms and Rec classes from Book a space, so the time stays open for you.")
    else:
        fields = _event_fields(request.get_json(silent=True) or {})
        db.execute(
            "UPDATE events SET title = ?, event_date = ?, start_time = ?, end_time = ?, location = ?, notes = ? WHERE id = ?",
            (*fields, item_id))
        msg = "Event updated"
    db.commit()
    return jsonify(data=schedule_data(sid), message=msg)


# ---------------------------------------------------------------------------
# Blackboard calendar import (.ics), using only the standard library
# ---------------------------------------------------------------------------
def _eastern_offset(dt):
    """Hours behind UTC for Cleveland: EDT from the 2nd Sunday of March to the 1st Sunday of November."""
    def nth_sunday(year, month, n):
        d = date(year, month, 1)
        d += timedelta(days=(6 - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)
    start = datetime.combine(nth_sunday(dt.year, 3, 2), datetime.min.time()).replace(hour=7)
    end = datetime.combine(nth_sunday(dt.year, 11, 1), datetime.min.time()).replace(hour=6)
    return 4 if start <= dt < end else 5


def _parse_ics_datetime(value, params):
    value = value.strip()
    if "VALUE=DATE" in params or re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value[:8], "%Y%m%d"), True
    dt = datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        dt -= timedelta(hours=_eastern_offset(dt))
    return dt, False


def _ics_text(value):
    return value.replace("\\n", " ").replace("\\N", " ").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def parse_ics(text):
    # Unfold continued lines
    lines = re.sub(r"\r?\n[ \t]", "", text).splitlines()
    events, current = [], None
    for line in lines:
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            events.append(current)
            current = None
        elif current is not None and ":" in line:
            key, _, value = line.partition(":")
            name, _, params = key.partition(";")
            current[name.upper()] = (value, params.upper())
    parsed = []
    for ev in events:
        if "DTSTART" not in ev or "SUMMARY" not in ev:
            continue
        try:
            start, all_day = _parse_ics_datetime(*ev["DTSTART"])
            end = _parse_ics_datetime(*ev["DTEND"])[0] if "DTEND" in ev else None
        except ValueError:
            continue
        parsed.append({
            "title": _ics_text(ev["SUMMARY"][0])[:100] or "Blackboard item",
            "event_date": start.date().isoformat(),
            "start_time": None if all_day else start.strftime("%H:%M"),
            "end_time": None if all_day or not end or end.date() != start.date() or end <= start else end.strftime("%H:%M"),
            "location": _ics_text(ev["LOCATION"][0])[:80] if "LOCATION" in ev else None,
            "notes": _ics_text(ev["DESCRIPTION"][0])[:300] if "DESCRIPTION" in ev else None,
        })
    return parsed


@bp.route("/api/schedule/import", methods=["POST"])
@login_required
def import_calendar():
    sid = session["student_id"]
    upload = request.files.get("calendar")
    if not upload or not upload.filename:
        _bad("Choose a calendar file to import.")
    if not upload.filename.lower().endswith(".ics"):
        _bad("Choose a calendar file that ends in .ics.")
    raw = upload.read(2_000_000)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    if "BEGIN:VCALENDAR" not in text:
        _bad("That file isn't a calendar file. Export your calendar from Blackboard as an .ics file.")
    items = parse_ics(text)[:300]
    if not items:
        _bad("No calendar items were found in that file.")
    db = get_db()
    added = 0
    for it in items:
        exists = db.execute(
            "SELECT 1 FROM events WHERE student_id = ? AND kind = 'imported' AND title = ? AND event_date = ? AND IFNULL(start_time, '') = ?",
            (sid, it["title"], it["event_date"], it["start_time"] or ""),
        ).fetchone()
        if exists:
            continue
        db.execute(
            """INSERT INTO events (student_id, kind, title, event_date, start_time, end_time, location, notes)
               VALUES (?, 'imported', ?, ?, ?, ?, ?, ?)""",
            (sid, it["title"], it["event_date"], it["start_time"], it["end_time"], it["location"], it["notes"]),
        )
        added += 1
    db.commit()
    skipped = len(items) - added
    message = f"Imported {added} item{'s' if added != 1 else ''} from Blackboard"
    if skipped:
        message += f" ({skipped} already on your schedule)"
    return jsonify(data=schedule_data(sid), message=message)


# ---------------------------------------------------------------------------
# Export: the schedule as an .ics calendar file for Google Calendar, Outlook or Apple Calendar
# ---------------------------------------------------------------------------
EXPORT_PARTS = {"classes": "Classes", "assignments": "Assignment due dates", "personal": "Personal events",
                "campus": "Campus events", "imported": "Blackboard items"}
ICS_DAYS = {"M": "MO", "T": "TU", "W": "WE", "R": "TH", "F": "FR", "S": "SA", "U": "SU"}


def _ics_text(value):
    """Escape text for an .ics field."""
    return (value or "").replace("\\", "\\\\").replace(";", "\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_stamp(day, hhmm):
    return day.replace("-", "") + "T" + hhmm.replace(":", "") + "00"


def _fold(line):
    """Calendar files keep lines to 75 characters; longer ones continue on the next line after a space."""
    out = []
    while len(line) > 74:
        out.append(line[:74])
        line = " " + line[74:]
    out.append(line)
    return "\r\n".join(out)


def build_ics(sid, parts):
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CSU Viking Hub//Schedule//EN", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:Viking Hub schedule", "X-WR-TIMEZONE:America/New_York"]

    def event(uid, title, start, end=None, location=None, description=None, extra=()):
        lines.extend(["BEGIN:VEVENT", f"UID:{uid}@vikinghub", f"DTSTAMP:{now}",
                      f"SUMMARY:{_ics_text(title)}"])
        lines.extend(start)
        if end:
            lines.extend(end)
        if location:
            lines.append(f"LOCATION:{_ics_text(location)}")
        if description:
            lines.append(f"DESCRIPTION:{_ics_text(description)}")
        lines.extend(extra)
        lines.append("END:VEVENT")

    if "classes" in parts:
        until = TERM["end"].replace("-", "") + "T235900"
        for c in query_all("SELECT * FROM courses WHERE student_id = ? AND delivery = 'In person' AND days IS NOT NULL", (sid,)):
            # First meeting on or after the first day of the term
            first = date.fromisoformat(TERM["start"])
            while DAY_LETTERS[first.weekday()] not in c["days"]:
                first += timedelta(days=1)
            skipped = [r["class_date"] for r in query_all(
                "SELECT class_date FROM class_cancellations WHERE course_id = ? ORDER BY class_date", (c["id"],))]
            extra = [f"RRULE:FREQ=WEEKLY;BYDAY={','.join(ICS_DAYS[d] for d in c['days'])};UNTIL={until}"]
            extra += [f"EXDATE:{_ics_stamp(d, c['start_time'])}" for d in skipped]
            event(f"class-{c['id']}", c["code"], [f"DTSTART:{_ics_stamp(first.isoformat(), c['start_time'])}"],
                  [f"DTEND:{_ics_stamp(first.isoformat(), c['end_time'])}"], c["location"],
                  f"{c['professor']}. Class times from Viking Hub; CampusNet has your official schedule.", extra)

    if "assignments" in parts:
        for a in query_all("SELECT * FROM assignments WHERE student_id = ?", (sid,)):
            due = _ics_stamp(a["due_date"], a["due_time"])
            event(f"assignment-{a['id']}", f"Due: {a['course_code']} {a['title']}", [f"DTSTART:{due}"], [f"DTEND:{due}"],
                  None, "Complete" if a["completed"] else "Not complete yet")

    kinds = [k for k in ("personal", "campus", "imported") if k in parts]
    if kinds:
        marks = ",".join("?" * len(kinds))
        for e in query_all(f"SELECT * FROM events WHERE student_id = ? AND kind IN ({marks})", (sid, *kinds)):
            if e["start_time"]:
                start = [f"DTSTART:{_ics_stamp(e['event_date'], e['start_time'])}"]
                end = [f"DTEND:{_ics_stamp(e['event_date'], e['end_time'] or e['start_time'])}"]
            else:  # all day
                day = date.fromisoformat(e["event_date"])
                start = [f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}"]
                end = [f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}"]
            event(f"event-{e['id']}", e["title"], start, end, e["location"], e["notes"])

    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"


@bp.route("/schedule/export.ics")
@login_required
def export_ics():
    parts = [p for p in request.args.getlist("part") if p in EXPORT_PARTS]
    if not parts:
        abort(400, description="Choose at least one thing to export.")
    body = build_ics(session["student_id"], parts)
    return current_app.response_class(body, mimetype="text/calendar", headers={
        "Content-Disposition": "attachment; filename=viking-hub-schedule.ics"})

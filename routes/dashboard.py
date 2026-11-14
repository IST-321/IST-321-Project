"""Home dashboard and the alerts API."""
from datetime import date

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session

from alerts import active_alerts, add_alert, project_now, serialize, project_today
from db import get_db, query_all, query_one
from security import login_required
from walking import building_for, plan_day

bp = Blueprint("dashboard", __name__)

DAY_LETTERS = "MTWRFSU"  # Monday..Sunday, R = Thursday


def _fmt_time(hhmm):
    h, m = map(int, hhmm.split(":"))
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


KIND_LABEL = {"personal": "Personal", "campus": "Campus event", "imported": "Blackboard"}


def todays_plan(student_id):
    """Everything on today's schedule in time order: classes, events, due assignments and common hour.

    Items with a campus location get a walk line from wherever the student was before.
    """
    now = project_now()
    today = now.date()
    key, hhmm = today.isoformat(), now.strftime("%H:%M")
    letter = DAY_LETTERS[today.weekday()]
    items = []

    canceled = {r["course_id"] for r in query_all(
        "SELECT course_id FROM class_cancellations WHERE class_date = ?", (key,))}
    for r in query_all("SELECT * FROM courses WHERE student_id = ? AND delivery = 'In person'", (student_id,)):
        if r["days"] and letter in r["days"]:
            items.append({"kind": "class", "title": r["code"], "start_time": r["start_time"], "end_time": r["end_time"],
                          "location": r["location"], "detail": r["professor"], "canceled": r["id"] in canceled})
    for e in query_all("SELECT * FROM events WHERE student_id = ? AND event_date = ? ORDER BY start_time", (student_id, key)):
        items.append({"kind": e["kind"], "title": e["title"], "start_time": e["start_time"], "end_time": e["end_time"],
                      "location": e["location"], "detail": KIND_LABEL[e["kind"]], "canceled": False})
    for a in query_all("SELECT * FROM assignments WHERE student_id = ? AND due_date = ? AND completed = 0",
                       (student_id, key)):
        items.append({"kind": "assignment", "title": f"{a['course_code']}: {a['title']}", "start_time": a["due_time"],
                      "end_time": None, "location": None, "detail": "Due", "canceled": False})
    from routes.schedule import COMMON_HOUR
    # Common hour shows as free time only when nothing else is planned in it
    busy = any(i["start_time"] and i["kind"] not in ("assignment", "class")
               and i["start_time"] < COMMON_HOUR["end"] and (i["end_time"] or i["start_time"]) > COMMON_HOUR["start"]
               for i in items)
    if letter in COMMON_HOUR["days"] and not busy:
        items.append({"kind": "common", "title": "Common hour", "start_time": COMMON_HOUR["start"],
                      "end_time": COMMON_HOUR["end"], "location": None,
                      "detail": "No classes meet. A good time for clubs and campus events.", "canceled": False})

    timed = sorted([i for i in items if i["start_time"]], key=lambda i: i["start_time"])
    all_day = [i for i in items if not i["start_time"]]
    # Walks only between places the student actually goes
    plan_day(student_id, [i for i in timed if not i["canceled"] and i["kind"] not in ("assignment", "common")])
    for i in timed + all_day:
        i.setdefault("walk", None)
        if i["walk"]:
            i["walk"]["leave_by_label"] = _fmt_time(i["walk"]["leave_by"])
        i["start"] = _fmt_time(i["start_time"]) if i["start_time"] else "All day"
        i["end"] = _fmt_time(i["end_time"]) if i["end_time"] else ""
        i["past"] = bool(i["start_time"]) and (i["end_time"] or i["start_time"]) < hhmm
    online = query_all(
        "SELECT * FROM courses WHERE student_id = ? AND delivery = 'Online' ORDER BY code", (student_id,))
    return all_day + timed, online


def orientation_complete(student_id):
    """True once every orientation task is done. The checklist is added in phase 3."""
    has_table = query_one(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'orientation_progress'"
    )
    if not has_table:
        return False
    row = query_one(
        "SELECT COUNT(*) AS total, SUM(status = 'Complete') AS done FROM orientation_progress WHERE student_id = ?",
        (student_id,),
    )
    return bool(row["total"]) and row["done"] == row["total"]


def _event_label(day, start):
    today = project_today()
    d = date.fromisoformat(day)
    gap = (d - today).days
    when = "Today" if gap == 0 else "Tomorrow" if gap == 1 else d.strftime("%a, %b ") + str(d.day)
    return f"{when}, {_fmt_time(start)}" if start else when


def next_event(student_id):
    """The next campus event the student added; if none, the next common hour event to try."""
    today = project_now().date().isoformat()
    row = query_one(
        """SELECT title, event_date, start_time, location FROM events
           WHERE student_id = ? AND kind = 'campus' AND source_id IS NOT NULL
             AND event_date > ?
           ORDER BY event_date, start_time LIMIT 1""", (student_id, today))
    suggested = False
    if row is None:
        from routes.schedule import COMMON_HOUR
        rows = query_all(
            """SELECT title, event_date, start_time, location FROM campus_events
               WHERE event_date > ? AND start_time >= ? AND start_time < ?
                 AND id NOT IN (SELECT source_id FROM events WHERE student_id = ? AND source_id IS NOT NULL)
               ORDER BY event_date, start_time""",
            (today, COMMON_HOUR["start"], COMMON_HOUR["end"], student_id))
        row = next((r for r in rows if "MTWRFSU"[date.fromisoformat(r["event_date"]).weekday()] in COMMON_HOUR["days"]), None)
        suggested = row is not None
    if row is None:
        return None
    return {"title": row["title"], "when": _event_label(row["event_date"], row["start_time"]),
            "location": row["location"], "code": building_for(row["location"]), "suggested": suggested}


@bp.route("/home")
@login_required
def index():
    sid = session["student_id"]
    plan, online = todays_plan(sid)
    card = query_one("SELECT * FROM viking_cards WHERE student_id = ?", (sid,))
    meal = query_one("SELECT * FROM meal_plans WHERE student_id = ?", (sid,))
    announcements = query_all("SELECT * FROM announcements ORDER BY posted_on DESC")
    from routes.orientation import progress_summary
    orientation = progress_summary(sid)
    show_orientation = orientation["total"] and orientation["percent"] < 100
    return render_template(
        "dashboard.html",
        just_signed_in=session.pop("just_signed_in", False),
        today=project_now(),
        plan=plan,
        next_event=next_event(sid),
        online=online,
        card=card,
        meal=meal,
        announcements=announcements,
        show_orientation=show_orientation,
        orientation=orientation,
    )


@bp.route("/alerts")
@login_required
def alerts_page():
    return render_template("alerts.html", title="Alerts")


@bp.route("/announcements")
@login_required
def announcements_page():
    announcements = query_all("SELECT * FROM announcements ORDER BY posted_on DESC")
    categories = sorted({a["category"] for a in announcements})
    return render_template("announcements.html", title="Announcements", announcements=announcements, categories=categories)


# ---------- Live moments: an alert that arrives a few seconds after a page opens ----------

def moment_for(student_id, endpoint):
    """The waiting moment for this page, if any. None while previewing another day."""
    from alerts import previewing
    if previewing():
        return None
    row = query_one("SELECT id, delay_seconds FROM pending_updates WHERE student_id = ? AND page = ? AND delivered = 0 ORDER BY id LIMIT 1",
                    (student_id, endpoint))
    return {"id": row["id"], "delay": row["delay_seconds"]} if row else None


def _apply_effect(sid, effect):
    """Change the data that goes with a moment. Returns extra details for the page, or False to skip the alert."""
    db = get_db()
    if effect == "advising":
        db.execute("""INSERT INTO events (student_id, kind, title, event_date, start_time, end_time, location, notes)
                      VALUES (?, 'personal', 'Advising appointment', '2026-11-17', '11:00', '11:30', 'Berkman Hall',
                              'Meet with your academic advisor about spring classes.')""", (sid,))
        return {}
    if effect == "cancel_mth":
        course = query_one("SELECT id FROM courses WHERE student_id = ? AND code = 'MTH 116'", (sid,))
        if course is None:
            return False  # the class was removed, so there's nothing to cancel
        from alerts import real_today
        db.execute("INSERT OR IGNORE INTO class_cancellations (course_id, class_date) VALUES (?, ?)",
                   (course["id"], real_today().isoformat()))
        return {"schedule_changed": True}
    if effect == "deposit":
        from routes.viking_card import _check_low, _txn_json, insights
        from formatting import money
        from alerts import real_now
        card = query_one("SELECT * FROM viking_cards WHERE student_id = ?", (sid,))
        balance = card["balance_cents"] + 2500
        cur = db.execute("""INSERT INTO card_transactions (student_id, occurred_at, location, txn_type, amount_cents, balance_after_cents)
                            VALUES (?, ?, 'Online card office deposit', 'Deposit', 2500, ?)""", (sid, real_now(), balance))
        db.execute("UPDATE viking_cards SET balance_cents = ? WHERE student_id = ?", (balance, sid))
        _check_low(sid, balance)
        txn = query_one("SELECT * FROM card_transactions WHERE id = ?", (cur.lastrowid,))
        return {"card": {"balance_label": money(balance), "transaction": _txn_json(txn), "insights": insights(sid)}}
    return {}


@bp.route("/api/moments/<int:moment_id>", methods=["POST"])
@login_required
def deliver_moment(moment_id):
    from alerts import previewing
    sid = session["student_id"]
    row = query_one("SELECT * FROM pending_updates WHERE id = ? AND student_id = ? AND delivered = 0", (moment_id, sid))
    if row is None or previewing():
        return jsonify(alert=None)
    db = get_db()
    db.execute("UPDATE pending_updates SET delivered = 1 WHERE id = ?", (moment_id,))
    extra = _apply_effect(sid, row["effect"])
    if extra is False:
        db.commit()
        return jsonify(alert=None)
    from routes.settings import get_settings
    if row["category"] in get_settings(sid)["alerts_off"]:  # that kind of alert is turned off; the change still happens
        db.commit()
        return jsonify(alert=None, **extra)
    add_alert(sid, row["category"], row["title"], row["body"], row["icon"], row["link"])
    db.commit()
    newest = query_one("SELECT * FROM alerts WHERE student_id = ? ORDER BY id DESC LIMIT 1", (sid,))
    return jsonify(alert=serialize(newest), **extra)


# ---------- Alerts API ----------

@bp.route("/api/alerts")
@login_required
def list_alerts():
    return jsonify(alerts=active_alerts(session["student_id"]))


@bp.route("/api/alerts/seen", methods=["POST"])
@login_required
def mark_alerts_seen():
    """Called when the student closes the alerts list: new alerts stop being highlighted."""
    db = get_db()
    db.execute("UPDATE alerts SET seen_at = datetime('now') WHERE student_id = ? AND seen_at IS NULL AND cleared_at IS NULL",
               (session["student_id"],))
    db.commit()
    return jsonify(alerts=active_alerts(session["student_id"]))


@bp.route("/api/alerts/<int:alert_id>/clear", methods=["POST"])
@login_required
def clear_alert(alert_id):
    db = get_db()
    cur = db.execute(
        "UPDATE alerts SET cleared_at = datetime('now') WHERE id = ? AND student_id = ? AND cleared_at IS NULL",
        (alert_id, session["student_id"]),
    )
    if cur.rowcount == 0:
        abort(404, description="That alert was already cleared.")
    db.commit()
    return jsonify(alerts=active_alerts(session["student_id"]))


@bp.route("/api/alerts/clear-all", methods=["POST"])
@login_required
def clear_all_alerts():
    db = get_db()
    db.execute(
        "UPDATE alerts SET cleared_at = datetime('now') WHERE student_id = ? AND cleared_at IS NULL",
        (session["student_id"],),
    )
    db.commit()
    return jsonify(alerts=[])


@bp.route("/api/app-date", methods=["POST"])
@login_required
def set_app_date():
    """Move the day the whole app treats as today, to preview another day. Empty goes back to November 12."""
    from routes.schedule import TERM
    sid = session["student_id"]
    raw = (request.get_json(silent=True) or {}).get("date") or None
    default = current_app.config["PROJECT_DATE"]
    if raw:
        try:
            day = date.fromisoformat(raw)
        except ValueError:
            abort(400, description="Choose a date.")
        if not default <= day.isoformat() <= TERM["end"]:
            abort(400, description="Choose a day between November 12 and December 12.")
        raw = None if day.isoformat() == default else day.isoformat()
    db = get_db()
    db.execute("UPDATE students SET app_date = ? WHERE student_id = ?", (raw, sid))
    db.commit()
    shown = date.fromisoformat(raw or default)
    return jsonify(date=shown.isoformat(), message=f"Showing {shown.strftime('%A, %B')} {shown.day}")

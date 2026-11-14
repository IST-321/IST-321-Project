"""Alert helpers shared by the dashboard and other sections."""
from datetime import date, datetime, timedelta

from flask import current_app, g, has_request_context, session, url_for

from db import get_db, query_all, query_one


def project_today():
    """The app's today: November 12, 2026, unless the student moved the app date.

    The moved date is saved with the student, so it lasts through sign out and
    goes back to November 12 when the app restarts.
    """
    if has_request_context() and session.get("student_id"):
        if "app_date" not in g:
            row = query_one("SELECT app_date FROM students WHERE student_id = ?", (session["student_id"],))
            g.app_date = row["app_date"] if row else None
        if g.app_date:
            return date.fromisoformat(g.app_date)
    return date.fromisoformat(current_app.config["PROJECT_DATE"])


def real_today():
    """The app's actual today, November 12, 2026, whatever day the student is previewing."""
    return date.fromisoformat(current_app.config["PROJECT_DATE"])


def previewing():
    """True when the student moved the app to another day to look ahead."""
    return project_today() != real_today()


def day_label(d):
    return f"{d.strftime('%A, %B')} {d.day}"


_LAUNCHED = datetime.now()


def clock():
    """The time of day. Starts at PRESENT_TIME when the app launches and runs on from there,
    or follows the computer's clock when PRESENT_TIME is None."""
    start = current_app.config.get("PRESENT_TIME")
    if not start:
        return datetime.now()
    h, m = map(int, start.split(":"))
    elapsed = datetime.now() - _LAUNCHED
    return datetime.combine(date.today(), datetime.min.time()).replace(hour=h, minute=m) + elapsed


def real_now():
    """Now on the real day (November 12), for things that happen right away, like a new alert,
    even while the student previews another day."""
    now = clock()
    d = real_today()
    return datetime(d.year, d.month, d.day, now.hour, now.minute).isoformat(timespec="minutes")


def project_now():
    """The current time of day on the app's date."""
    today = project_today()
    now = clock()
    return datetime(today.year, today.month, today.day, now.hour, now.minute)


def when_label(iso):
    """'Today, 7:30 AM', 'Yesterday', or 'Nov 9' relative to the project date."""
    dt = datetime.fromisoformat(iso)
    today = project_now().date()
    hour = dt.hour % 12 or 12
    time = f"{hour}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"
    if dt.date() == today:
        return f"Today, {time}"
    if dt.date() == today - timedelta(days=1):
        return f"Yesterday, {time}"
    return f"{dt.strftime('%b')} {dt.day}"


def _url(link):
    endpoint, _, anchor = link.partition("#")
    return url_for(endpoint) + (f"#{anchor}" if anchor else "")


CATEGORY_LABELS = {
    "card": "Viking Card", "schedule": "Schedule", "deadline": "Deadlines", "orientation": "Orientation",
    "campus": "Campus", "transportation": "Getting around",
}


def serialize(row):
    return {
        "new": row["seen_at"] is None,
        "label": CATEGORY_LABELS.get(row["category"], "Campus"),
        "id": row["id"],
        "category": row["category"],
        "title": row["title"],
        "body": row["body"],
        "icon": row["icon"],
        "url": _url(row["link"]),
        "when": when_label(row["created_at"]),
        "actions": [a for a in (row["actions"] or "").split(",") if a],
    }


def active_alerts(student_id):
    rows = query_all(
        "SELECT * FROM alerts WHERE student_id = ? AND cleared_at IS NULL ORDER BY created_at DESC, id DESC",
        (student_id,),
    )
    return [serialize(r) for r in rows]


def add_alert(student_id, category, title, body, icon, link, actions=None):
    """Record a new alert, unless the student turned that kind of alert off in Settings. The caller commits."""
    from routes.settings import get_settings
    if category in get_settings(student_id)["alerts_off"]:
        return
    get_db().execute(
        "INSERT INTO alerts (student_id, category, title, body, icon, link, actions, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (student_id, category, title, body, icon, link, ",".join(actions or []) or None, real_now()),
    )

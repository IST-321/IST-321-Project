"""Search everything: one index of pages, places, offices, clubs, events, classes and alerts.

The page fetches the index once, then matches as the student types, so results show instantly.
"""
from datetime import date

from flask import Blueprint, jsonify, session, url_for

from alerts import active_alerts, project_today
from db import query_all
from security import login_required

bp = Blueprint("search", __name__)

# Extra words students might type for a page
PAGE_WORDS = {
    "viking_card.index": "balance money funds tap pay meal plan swipes dining dollars lock",
    "schedule.index": "calendar planner classes deadlines assignments export ics blackboard",
    "grades.index": "grade gpa scores syllabus what do i need",
    "campus_map.index": "map buildings directions innerlink",
    "events.index": "clubs organizations vikesconnect activities",
    "mobile_campus.index": "laptop macbook calculator borrow loan device",
    "lift_up_vikes.index": "food pantry groceries",
    "transportation.parking": "garage permit lot cars",
    "transportation.trip": "rta bus train transit scooter bike zipcar",
    "transportation.escorts": "safety walk police escort",
    "transportation.reports": "report problem issue lighting broken",
    "orientation.index": "checklist new student viking voyage",
    "orientation.resources_page": "resources directory offices first semester",
    "spaces.index": "library study room reserve rec center gym fitness yoga cycling zumba workout",
    "settings.index": "preferences text size sounds motion alerts notifications",
}


def _day(iso):
    d = date.fromisoformat(iso)
    return f"{d.strftime('%a, %b')} {d.day}"


def _time(hhmm):
    h, m = map(int, hhmm.split(":"))
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def build_index(sid):
    from navigation import GETTING_AROUND, RESOURCES_LINK, SERVICES
    from routes.campus_map import ALIASES, BUILDINGS
    from routes.events import CLUBS
    from routes.orientation import DIRECTORY
    from routes.transportation import ESCORT_POINTS

    out = []

    def add(group, title, sub, url, keys=""):
        out.append({"group": group, "title": title, "sub": sub, "url": url, "keys": keys})

    pages = ([{"endpoint": "dashboard.index", "label": "Home", "blurb": "Today's schedule, card and alerts"},
              {"endpoint": "dashboard.alerts_page", "label": "Alerts", "blurb": "Everything Viking Hub told you"},
              {"endpoint": "dashboard.announcements_page", "label": "Announcements", "blurb": "Campus news"},
              {"endpoint": "grades.index", "label": "Grades", "blurb": "Running grades and what you need"},
              {"endpoint": "settings.index", "label": "Settings", "blurb": "Text size, alerts, sounds and motion"}]
             + SERVICES + [RESOURCES_LINK]
             + [{**g, "blurb": "Getting around"} for g in GETTING_AROUND])
    for p in pages:
        add("Pages", p["label"], p.get("blurb", ""), url_for(p["endpoint"]), PAGE_WORDS.get(p["endpoint"], ""))

    for code, (name, category, address, inside) in BUILDINGS.items():
        add("Buildings", name, f"{code} · {address}", url_for("campus_map.index", b=code),
            " ".join([code] + ALIASES.get(code, []) + [inside, category]))

    for _section, offices in DIRECTORY:
        for o in offices:
            add("Offices and resources", o["name"], o.get("where", ""), url_for("orientation.resources_page"), o.get("text", ""))
    for p in ESCORT_POINTS:
        add("Offices and resources", f"Escort pickup: {p['point']}", p["name"], url_for("transportation.escorts"),
            " ".join([p["code"]] + p["aliases"]))

    for c in CLUBS:
        add("Clubs", c["name"], c["short"], url_for("events.index") + f"#club-{c['slug']}", c.get("category", ""))

    today = project_today().isoformat()
    for e in query_all("SELECT * FROM campus_events WHERE event_date >= ? ORDER BY event_date, start_time", (today,)):
        add("Campus events", e["title"], f"{_day(e['event_date'])}, {_time(e['start_time'])} · {e['location']}",
            url_for("events.index") + f"#event-{e['id']}", f"{e['host']} {e['category']}")

    for c in query_all("SELECT * FROM courses WHERE student_id = ? ORDER BY code", (sid,)):
        where = "Online" if c["delivery"] == "Online" else c["location"]
        add("Your classes and assignments", c["code"], f"{where} · {c['professor']}", url_for("schedule.index"), "class course")
    for a in query_all("SELECT * FROM assignments WHERE student_id = ? AND completed = 0 ORDER BY due_date", (sid,)):
        add("Your classes and assignments", f"{a['course_code']}: {a['title']}", f"Due {_day(a['due_date'])} at {_time(a['due_time'])}",
            url_for("schedule.index"), "assignment due homework")

    for a in active_alerts(sid):
        add("Alerts", a["title"], a["body"], a["url"], a["label"])
    return out


@bp.route("/api/search-index")
@login_required
def index():
    return jsonify(build_index(session["student_id"]))

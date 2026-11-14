"""Transportation and parking.

Parking rules, permit prices and the access table come from CSU Parking Services
(the commuter parking page, the green permit map and the permit and visitor access
restrictions table, updated 10/3/2024). Space counts are Viking Hub estimates:
CSU does not publish a live availability feed, so the numbers are sample data
that can be refreshed in the app.
"""
import random

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for

from alerts import project_now, previewing
from db import get_db, query_all
from security import login_required

bp = Blueprint("transportation", __name__)

PARKING_OFFICE = {
    "where": "Berkman Hall, Room 115, 1899 East 22nd Street",
    "phone": "216-687-2023",
    "email": "parking@csuohio.edu",
    "hours": "Monday to Friday, 9 AM to 4 PM",
    "buy_url": "https://csuparking.t2hosted.com/cmn/auth_ext.aspx",
    "page_url": "https://www.csuohio.edu/parking/commuter-student-parking-information-including-edgelangston-residents",
    "maps_url": "https://www.csuohio.edu/parking/parking-maps",
    "rules_url": "https://www.csuohio.edu/parking/parking-rules-effective-fy22",
    "green_map": "https://www.csuohio.edu/sites/default/files/2024/10/22/parking-maps-green.jpg",
    "white_map": "https://www.csuohio.edu/sites/default/files/2024-10/240033-parking-map-update_fall-2024-white_fa-digital.pdf",
    "visitor_map": "https://www.csuohio.edu/sites/default/files/2024/10/22/parking-maps-4.jpg",
}

# Fall 2026 (Aug 12 to Dec 31, 2026) and spring 2027 (Jan 1 to May 14, 2027) prices, per semester
PERMITS = [
    {"name": "Green", "price": "$278", "hours": "5 AM to 11:59 PM",
     "text": "All core garages, a few core surface lots and the South Garage. Also valid in white lots on weeknights after 5:30 PM and all day on weekends."},
    {"name": "White", "price": "$192", "hours": "5 AM to 11:59 PM",
     "text": "Non-core surface lots and the South Garage. The best daily value if you park on campus two or more times a week."},
    {"name": "Evening", "price": "$191", "hours": "3:30 PM to 11:59 PM",
     "text": "Most green and white locations during evening hours. Fall and spring only; not valid in the South or Prospect garages."},
    {"name": "Night", "price": "$174", "hours": "5:30 PM to 11:59 PM",
     "text": "Most green and white locations at night. Fall and spring only; not valid in the South or Prospect garages."},
]
OVERNIGHT = {"price": "$200", "text": "An add-on to a base permit, valid 24/7 in your permit's zone. Required for Langston and EDGE residents."}

RULES = [
    "Your Viking Card opens the gates at permit garages, so keep it with you.",
    "You need an active class registration, an up-to-date parking account and no unpaid citations to buy a permit.",
    "Permits are limited and can sell out.",
    "Middough Garage (Lot 13): no student parking before 4 PM on weekdays. After 4 PM and on weekends, any CSU permit works.",
    "Evening and Night permits work in every permit location except the Prospect and South garages.",
    "No overnight re-entry from 11 PM to 6 AM in the Main and Underground garages.",
    "Overnight visitor parking is in the South Garage only.",
]

# Permit and visitor access restrictions (CSU Parking Services, updated 10/3/2024).
# Each permit maps to (weekday window, weekend window) as 24-hour "HH:MM" pairs; a missing key means no access.
EVERYDAY = (("05:00", "23:59"), ("05:00", "23:59"))
AFTER_530 = (("17:30", "23:59"), ("05:00", "23:59"))
EVENING = (("15:30", "23:59"), ("05:00", "23:59"))
ALL_DAY = (("00:00", "23:59"), ("00:00", "23:59"))
ACCESS = [
    {"code": "PG", "name": "Prospect Garage", "overnight": "With an overnight Prospect permit only",
     "Prospect": EVERYDAY, "Visitor": EVERYDAY},
    {"code": "SG", "name": "South Garage", "overnight": "With a permit overnight or a visitor ticket",
     "Prospect": EVERYDAY, "Green": EVERYDAY, "White": EVERYDAY, "Visitor": ALL_DAY,
     "visitor_note": "24/7, overnight parking permitted"},
    {"code": "EG", "name": "East Garage", "overnight": "With an overnight permit only",
     "Prospect": AFTER_530, "Green": EVERYDAY, "Evening": EVENING, "Night": AFTER_530,
     "Visitor": (("15:00", "23:59"), ("05:00", "23:59"))},
    {"code": "UG", "name": "Underground Garage", "overnight": None,
     "Prospect": AFTER_530, "Green": EVERYDAY, "Evening": EVENING, "Night": AFTER_530},
    {"code": "MG", "name": "Main Garage", "overnight": None,
     "Prospect": AFTER_530, "Green": EVERYDAY, "Evening": EVENING, "Night": AFTER_530},
    {"code": "CG", "name": "Central Garage", "overnight": "With an overnight permit only",
     "Prospect": AFTER_530, "Green": EVERYDAY, "White": AFTER_530, "Evening": EVENING, "Night": AFTER_530,
     "Visitor": EVERYDAY},
    {"code": "WG", "name": "West Garage", "overnight": "With an overnight permit only, including EDGE residents",
     "Prospect": AFTER_530, "Green": EVERYDAY, "Evening": EVENING, "Night": AFTER_530, "Visitor": EVERYDAY},
    {"code": "L51", "name": "Lot 51 (Langston)", "overnight": "With an overnight permit only",
     "Green": AFTER_530, "White": EVERYDAY, "Evening": EVENING, "Night": AFTER_530,
     "visitor_note": "Langston visitor hangtag required"},
    {"code": "L52", "name": "Lot 52 (Langston)", "overnight": "With an overnight permit only",
     "Green": AFTER_530, "White": EVERYDAY, "Evening": EVENING, "Night": AFTER_530,
     "visitor_note": "Langston visitor hangtag required"},
    {"code": "EDGE", "name": "EDGE", "overnight": "With an EDGE resident or EDGE faculty and staff overnight permit",
     "only_note": "EDGE permit only (virtual permit)"},
    {"code": "L70", "name": "Lot 70", "overnight": "Visitors only, with pay station payment",
     "Visitor": ALL_DAY, "visitor_note": "24/7 with pre-payment"},
    {"code": "L66", "name": "Lot 66", "overnight": "Visitors only, with pay station payment",
     "Visitor": ALL_DAY, "visitor_note": "24/7 with pre-payment"},
    {"code": "L65", "name": "Lot 65", "overnight": None,
     "Visitor": EVERYDAY, "visitor_note": "Rec permit, or everyday 5 AM to 11:59 PM"},
]
PERMIT_TYPES = ["Green", "White", "Evening", "Night", "Prospect", "Visitor"]

# Garages and lots on the availability board. Space counts live in the parking_status table.
FACILITIES = [
    {"code": "WG", "name": "West Garage", "address": "1851 East 17th Street", "map": "WG",
     "permits": "Green, Evening, Night and visitors"},
    {"code": "CG", "name": "Central Garage", "address": "1880 East 21st Street", "map": "CG",
     "permits": "Green, Evening, Night and visitors; White after 5:30 PM"},
    {"code": "MG", "name": "Main Garage", "address": "1899 East 22nd Street", "map": "MG",
     "permits": "Green, Evening and Night"},
    {"code": "UG", "name": "Underground Garage", "address": "2399 Euclid Avenue", "map": "UG",
     "permits": "Green, Evening and Night"},
    {"code": "EG", "name": "East Garage", "address": "2506 Chester Avenue", "map": "EG",
     "permits": "Green, Evening and Night; visitors after 3 PM on weekdays"},
    {"code": "SG", "name": "South Garage", "address": "2101 East 21st Street", "map": "SG",
     "permits": "Green, White, Prospect and visitors (24/7)"},
    {"code": "PG", "name": "Prospect Garage", "address": "Prospect Avenue", "map": "PG",
     "permits": "Prospect permit and visitors"},
    {"code": "L13", "name": "Middough Garage (Lot 13)", "address": "Next to the Theatre and Arts campus", "map": None,
     "permits": "Any CSU permit after 4 PM on weekdays and all weekend"},
    {"code": "L14", "name": "Lot 14", "address": "1842 Payne Avenue", "map": None,
     "permits": "White, plus metered and visitor spaces"},
    {"code": "L20", "name": "Lot 20", "address": "1870 East 19th Street", "map": None,
     "permits": "Green, plus metered and visitor spaces"},
    {"code": "L27", "name": "Lot 27", "address": "2027 Prospect Avenue", "map": None,
     "permits": "Green and visitors"},
    {"code": "L40", "name": "Lot 40", "address": "2000 Prospect Avenue", "map": None,
     "permits": "White and visitors"},
]

NOTICES = [
    {"icon": "calendar", "title": "Thanksgiving break",
     "text": "Campus is closed Thursday, November 26 and Friday, November 27. Check garage hours before you travel."},
    {"icon": "warning", "title": "Event closures near the Wolstein Center",
     "text": "Lots 14, 27 and 40 and the South Garage may close for special events. Watch for signs before you park."},
    {"icon": "clock", "title": "Main and Underground garages overnight",
     "text": "There's no overnight re-entry from 11 PM to 6 AM in either garage."},
    {"icon": "building", "title": "Innerlink hours",
     "text": "The indoor walkway from the West Garage to the East Garage is open 6 AM to midnight, seven days a week."},
]

SCOOTER_RULES = [
    ("Riding", ["Ride in the street and follow traffic laws; use bike lanes when you can.",
                "Riders must be 18 or older. No passengers, headphones, racing or stunts.",
                "Scooters can't be charged on campus."]),
    ("Where you can't ride", ["Inside buildings or parking garages.",
                              "On the Student Center Plaza, lawns, sidewalks or pedestrian walkways."]),
    ("Parking", ["Park upright at bike racks or marked scooter zones.",
                 "Walk the scooter once you leave the road. Never block walkways, doorways, ramps or ADA spaces."]),
]

GREEN_OPTIONS = [
    {"icon": "bus", "title": "RTA buses and trains",
     "text": "Your RTA U-Pass is included in your tuition each semester, so you can ride any RTA bus or train, including the HealthLine on Euclid Avenue.",
     "label": "RideRTA", "url": "https://www.riderta.com/"},
    {"icon": "card", "title": "Zipcar",
     "text": "Five Zipcars are on campus. Students 18 and older get discounted hourly rates with gas and insurance included.",
     "label": "CSU Zipcar", "url": "https://www.zipcar.com/universities/cleveland-state-university"},
    {"icon": "refresh", "title": "Electric vehicle charging",
     "text": "Three chargers on the east side of the Student Center Garage (Lot 22). Free with a CSU permit or visitor payment; four-hour limit.",
     "label": "EV charging", "url": "https://www.csuohio.edu/parking/electric-vehicle-charging-0"},
    {"icon": "pin", "title": "Bike racks and repair",
     "text": "Racks are outside buildings across campus. A Fixit repair station with a pump sits between the Rec Center and Washkewicz Hall.",
     "label": "Bike parking", "url": "https://www.csuohio.edu/parking/motorcyclebicycle-parking"},
    {"icon": "map", "title": "Carpools and commute planning",
     "text": "GOHIO Commute compares transit, biking and carpooling by time, cost and emissions. Sign up with your CSU email.",
     "label": "GOHIO Commute", "url": "https://gohiocommute.com/"},
    {"icon": "bus", "title": "Trips out of town",
     "text": "GoBus connects Cleveland to Columbus, Athens, Cincinnati and more, and Laketran Park-n-Ride serves Lake County.",
     "label": "GoBus", "url": "https://ridegobus.com/"},
]

ESCORTS = {
    "phone": "216-687-2020",
    "map_url": "https://www.csuohio.edu/sites/default/files/Safety%20Escort%20Perimeter.jpg",
    "text": "Viking Safety Ambassadors walk with students, faculty and staff who feel unsure about their safety on campus. "
            "Escorts cover campus and nearby student housing, 24 hours a day, 7 days a week, 365 days a year.",
    "note": "It's a safety service, not a ride service.",
    "url": "https://www.csuohio.edu/police/viking-safety-escorts",
}

# Campus buildings and their escort pickup and drop-off points (CSU Police, Viking Safety Escorts page).
# The chat only recognizes these places, by name, short name or building code.
ESCORT_POINTS = [
    {"code": "BH", "name": "Berkman Hall", "point": "E. 22nd Street Cut Out", "aliases": ["Berkman"]},
    {"code": "BU", "name": "Monte Ahuja Hall (Business College)", "point": "E. 17th Street Cut Out",
     "aliases": ["Business College", "Business", "Monte Ahuja", "Monte Ahuja Hall", "College of Business"]},
    {"code": "FH", "name": "Fenn Hall", "point": "E. 24th Street and Chester Avenue", "aliases": []},
    {"code": "FT", "name": "Fenn Tower", "point": "E. 24th Street (building entrance)", "aliases": []},
    {"code": "JH", "name": "Julka Hall", "point": "Lot 66", "aliases": ["Julka"]},
    {"code": "LB", "name": "Law Building (Bert L. Wolstein Hall)", "point": "Euclid Avenue (building entrance)",
     "aliases": ["Law Building", "Law", "Wolstein Hall", "College of Law"]},
    {"code": "MU", "name": "Music and Communication Building", "point": "Lot 21 (Euclid Avenue building entrance)",
     "aliases": ["Music and Communications", "Music & Communications", "Music"]},
    {"code": "PE", "name": "Physical Education Building", "point": "E. 24th Street (near the Fenn Tower entrance)",
     "aliases": ["Physical Education", "PE Building"]},
    {"code": "RC", "name": "Recreation Center", "point": "E. 24th Street and Chester Avenue", "aliases": ["Rec Center", "Rec"]},
    {"code": "RT", "name": "Rhodes Tower", "point": "Lot 22", "aliases": ["Rhodes", "Library", "Michael Schwartz Library"]},
    {"code": "SI", "name": "Science Building", "point": "E. 24th Street (near the Fenn Tower entrance)", "aliases": ["Basic Science"]},
    {"code": "SR", "name": "Science and Research Center", "point": "E. 24th Street (near the Fenn Tower entrance)",
     "aliases": ["Science and Research", "Science Research"]},
    {"code": "SC", "name": "Student Center", "point": "Lot 22", "aliases": []},
    {"code": "ED", "name": "The Edge", "point": "Euclid Avenue (building entrance)", "aliases": ["Edge"]},
    {"code": "UR", "name": "Urban Affairs (Glickman-Miller Hall)", "point": "E. 17th Street Cut Out",
     "aliases": ["Urban Affairs", "Glickman-Miller Hall", "Levin College"]},
    {"code": "WH", "name": "Washkewicz Hall", "point": "E. 24th Street and Chester Avenue",
     "aliases": ["Washkewicz", "Engineering", "College of Engineering"]},
]

# Pickup and drop-off points placed on the campus map (map coordinates), with the buildings each one serves
ESCORT_STOPS = [
    {"id": "e17", "name": "E. 17th Street Cut Out", "x": 135, "y": 194, "codes": ["BU", "UR"]},
    {"id": "law", "name": "Euclid Avenue entrance, Law Building", "x": 197, "y": 236, "codes": ["LB"]},
    {"id": "edge", "name": "Euclid Avenue entrance, The Edge", "x": 160, "y": 245, "codes": ["ED"]},
    {"id": "lot21", "name": "Lot 21", "x": 259, "y": 225, "codes": ["MU"]},
    {"id": "lot22", "name": "Lot 22", "x": 332, "y": 227, "codes": ["RT", "SC"]},
    {"id": "e22", "name": "E. 22nd Street Cut Out", "x": 332, "y": 192, "codes": ["BH"]},
    {"id": "e24chester", "name": "E. 24th Street and Chester Avenue", "x": 416, "y": 146, "codes": ["FH", "RC", "WH"]},
    {"id": "e24near", "name": "E. 24th Street, near the Fenn Tower entrance", "x": 416, "y": 203, "codes": ["PE", "SI", "SR"]},
    {"id": "e24ft", "name": "E. 24th Street, Fenn Tower entrance", "x": 417, "y": 225, "codes": ["FT"]},
    {"id": "lot66", "name": "Lot 66", "x": 481, "y": 226, "codes": ["JH"]},
]
# The Viking Safety Escort perimeter from CSU Police's map, traced onto the campus map
ESCORT_PERIMETER = [(-28.4, 104.9), (368.4, 21.9), (562.2, 24.7), (589.2, 377.4), (321.9, 373.5), (323.9, 404.1),
                    (283.1, 415.4), (274.2, 425.1), (229.5, 424.4), (228.3, 406.7), (199.4, 404.3), (152.2, 413.4),
                    (55.7, 254.2), (8.3, 245.6), (-0.7, 154.7), (-12.7, 134.7)]

REPORT_CATEGORIES = ["Parking garage or lot", "Gate or pay station", "Lighting", "Sidewalk or crosswalk",
                     "Scooter or bike", "Bus stop or RTA", "Other"]


def _report_locations():
    return [f["name"] for f in FACILITIES] + ["Euclid Avenue", "Chester Avenue", "Prospect Avenue",
                                               "East 21st Street", "East 22nd Street", "Innerlink", "Somewhere else"]


def availability():
    rows = {r["code"]: dict(r) for r in query_all("SELECT * FROM parking_status")}
    out = []
    for f in FACILITIES:
        r = rows.get(f["code"])
        if not r:
            continue
        pct = round(100 * r["available"] / r["capacity"])
        level = "Full" if r["available"] == 0 else "Almost full" if pct < 10 else "Filling up" if pct < 30 else "Open"
        out.append({**f, "capacity": r["capacity"], "available": r["available"], "percent": pct,
                    "level": level, "updated_at": r["updated_at"]})
    return out


def best_garage(permit, now):
    """The open facility with the most spaces that this permit can use right now."""
    weekend = now.weekday() >= 5
    hhmm = now.strftime("%H:%M")
    allowed = set()
    for a in ACCESS:
        window = a.get(permit)
        if window:
            start, end = window[1 if weekend else 0]
            if start <= hhmm <= end:
                allowed.add(a["code"])
    open_now = [g for g in availability() if g["code"] in allowed and g["available"] > 0]
    return max(open_now, key=lambda g: g["available"], default=None)


def parking_for(map_code):
    """Parking details for one map code, used by the campus map popup."""
    return next((a for a in availability() if a["map"] == map_code), None)


def _reports(sid):
    return [dict(r) for r in query_all(
        "SELECT * FROM transport_reports WHERE student_id = ? ORDER BY created_at DESC, id DESC", (sid,))]


@bp.route("/transportation")
@login_required
def index():
    """Older links: the Transportation page is now split into the Getting around pages."""
    garage = request.args.get("garage")
    return redirect(url_for("transportation.parking", garage=garage) + "#parking" if garage else url_for("transportation.parking"))


@bp.route("/parking")
@login_required
def parking():
    return render_template(
        "parking.html", title="Parking garages and permits", office=PARKING_OFFICE, permits=PERMITS,
        overnight=OVERNIGHT, rules=RULES, notices=NOTICES, garages=availability(), access=ACCESS,
        permit_types=PERMIT_TYPES, focus=request.args.get("garage", ""),
    )


@bp.route("/plan-a-trip")
@login_required
def trip():
    return render_template("trip.html", title="Plan a trip", green=GREEN_OPTIONS, scooter=SCOOTER_RULES)


@bp.route("/safety-escorts")
@login_required
def escorts():
    by_code = {p["code"]: p for p in ESCORT_POINTS}
    stops = [{**st, "buildings": [by_code[c]["name"] for c in st["codes"]]} for st in ESCORT_STOPS]
    perimeter = "M" + " L".join(f"{x},{y}" for x, y in ESCORT_PERIMETER) + "Z"
    return render_template("escorts.html", title="Viking Safety Escorts", escorts=ESCORTS, points=ESCORT_POINTS,
                           stops=stops, perimeter=perimeter)


@bp.route("/report-an-issue")
@login_required
def reports():
    return render_template(
        "reports.html", title="Report an issue", categories=REPORT_CATEGORIES, locations=_report_locations(),
        reports=_reports(session["student_id"]), office=PARKING_OFFICE, escorts=ESCORTS,
    )


@bp.route("/api/transportation/parking/refresh", methods=["POST"])
@login_required
def refresh_parking():
    """Move each estimate a little, the way a garage fills and empties through the day.

    While the student previews another day the counts stay put: nobody knows what parking will look like then.
    """
    if previewing():
        return jsonify(garages=availability(), frozen=True,
                       message="Parking counts stay as of November 12 while you preview another day.")
    now = project_now().isoformat(timespec="minutes")
    db = get_db()
    for r in query_all("SELECT * FROM parking_status"):
        # Surface lots move by a few spaces at a time; big garages by up to about one percent
        step = 3 if r["code"].startswith("L") else max(4, r["capacity"] // 100)
        value = min(r["capacity"], max(0, r["available"] + random.randint(-step, step)))
        db.execute("UPDATE parking_status SET available = ?, updated_at = ? WHERE code = ?", (value, now, r["code"]))
    db.commit()
    return jsonify(garages=availability())


@bp.route("/api/transportation/reports", methods=["POST"])
@login_required
def add_report():
    sid = session["student_id"]
    data = request.get_json(silent=True) or {}
    category = data.get("category")
    location = " ".join(str(data.get("location") or "").split())
    description = " ".join(str(data.get("description") or "").split())
    details = " ".join(str(data.get("details") or "").split()) or None
    if category not in REPORT_CATEGORIES:
        abort(400, description="Choose what kind of issue it is.")
    if not location or len(location) > 80:
        abort(400, description="Choose or enter where the issue is.")
    if len(description) < 10:
        abort(400, description="Describe the issue in at least 10 characters.")
    if len(description) > 500 or (details and len(details) > 500):
        abort(400, description="Keep each answer under 500 characters.")
    db = get_db()
    db.execute(
        "INSERT INTO transport_reports (student_id, category, location, description, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (sid, category, location, description, details, project_now().isoformat(timespec="minutes")),
    )
    db.commit()
    return jsonify(reports=_reports(sid))

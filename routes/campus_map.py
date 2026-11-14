"""Interactive CSU campus map.

The map is drawn from the official CSU campus map PDF (buildings, grounds and
city blocks are traced from its shapes). Building names, codes and addresses
come from the map's building key.
"""
from flask import Blueprint, abort, current_app, jsonify, render_template, request, session, url_for

from alerts import project_today
from db import get_db, query_all, query_one
from routes.transportation import parking_for
from security import login_required

bp = Blueprint("campus_map", __name__)

OFFICIAL_MAP = "https://www.csuohio.edu/campus-map"
OFFICIAL_PDF = "https://www.csuohio.edu/sites/default/files/2026-08/campusmap.pdf"

CATEGORIES = ["Academic", "Student services", "Housing", "Athletics and recreation", "Parking", "Facilities"]

# code: (name, category, address, what's inside)
BUILDINGS = {
    "AA": ("AMC Annex", "Facilities", "1751 East 23rd Street", ""),
    "AC": ("Parker Hannifin Administration Center", "Student services", "2300 Euclid Avenue", ""),
    "BH": ("Berkman Hall", "Student services", "1899 East 22nd Street",
           "Jack, Joseph and Morton Mandel Honors College; Campus 411 All-In-1; Parking and Transportation Services; Viking Card Office; ATM"),
    "BU": ("Monte Ahuja Hall", "Academic", "1860 East 18th Street", "Monte Ahuja College of Business"),
    "CE": ("Cole Center", "Facilities", "3100 Chester Avenue", "C.M.S.D. Campus International School 9–12"),
    "CH": ("College of Health", "Academic", "2112 Euclid Avenue", "College of Health; Health and Wellness Services"),
    "CM": ("Ceramics and Manufacturing", "Facilities", "1768 East 25th Street", "Magnet ceramics building"),
    "CS": ("Campus Safety", "Student services", "1840 Chester Avenue", "University Police"),
    "EC": ("Euclid Commons", "Housing", "2450 Euclid Avenue",
           "Student housing; Welcome Center; Undergraduate, Graduate and International Admissions; Residence Life"),
    "ED": ("Edge Building", "Housing", "1750 Euclid Avenue", "Student housing"),
    "FH": ("Fenn Hall", "Academic", "1960 East 24th Street", "Washkewicz College of Engineering"),
    "FM": ("School of Film & Media Arts", "Academic", "1375 Euclid Avenue", "CSU Arts Campus"),
    "FT": ("Fenn Tower", "Housing", "1983 East 24th Street", "Student housing; ATM"),
    "HS": ("Health Sciences", "Academic", "2501 Euclid Avenue", ""),
    "JH": ("Julka Hall", "Academic", "2485 Euclid Avenue", ""),
    "KF": ("Krenzler Field", "Athletics and recreation", "1850 Chester Avenue", ""),
    "LA": ("Langston", "Housing", "North of Chester Avenue", "Student housing, buildings 1 to 9"),
    "LB": ("Bert L. Wolstein Hall", "Academic", "1801 Euclid Avenue", "College of Law"),
    "LL": ("Law Library", "Academic", "1801 Euclid Avenue", ""),
    "MM": ("Mather Mansion", "Student services", "2605 Euclid Avenue", "Counseling Center"),
    "MU": ("Music and Communication", "Academic", "2001 Euclid Avenue", "Waetjen Auditorium; Drinko Recital Hall"),
    "PA": ("Plant Annex", "Facilities", "1741 East 25th Street", ""),
    "PE": ("Physical Education", "Athletics and recreation", "2451 Euclid Avenue", "Robert Busbey Natatorium; Woodling Gymnasium"),
    "PH": ("Parker Hannifin Hall", "Academic", "2258 Euclid Avenue", "College of Graduate Studies"),
    "PS": ("Plant Services", "Facilities", "1802 East 25th Street", ""),
    "RC": ("Recreation Center", "Athletics and recreation", "2420 Chester Avenue", ""),
    "RT": ("Rhodes Tower", "Academic", "1860 East 22nd Street", "Michael Schwartz Library; Center for eLearning"),
    "RW": ("Rhodes West", "Academic", "2124 Chester Avenue", ""),
    "SC": ("Student Center", "Student services", "2121 Euclid Avenue", "Viking Marketplace; Viking Outfitters; Starbucks; Chick-fil-A; ATM"),
    "SI": ("Science Building", "Academic", "2399 Euclid Avenue", ""),
    "SR": ("Science and Research Center", "Academic", "2351 Euclid Avenue", ""),
    "TA": ("Theatre and Arts", "Academic", "1901 East 13th Street", "CSU Arts Campus"),
    "TC": ("Trinity Commons", "Student services", "2254 Euclid Avenue", "Veteran and Military Student Success Center"),
    "TD": ("Medical Mutual Tennis Dome and Pavilion", "Athletics and recreation", "2005 Chester Avenue", ""),
    "UN": ("Union Building", "Student services", "1836 Euclid Avenue", ""),
    "UR": ("Glickman-Miller Hall", "Academic", "1717 Euclid Avenue", "Levin College of Public Affairs and Education"),
    "WA": ("Wallingford Building", "Facilities", "2504 Payne Avenue", ""),
    "WH": ("Washkewicz Hall", "Academic", "2300 Chester Avenue", "Washkewicz College of Engineering"),
    "WO": ("Wolstein Center", "Athletics and recreation", "2000 Prospect Avenue", "Bert L. & Iris S. Wolstein Center; Henry A. Goodman Arena"),
    "WP": ("Wolstein Center Pavilion and Banquet Center", "Athletics and recreation", "2000 Prospect Avenue", "Gerald H. Gordon Conference Pavilion"),
    # Parking garages
    "CG": ("Central Garage", "Parking", "East 21st Street", ""),
    "EG": ("East Garage", "Parking", "2506 Chester Avenue", ""),
    "MG": ("Main Garage", "Parking", "Underneath Berkman Hall", ""),
    "PG": ("Prospect Garage", "Parking", "2350 Prospect Avenue", ""),
    "RG": ("Rec Center Garage", "Parking", "Between the Rec Center and East Garage", ""),
    "SG": ("South Garage", "Parking", "2101 East 21st Street", ""),
    "UG": ("Underground Garage", "Parking", "Underneath the Science Building", ""),
    "WG": ("West Garage", "Parking", "1851 East 17th Street", ""),
}

# Where each building's pin sits on the map (map units), from the label positions on the official map
PINS = {'WO': [231.1, 350.1], 'WP': [269.8, 350.1], 'KF': [201.4, 105.9], 'TD': [267.5, 116.1], 'LA': [376.0, 114.2],
        'RT': [327.4, 143.7], 'CS': [212.9, 160.4], 'RW': [298.0, 161.2], 'WH': [391.6, 155.5], 'RC': [447.7, 157.5],
        'FH': [406.7, 181.4], 'PE': [455.1, 181.2], 'BH': [350.4, 193.0], 'MU': [247.0, 201.7], 'SR': [372.7, 203.2],
        'HS': [465.9, 200.4], 'SC': [312.1, 211.2], 'SI': [400.6, 216.9], 'FT': [426.9, 216.7], 'TC': [354.5, 257.1],
        'PH': [375.2, 257.1], 'AC': [394.2, 257.1], 'EC': [409.7, 288.6], 'CH': [308.3, 273.9], 'WA': [473.1, 11.6],
        'PA': [476.2, 34.2], 'AA': [403.0, 65.4], 'PS': [451.7, 75.9], 'CE': [648.5, 162.7], 'LL': [190.5, 175.4],
        'TA': [46.7, 188.2], 'BU': [153.6, 195.2], 'MM': [488.3, 200.9], 'LB': [194.9, 216.5], 'FM': [56.4, 223.2],
        'UR': [148.2, 222.2], 'JH': [463.7, 225.7], 'UN': [215.7, 249.9], 'ED': [162.2, 255.1], 'CM': [451.7, 47.2],
        'SG': [308.6, 353.6], 'UG': [402.3, 204.6], 'PG': [392.7, 290.4], 'WG': [148.4, 164.3], 'CG': [254.2, 166.9],
        'RG': [467.8, 156.5], 'EG': [491.7, 173.9], 'MG': [350.4, 193.0]}

# Official CSU pages related to each building (all verified csuohio.edu or CSU-run sites)
LINKS = {
    "parking": ("Parking and transportation services", "https://www.csuohio.edu/parking"),
    "allin1": ("Campus 411 All-In-1 Enrollment Services", "https://www.csuohio.edu/all-in-1/all-in-1"),
    "vcard": ("Viking Card Office", "https://www.csuohio.edu/vikingcard"),
    "library": ("Michael Schwartz Library", "https://library.csuohio.edu/"),
    "elearning": ("Center for eLearning and Blackboard", "https://www.csuohio.edu/center-for-elearning/blackboard-login"),
    "dining": ("Viking Food Co. menus and hours", "https://vikingfoodco.campusdish.com/"),
    "belonging": ("Student Belonging and Success", "https://www.csuohio.edu/sbs/vikesbewell"),
    "rec": ("Campus Recreation", "https://csurec.com/"),
    "health": ("CSU Health Clinic", "https://www.csuohio.edu/health"),
    "counseling": ("Counseling Center", "https://www.csuohio.edu/counseling"),
    "escorts": ("Viking Safety Escorts", "https://www.csuohio.edu/police/viking-safety-escorts"),
    "welcome": ("New student welcome page", "https://www.csuohio.edu/welcome"),
    "housing": ("Residence Life and housing", "https://www.csuohio.edu/residence-life/housing-rates"),
    "business": ("Monte Ahuja College of Business", "https://business.csuohio.edu/"),
    "engineering": ("Washkewicz College of Engineering", "https://engineering.csuohio.edu/"),
    "colleges": ("CSU colleges", "https://www.csuohio.edu/academics/colleges"),
    "athletics": ("Cleveland State Athletics: Wolstein Center", "https://csuvikings.com/sports/2024/5/10/directionsandinformation"),
}
# Pages inside Viking Hub related to each building
HUB = {
    "card": ("Your Viking Card", "viking_card.index"),
    "transport": ("Parking garages and permits", "transportation.parking"),
    "escort": ("Viking Safety Escorts", "transportation.escorts"),
    "schedule": ("Your schedule", "schedule.index"),
    "orientation": ("Orientation checklist", "orientation.index"),
}
RESOURCES = {
    "BH": (["allin1", "vcard", "parking"], ["card", "transport"]),
    "RT": (["library", "elearning"], []),
    "SC": (["dining", "belonging"], ["card"]),
    "RC": (["rec"], []), "PE": (["rec"], []),
    "CH": (["health", "colleges"], []),
    "MM": (["counseling"], []),
    "CS": (["escorts"], ["escort"]),
    "EC": (["welcome", "housing"], ["orientation"]),
    "FT": (["housing"], []), "ED": (["housing"], []), "LA": (["housing"], []),
    "BU": (["business"], []),
    "FH": (["engineering"], []), "WH": (["engineering"], []),
    "LB": (["colleges"], []), "LL": (["colleges"], []), "UR": (["colleges"], []), "PH": (["colleges"], []),
    "MU": (["colleges"], []), "SI": (["colleges"], []), "SR": (["colleges"], []), "HS": (["colleges"], []),
    "FM": (["colleges"], []), "TA": (["colleges"], []),
    "WO": (["athletics"], []), "WP": (["athletics"], []),
}
# Other names a building goes by, used to match class and event locations
ALIASES = {
    "BU": ["Monte Ahuja"], "RT": ["Michael Schwartz Library", "Rhodes Tower"], "RC": ["Recreation Center", "Rec Center"],
    "SC": ["Student Center", "Viking Outfitters"], "CH": ["College of Health"], "FT": ["Fenn Tower"],
    "LA": ["Langston"], "BH": ["Berkman Hall"],
}

# Codes whose shape on the map belongs to another building (garages under buildings)
SHAPE_OF = {"MG": "BH"}

# The Innerlink: enclosed walkways and bridges joining the core buildings (CSU news, November 2022)
INNERLINK = {
    "route": ["WG", "UR", "BU", "LL", "LB", "MU", "SC", "BH", "SI", "SR", "FH", "RC", "EG"],
    "hours": "6 AM to midnight, seven days a week",
    "entries": ["Second floor of the West Garage, into Monte Ahuja Hall",
                "The Euclid Avenue entrance to the Student Center",
                "Third floor of the East Garage, into the Recreation Center"],
    "url": "https://csu2.0.csuohio.edu/news/innerlink-now-open-6-am-midnight-seven-days-week",
}


def building_list():
    out = []
    for code, (name, category, address, inside) in BUILDINGS.items():
        ext, hub = RESOURCES.get(code, ([], []))
        if category == "Parking":
            ext, hub = ["parking"], ["transport"]
        links = [{"label": LINKS[k][0], "url": LINKS[k][1], "external": True} for k in ext]
        links += [{"label": HUB[k][0], "url": url_for(HUB[k][1]), "external": False} for k in hub]
        parking = None
        if category == "Parking":
            p = parking_for(code)
            if p:
                parking = {k: p[k] for k in ("name", "available", "capacity", "percent", "level", "permits", "updated_at")}
                parking["url"] = url_for("transportation.parking", garage=code) + "#parking"
        out.append({"code": code, "name": name, "category": category, "address": address, "parking": parking,
                    "inside": [s.strip() for s in inside.split(";") if s.strip()],
                    "pin": PINS.get(code), "shape": SHAPE_OF.get(code, code),
                    "names": [name] + ALIASES.get(code, []), "links": links})
    return sorted(out, key=lambda b: b["name"])


def _pins(sid):
    return [dict(r) for r in query_all(
        "SELECT id, code, x, y, label, is_home FROM map_pins WHERE student_id = ? ORDER BY id", (sid,))]


def _my_places(sid):
    """Classes and upcoming plans, so a building can show what's on the student's schedule there."""
    today = project_today().isoformat()
    classes = [dict(r) for r in query_all(
        "SELECT code, days, start_time, end_time, location FROM courses WHERE student_id = ? AND location IS NOT NULL", (sid,))]
    events = [dict(r) for r in query_all(
        """SELECT title, event_date, start_time, location FROM events
           WHERE student_id = ? AND location IS NOT NULL AND event_date >= ? ORDER BY event_date, start_time""", (sid, today))]
    return {"classes": classes, "events": events}


@bp.route("/campus-map")
@login_required
def index():
    sid = session["student_id"]
    selected = (request.args.get("b") or "").upper()
    return render_template(
        "campus_map.html", title="Campus map", buildings=building_list(), categories=CATEGORIES,
        selected=selected if selected in BUILDINGS else "", official_map=OFFICIAL_MAP, official_pdf=OFFICIAL_PDF,
        pins=_pins(sid), places=_my_places(sid), innerlink=INNERLINK,
        open_innerlink=request.args.get("innerlink") == "1",
    )


@bp.route("/api/map/pins", methods=["POST"])
@login_required
def add_pin():
    sid = session["student_id"]
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").upper() or None
    label = " ".join(str(data.get("label") or "").split())[:40]
    if code:
        if code not in BUILDINGS:
            abort(400, description="That building wasn't found.")
        if query_one("SELECT 1 FROM map_pins WHERE student_id = ? AND code = ?", (sid, code)):
            abort(400, description="That building is already pinned.")
        x, y = PINS[code]
        label = label or BUILDINGS[code][0]
    else:
        try:
            x, y = float(data.get("x")), float(data.get("y"))
        except (TypeError, ValueError):
            abort(400, description="Choose a spot on the map.")
        if not (0 <= x <= 680 and 0 <= y <= 395):
            abort(400, description="Choose a spot on the map.")
        if not label:
            abort(400, description="Give your pin a name.")
    db = get_db()
    db.execute("INSERT INTO map_pins (student_id, code, x, y, label) VALUES (?, ?, ?, ?, ?)", (sid, code, x, y, label))
    db.commit()
    return jsonify(pins=_pins(sid), message="Pin added to your map")


@bp.route("/api/map/pins/<int:pin_id>/home", methods=["POST"])
@login_required
def set_home(pin_id):
    """Make a pin the starting point for Leave by walking times."""
    sid = session["student_id"]
    pin = query_one("SELECT label FROM map_pins WHERE id = ? AND student_id = ?", (pin_id, sid))
    if pin is None:
        abort(404, description="That pin was already removed.")
    db = get_db()
    db.execute("UPDATE map_pins SET is_home = (id = ?) WHERE student_id = ?", (pin_id, sid))
    db.commit()
    return jsonify(pins=_pins(sid), message=f"Walking times now start from {pin['label']}")


@bp.route("/api/map/pins/<int:pin_id>", methods=["DELETE"])
@login_required
def remove_pin(pin_id):
    sid = session["student_id"]
    db = get_db()
    cur = db.execute("DELETE FROM map_pins WHERE id = ? AND student_id = ?", (pin_id, sid))
    if cur.rowcount == 0:
        abort(404, description="That pin was already removed.")
    db.commit()
    return jsonify(pins=_pins(sid), message="Pin removed")

"""Walking times between campus buildings, for the Leave by lines on Home and the schedule.

Times are estimates measured on the campus map. The map is drawn to scale:
East 17th Street to East 24th Street is about half a mile, which is about
560 map units per mile. Paths are rarely straight, so the straight-line
distance is stretched by a fifth. The pace is 3 miles an hour, plus a
2 minute buffer, rounded up to whole minutes.
"""
import math

from db import query_one
from routes.campus_map import ALIASES, BUILDINGS, INNERLINK, PINS

UNITS_PER_MILE = 560
PATH_FACTOR = 1.2
MPH = 3
BUFFER_MIN = 2
MAX_GAP_MIN = 30   # a longer break than this and the next walk starts from home
DEFAULT_HOME = "FT"


def _names():
    """(lowercase name, code) pairs, longest first, so 'Science and Research Center' wins over 'Science'."""
    pairs = []
    for code, (name, category, *_rest) in BUILDINGS.items():
        if category == "Parking" or code not in PINS:
            continue
        for n in [name] + ALIASES.get(code, []):
            pairs.append((n.lower(), code))
    return sorted(pairs, key=lambda p: -len(p[0]))


NAMES = _names()


def building_for(location):
    """The map code for a class or event location, such as 'Berkman Hall 433' -> 'BH'."""
    text = (location or "").lower()
    return next((code for name, code in NAMES if name in text), None)


def walk_minutes(a, b):
    """Minutes to walk between two (x, y) map points, buffer included."""
    miles = math.dist(a, b) / UNITS_PER_MILE * PATH_FACTOR
    return math.ceil(miles / MPH * 60 + BUFFER_MIN)


def home_point(sid):
    """Where the first walk of the day starts: the student's home pin, or Fenn Tower."""
    pin = query_one("SELECT code, x, y, label FROM map_pins WHERE student_id = ? AND is_home = 1", (sid,))
    if pin:
        return {"label": pin["label"], "code": pin["code"], "point": [pin["x"], pin["y"]]}
    return {"label": BUILDINGS[DEFAULT_HOME][0], "code": DEFAULT_HOME, "point": PINS[DEFAULT_HOME]}


def indoor(a_code, b_code):
    route = INNERLINK["route"]
    return bool(a_code and b_code and a_code != b_code and a_code in route and b_code in route)


def walk_line(start, code):
    """start = {'label', 'code', 'point'}; code = the destination building."""
    if code is None or code not in PINS:
        return None
    if start["code"] == code:
        return {"same": True, "from": start["label"], "minutes": 0, "indoor": False}
    return {"same": False, "from": start["label"], "minutes": walk_minutes(start["point"], PINS[code]),
            "indoor": indoor(start["code"], code)}


def _minutes(hhmm):
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def plan_day(sid, classes):
    """Add a 'walk' entry to each item (dicts with start_time, end_time and location, sorted by time).

    A walk starts from the previous item's building only when this one begins within
    MAX_GAP_MIN minutes of the previous one ending. After a longer break, or for the
    first item of the day, it starts from the student's home pin.
    """
    home = home_point(sid)
    prev = None  # (start point, end minute) of the last place the student was
    for c in classes:
        code = building_for(c.get("location"))
        start_min = _minutes(c["start_time"])
        start = prev[0] if prev and start_min - prev[1] <= MAX_GAP_MIN else home
        walk = walk_line(start, code)
        if walk:
            walk["from_home"] = start is home
            leave = start_min - walk["minutes"]
            walk["leave_by"] = f"{leave // 60:02d}:{leave % 60:02d}"
        c["walk"] = walk
        if code:
            end_min = _minutes(c["end_time"]) if c.get("end_time") else start_min
            prev = ({"label": BUILDINGS[code][0], "code": code, "point": PINS[code]}, end_min)
    return classes


def walk_config(sid):
    """Everything the schedule page needs to work out the same lines in the browser."""
    return {
        "points": {code: PINS[code] for code in BUILDINGS if code in PINS and BUILDINGS[code][1] != "Parking"},
        "building_names": {code: BUILDINGS[code][0] for code in BUILDINGS},
        "names": [[n, c] for n, c in NAMES],
        "home": home_point(sid),
        "route": INNERLINK["route"],
        "max_gap": MAX_GAP_MIN,
        "units_per_mile": UNITS_PER_MILE, "path_factor": PATH_FACTOR, "mph": MPH, "buffer": BUFFER_MIN,
    }

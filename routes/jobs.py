"""Student jobs: CSU's on-campus employment rules, Handshake links and sample openings.

CSU posts on-campus jobs in Handshake, which has no public API, so Viking Hub can't read real
postings. The openings here are sample listings; every Apply button opens Handshake. What
Viking Hub adds is the planning: each opening is checked against the student's classes
(CSU doesn't allow working during class time) and the 20 hour weekly limit, and its shifts
can be added to the schedule."""
from datetime import date, timedelta

from flask import Blueprint, abort, jsonify, render_template, request, session

from alerts import add_alert, project_today
from db import get_db, query_all, query_one
from security import login_required

bp = Blueprint("jobs", __name__)

HANDSHAKE = "https://app.joinhandshake.com/login"
SEMESTER_LIMIT = 20          # hours a week during fall and spring, all campus jobs together
BREAK_LIMIT = 40
LAST_WORK_DAY = "2026-12-11"  # the last day of classes before finals week
CLOSED = {"2026-11-26", "2026-11-27"}  # Thanksgiving closure: no hours can be recorded
DAY_NAMES = {"M": "Mon", "T": "Tue", "W": "Wed", "R": "Thu", "F": "Fri", "S": "Sat", "U": "Sun"}
DAY_INDEX = {"M": 0, "T": 1, "W": 2, "R": 3, "F": 4, "S": 5, "U": 6}

OFFICE = {
    "name": "Career Development and Exploration",
    "where": "Berkman Hall 116", "code": "BH",
    "hours": "Monday to Friday, 9:00 AM to 5:00 PM",
    "email": "careers@csuohio.edu",
    "url": "https://www.csuohio.edu/career-development-exploration/students",
}

# Magnus's current campus job: the Friday shift already on his schedule
CURRENT_JOB = {"title": "Sales associate", "where": "Viking Outfitters, Student Center",
               "shifts": [("F", "13:30", "17:30")]}

RULES = [
    "Be registered for at least 6 credit hours in the semester you work, and in good academic standing.",
    "Work up to 20 hours a week during fall and spring semesters, finals week included, and up to 40 hours a week during breaks.",
    "Hours from every campus job count together toward those limits. Let each supervisor know about the others.",
    "You can't work during your scheduled class times or final exams, even if a class is canceled or lets out early.",
    "Clock in and out in Kronos for every shift, and clock out for breaks, which are unpaid.",
    "Pay weeks run Sunday to Saturday, and paychecks come every other Friday for the two weeks before.",
    "No hours can be recorded on days the university is closed.",
]

WORK_STUDY = [
    "Federal Work Study (FWS) is financial aid you earn by working a student job. It isn't paid up front.",
    "Your award, if you have one, is on your financial aid award letter in CampusNet. It depends on your FAFSA, financial need and available funds.",
    "You can earn up to your award during the academic year, including winter and spring breaks but not summer. Keep track by subtracting each paycheck's gross pay.",
    "FWS is open to U.S. citizens and eligible residents, not international students. FWS wages are taxable.",
]

GUIDES = [
    ("Student Employee Handbook", "https://www.csuohio.edu/sites/default/files/Student%20Handbook%20rev0822.pdf",
     "Rules, Federal Work Study and Handshake steps"),
    ("New student employee orientation", "https://www.csuohio.edu/sites/default/files/New%20Student%20Employee%20Orientation%20rev0822.pdf",
     "What to expect in your first weeks"),
    ("Student employment hiring packet", "https://www.csuohio.edu/sites/default/files/Student%20Employment%20Hiring%20Packet%20rev0822.pdf",
     "Forms to complete once you're hired"),
    ("Work schedule template", "https://www.csuohio.edu/sites/default/files/media/career_services/documents/workschedule.pdf",
     "Share your class schedule with a supervisor"),
    ("Kronos timesheet instructions", "https://www.csuohio.edu/sites/default/files/Kronos%20Recording%20Instructions.pptx",
     "Clocking in and out"),
    ("Viewing your paycheck", "https://www.csuohio.edu/sites/default/files/View%20Paycheck%20Instructions_0.pdf",
     "Find your pay statements"),
]


def _shift_text(shifts):
    from formatting import nice_time
    return [f"{DAY_NAMES[d]} {nice_time(s)} to {nice_time(e)}" for d, s, e in shifts]


def _hours(shifts):
    total = 0
    for _d, s, e in shifts:
        sh, sm = map(int, s.split(":"))
        eh, em = map(int, e.split(":"))
        total += (eh * 60 + em - sh * 60 - sm) / 60
    return total


def _parse_shifts(text):
    out = []
    for part in text.split(";"):
        d, span = part.strip().split(" ")
        s, e = span.split("-")
        out.append((d, s, e))
    return out


def _class_clashes(sid, shifts):
    """Classes that meet during any shift (CSU doesn't allow working during class time)."""
    from routes.schedule import _overlaps
    out = []
    for c in query_all("SELECT * FROM courses WHERE student_id = ? AND delivery = 'In person'", (sid,)):
        for d, s, e in shifts:
            if d in (c["days"] or "") and _overlaps(s, e, c["start_time"], c["end_time"]):
                out.append({"course": c["code"], "day": DAY_NAMES[d], "start": c["start_time"], "end": c["end_time"]})
    return out


def _shift_dates(shifts, start_day):
    """Every date a weekly shift falls on from start_day through the last day of classes."""
    out = []
    for d, s, e in shifts:
        day = start_day + timedelta(days=(DAY_INDEX[d] - start_day.weekday()) % 7)
        while day.isoformat() <= LAST_WORK_DAY:
            if day.isoformat() not in CLOSED:
                out.append((day.isoformat(), s, e))
            day += timedelta(days=7)
    return sorted(out)


def _added_jobs(sid):
    return {r["job_id"] for r in query_all(
        "SELECT DISTINCT job_id FROM events WHERE student_id = ? AND job_id IS NOT NULL", (sid,))}


def jobs_state(sid):
    saved = {r["job_id"] for r in query_all("SELECT job_id FROM job_saves WHERE student_id = ?", (sid,))}
    added = _added_jobs(sid)
    listings = []
    for r in query_all("SELECT * FROM jobs ORDER BY posted DESC, id"):
        shifts = _parse_shifts(r["shifts"])
        clashes = _class_clashes(sid, shifts)
        listings.append({
            "id": r["id"], "title": r["title"], "dept": r["dept"], "where": r["location"], "code": r["building"],
            "pay": r["pay_cents"] / 100, "fws": bool(r["fws"]), "posted": r["posted"],
            "description": r["description"], "shifts": _shift_text(shifts), "hours": round(_hours(shifts), 1),
            "clashes": clashes, "saved": r["id"] in saved, "added": r["id"] in added,
        })
    current = round(_hours(CURRENT_JOB["shifts"]), 1)
    planned = sum(j["hours"] for j in listings if j["added"])
    return {"listings": listings, "current": {**CURRENT_JOB, "shift_text": _shift_text(CURRENT_JOB["shifts"]),
                                              "hours": current},
            "hours_total": round(current + planned, 1), "limit": SEMESTER_LIMIT}


def _job(job_id):
    try:
        job_id = int(job_id)
    except (TypeError, ValueError, OverflowError):
        abort(404, description="That opening wasn't found.")
    row = query_one("SELECT * FROM jobs WHERE id = ?", (job_id,)) if 0 < job_id < 2**31 else None
    if row is None:
        abort(404, description="That opening wasn't found.")
    return row


@bp.route("/student-jobs")
@login_required
def index():
    return render_template("student_jobs.html", title="Student jobs", handshake=HANDSHAKE, office=OFFICE,
                           rules=RULES, work_study=WORK_STUDY, guides=GUIDES,
                           state=jobs_state(session["student_id"]))


@bp.route("/api/jobs/<int:job_id>/save", methods=["POST", "DELETE"])
@login_required
def save(job_id):
    sid = session["student_id"]
    job = _job(job_id)
    db = get_db()
    if request.method == "POST":
        db.execute("INSERT OR IGNORE INTO job_saves (student_id, job_id) VALUES (?, ?)", (sid, job["id"]))
        message = "Saved"
    else:
        db.execute("DELETE FROM job_saves WHERE student_id = ? AND job_id = ?", (sid, job["id"]))
        message = "Removed from saved"
    db.commit()
    return jsonify(state=jobs_state(sid), message=message)


@bp.route("/api/jobs/<int:job_id>/schedule", methods=["POST", "DELETE"])
@login_required
def schedule(job_id):
    """Add an opening's weekly shifts to the schedule through the last day of classes, or take them off."""
    from routes.schedule import conflicts_for
    sid = session["student_id"]
    job = _job(job_id)
    db = get_db()
    if request.method == "DELETE":
        n = db.execute("DELETE FROM events WHERE student_id = ? AND job_id = ?", (sid, job["id"])).rowcount
        db.commit()
        if not n:
            abort(404, description="Those shifts aren't on your schedule.")
        return jsonify(state=jobs_state(sid), message=f"{job['title']} shifts removed from your schedule")

    if job["id"] in _added_jobs(sid):
        abort(409, description="Those shifts are already on your schedule.")
    shifts = _parse_shifts(job["shifts"])
    clashes = _class_clashes(sid, shifts)
    if clashes:
        c = clashes[0]
        abort(409, description=f"These shifts overlap {c['course']} on {c['day']}. CSU doesn't allow working during class time.")
    state = jobs_state(sid)
    total = state["hours_total"] + _hours(shifts)
    if total > SEMESTER_LIMIT:
        abort(409, description=(f"That would bring you to {total:g} hours a week across your campus jobs. "
                                f"CSU's limit during the semester is {SEMESTER_LIMIT}."))
    start_day = max(project_today(), date(2026, 8, 24))
    dates = _shift_dates(shifts, start_day)
    if not dates:
        abort(409, description="There are no class days left this semester to add shifts to.")
    data = request.get_json(silent=True) or {}
    overlaps = []
    for day, s, e in dates:
        for c in conflicts_for(sid, day, s, e):
            if c["kind"] == "event":
                overlaps.append({**c, "date": day})
    if overlaps and not data.get("confirm"):
        return jsonify(needs_confirm=True, conflicts=overlaps[:3], count=len(overlaps))
    db.executemany(
        """INSERT INTO events (student_id, kind, title, event_date, start_time, end_time, location, notes, job_id)
           VALUES (?, 'personal', ?, ?, ?, ?, ?, ?, ?)""",
        [(sid, f"Work: {job['title']}", day, s, e, job["location"],
          f"{job['dept']}. Clock in and out in Kronos.", job["id"]) for day, s, e in dates])
    db.commit()
    add_alert(sid, "schedule", "Work shifts added",
              f"{job['title']}: {len(dates)} shifts through December 11 are on your schedule.",
              "briefcase", "schedule.index")
    db.commit()
    return jsonify(state=jobs_state(sid), message=f"{len(dates)} shifts added to your schedule")

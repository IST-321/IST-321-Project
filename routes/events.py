"""Campus events, student organizations and VikesConnect.

The clubs are real Cleveland State student organizations. Meeting times, places and
applications here are Viking Hub sample data: applying saves the answers in Viking Hub
only. Joining for real happens on the organization's VikesConnect page.
"""
import json
from datetime import date

from flask import Blueprint, abort, jsonify, render_template, request, session

from alerts import add_alert, project_now
from db import get_db, query_all, query_one
from routes.schedule import COMMON_HOUR, conflicts_for
from security import login_required

bp = Blueprint("events", __name__)

VIKESCONNECT = "https://csuohio.presence.io/"
ENGAGEMENT = {
    "name": "Center for Campus Engagement",
    "where": "Student Center, Room 343",
    "phone": "216-687-2048",
    "email": "studentorgs@csuohio.edu",
    "hours": "Monday to Friday, 8 AM to 5 PM",
    "url": "https://www.csuohio.edu/campus-engagement/vikesconnect",
}

# A short list of real CSU student organizations. Meeting details are sample data.
CLUBS = [
    {"slug": "cab", "name": "Campus Activities Board", "short": "Plans the big campus events, from spirit week to CABsino.",
     "category": "Campus life", "icon": "ticket", "tone": "green",
     "about": "CAB is the student-run programming board behind spirit week, CABsino, movie nights and other campus-wide events. "
              "Members pitch ideas, plan events and run them on the day.",
     "meets": "Thursdays during common hour, 11:30 AM", "where": "Student Center 313",
     "question": "Which kind of event would you most like to help plan?"},
    {"slug": "vicious-vikes", "name": "Vicious Vikes", "short": "The student section that brings the noise to Vikings games.",
     "category": "Spirit and athletics", "icon": "horn", "tone": "dark",
     "about": "Vicious Vikes fills the student section at the Wolstein Center and other home games, makes the signs and leads the chants. "
              "Road trips to big away games happen when the schedule allows.",
     "meets": "Before home games", "where": "Wolstein Center",
     "question": "Which Vikings teams do you want to cheer for?"},
    {"slug": "esports", "name": "Cleveland State Esports", "short": "Casual and competitive gaming out of the esports lab.",
     "category": "Gaming", "icon": "laptop", "tone": "fresh",
     "about": "CSU Esports practices and competes in titles such as Valorant from the esports lab in the Washkewicz College of Engineering. "
              "Club members can play casually or try out for competitive rosters.",
     "meets": "Tuesdays during common hour, plus open lab nights", "where": "Esports lab, Washkewicz Hall",
     "question": "What games do you play, and what rank or level are you?"},
    {"slug": "swe", "name": "Society of Women Engineers", "short": "Support, networking and outreach for women in engineering.",
     "category": "Academic and professional", "icon": "building", "tone": "green",
     "about": "SWE is a professional and social organization that supports women in engineering through coffee hours, networking nights "
              "with IEEE and Women in Engineering, and outreach to local students. All majors are welcome.",
     "meets": "Coffee hour on Tuesdays during common hour", "where": "Washkewicz Hall",
     "question": "What's your major or the engineering field you're curious about?"},
    {"slug": "ewb", "name": "Engineers Without Borders", "short": "Hands-on engineering projects that serve communities.",
     "category": "Service", "icon": "map", "tone": "dark",
     "about": "The CSU chapter of Engineers Without Borders designs and builds projects with partner communities, "
              "from local work in Cleveland to international trips. Students from any major can help with planning, fundraising and design.",
     "meets": "Every other Wednesday, 5 PM", "where": "Fenn Hall",
     "question": "What skills would you bring to a project team?"},
    {"slug": "bsu", "name": "Black Student Union", "short": "Community, culture and advocacy for Black students at CSU.",
     "category": "Cultural", "icon": "megaphone", "tone": "fresh",
     "about": "BSU builds community through welcome events, cultural programs, service and conversations about issues that matter to Black students. "
              "Everyone who supports its mission is welcome.",
     "meets": "Thursdays during common hour, 11:30 AM", "where": "Berkman Hall 146",
     "question": "What would you like to see BSU host this year?"},
    {"slug": "prssa", "name": "Public Relations Student Society of America", "short": "The CSU chapter for students headed into PR and communication.",
     "category": "Academic and professional", "icon": "megaphone", "tone": "green",
     "about": "PRSSA connects students with public relations professionals through speakers, agency tours and portfolio workshops, "
              "and runs fundraisers like its campus thrift sale.",
     "meets": "Second and fourth Tuesdays during common hour", "where": "Music and Communication Building",
     "question": "Which part of communication interests you most?"},
    {"slug": "asl-club", "name": "American Sign Language Club", "short": "Practice ASL and learn about Deaf culture.",
     "category": "Cultural", "icon": "info", "tone": "dark",
     "about": "The ASL Club promotes Deaf awareness and gives signers of every level a relaxed place to practice, "
              "with games, guest speakers and socials.",
     "meets": "Wednesdays, 4 PM", "where": "Rhodes Tower",
     "question": "How much ASL do you know right now?"},
]
CLUB_BY_SLUG = {c["slug"]: c for c in CLUBS}
STANDINGS = ["First year", "Sophomore", "Junior", "Senior", "Graduate student"]
HEARD = ["Student organization fair", "VikesConnect", "A friend", "Social media", "Orientation", "Other"]
AVAILABILITY = ["Common hour (Tuesday and Thursday)", "Weekday afternoons", "Evenings", "Weekends"]


def _events(sid):
    added = {r["source_id"]: r["id"] for r in query_all(
        "SELECT id, source_id FROM events WHERE student_id = ? AND source_id IS NOT NULL", (sid,))}
    out = []
    for e in query_all("SELECT * FROM campus_events ORDER BY event_date, start_time"):
        e = dict(e)
        e["added"] = e["id"] in added
        e["conflicts"] = conflicts_for(sid, e["event_date"], e["start_time"], e["end_time"], ignore_source=e["id"])
        e["common_hour"] = (e["start_time"] < COMMON_HOUR["end"] and COMMON_HOUR["start"] < e["end_time"]
                            and "MTWRFSU"[date.fromisoformat(e["event_date"]).weekday()] in COMMON_HOUR["days"])
        out.append(e)
    return out


def _applications(sid):
    return {r["club"]: r["created_at"] for r in query_all(
        "SELECT club, created_at FROM club_applications WHERE student_id = ?", (sid,))}


@bp.route("/events")
@login_required
def index():
    sid = session["student_id"]
    student = query_one("SELECT * FROM students WHERE student_id = ?", (sid,))
    announcements = query_all("SELECT * FROM announcements ORDER BY posted_on DESC LIMIT 3")
    return render_template(
        "events.html", title="Events and VikesConnect", events=_events(sid), clubs=CLUBS,
        applied=_applications(sid), engagement=ENGAGEMENT, vikesconnect=VIKESCONNECT,
        standings=STANDINGS, heard=HEARD, availability=AVAILABILITY, student=student,
        announcements=announcements, common_hour=COMMON_HOUR,
    )


@bp.route("/api/events/<int:event_id>/schedule", methods=["POST", "DELETE"])
@login_required
def toggle_event(event_id):
    sid = session["student_id"]
    e = query_one("SELECT * FROM campus_events WHERE id = ?", (event_id,))
    if not e:
        abort(404, description="That event isn't available anymore.")
    db = get_db()
    db.execute("DELETE FROM events WHERE student_id = ? AND source_id = ?", (sid, event_id))
    if request.method == "POST":
        db.execute(
            """INSERT INTO events (student_id, kind, title, event_date, start_time, end_time, location, notes, source_id)
               VALUES (?, 'campus', ?, ?, ?, ?, ?, ?, ?)""",
            (sid, e["title"], e["event_date"], e["start_time"], e["end_time"], e["location"], f"Hosted by {e['host']}.", event_id),
        )
    db.commit()
    return jsonify(events=_events(sid))


@bp.route("/api/clubs/<slug>/apply", methods=["POST"])
@login_required
def apply(slug):
    sid = session["student_id"]
    club = CLUB_BY_SLUG.get(slug)
    if not club:
        abort(404, description="That organization isn't listed.")
    if query_one("SELECT 1 FROM club_applications WHERE student_id = ? AND club = ?", (sid, slug)):
        abort(409, description=f"You've already applied to {club['name']}.")
    data = request.get_json(silent=True) or {}
    clean = lambda k, n=600: " ".join(str(data.get(k) or "").split())[:n]
    answers = {
        "major": clean("major", 80), "standing": data.get("standing"), "graduation": clean("graduation", 20),
        "why": clean("why"), "club_answer": clean("club_answer"), "heard": data.get("heard"),
        "availability": [a for a in (data.get("availability") or []) if a in AVAILABILITY],
        "phone": clean("phone", 20),
    }
    if not answers["major"]:
        abort(400, description="Enter your major, or Undecided.")
    if answers["standing"] not in STANDINGS:
        abort(400, description="Choose your class standing.")
    if len(answers["why"]) < 20:
        abort(400, description="Tell the organization a little more about why you want to join (at least 20 characters).")
    if not answers["club_answer"]:
        abort(400, description="Answer the organization's question.")
    if answers["heard"] not in HEARD:
        abort(400, description="Choose how you heard about the organization.")
    if not answers["availability"]:
        abort(400, description="Choose at least one time you're usually free.")
    if not data.get("agree"):
        abort(400, description="Agree to follow the Student Code of Conduct and the organization's constitution.")
    db = get_db()
    db.execute("INSERT INTO club_applications (student_id, club, answers, created_at) VALUES (?, ?, ?, ?)",
               (sid, slug, json.dumps(answers), project_now().isoformat(timespec="minutes")))
    add_alert(sid, "campus", "Application submitted",
              f"Your application to {club['name']} is complete. Officers usually reply through VikesConnect within a week.",
              "check-circle", "events.index")
    db.commit()
    return jsonify(applied=_applications(sid))

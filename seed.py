"""Sample data for Magnus Viking, added the first time the database is created.

The Viking Card history starts with the fall Dining Dollars from the meal plan
and works down through purchases, with a few deposits along the way. The
ending balance is whatever the history adds up to.
"""
import random
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash

from security import password_meets_policy

FALL_START = date(2026, 8, 24)          # first day of fall classes
PROJECT_DAY = date(2026, 11, 12)        # project "today"

MEAL_PLAN = {
    "plan_name": "Block 135 + $250 dining dollars",
    "term": "Fall 2026",
    "semester_rate_cents": 145400,      # 2026-2027 rate, per semester
    "swipes_total": 135,
    "dining_dollars_cents": 25000,
}

# (location, low, high) purchase ranges in dollars
VENDORS = [
    ("Starbucks, Student Center", 3.45, 7.95),
    ("Chick-fil-A, Student Center", 6.29, 12.49),
    ("Viking Express", 2.99, 8.79),
    ("Market on Euclid", 3.25, 14.80),
    ("Hissho Sushi", 9.49, 13.99),
    ("Viking Public House", 11.50, 17.25),
    ("Campus vending", 1.75, 2.75),
]
WEIGHTS = [26, 22, 14, 14, 6, 4, 14]

DEPOSITS = {
    date(2026, 9, 21): (5000, "Online card office deposit"),
    date(2026, 10, 19): (4000, "Online card office deposit"),
    date(2026, 11, 10): (4000, "Online card office deposit"),
}


def seed_all(db, config):
    """Fill each area that is still empty, so a database from an earlier
    phase picks up the new sample data without losing anything."""
    sid = config["SAMPLE_STUDENT_ID"]

    def empty(table, where="student_id = ?", params=(sid,)):
        return db.execute(f"SELECT 1 FROM {table} WHERE {where} LIMIT 1", params).fetchone() is None

    if empty("students"):
        _seed_student(db, config)
    if empty("viking_cards"):
        _seed_card(db, sid)
    if empty("alerts"):
        _seed_alerts(db, sid)
    if empty("pending_updates"):
        _seed_pending_updates(db, sid)
    if empty("announcements", "1 = 1", ()):
        _seed_announcements(db)
    if empty("courses"):
        _seed_courses(db, sid)
    if empty("orientation_tasks", "1 = 1", ()):
        _seed_orientation(db, sid)
    if empty("assignments"):
        _seed_assignments(db, sid)
    if empty("events"):
        _seed_events(db, sid)
    if empty("parking_status", "1 = 1", ()):
        _seed_parking(db)
    if empty("campus_events", "1 = 1", ()):
        _seed_campus_events(db, sid)
    if empty("equipment", "1 = 1", ()):
        _seed_equipment(db, sid)
    if empty("rec_classes", "1 = 1", ()):
        _seed_rec_classes(db)
    if empty("grade_categories"):
        _seed_grades(db, sid)
    if empty("map_pins"):
        db.execute("INSERT INTO map_pins (student_id, code, x, y, label, is_home) VALUES (?, 'FT', 426.9, 216.7, 'Fenn Tower', 1)", (sid,))


def _seed_student(db, config):
    password = config["SAMPLE_PASSWORD"]
    assert password_meets_policy(password), "Sample password must meet policy"
    sid = config["SAMPLE_STUDENT_ID"]
    db.execute(
        """INSERT INTO students (student_id, first_name, last_name, email, password_hash)
           VALUES (?, ?, ?, ?, ?)""",
        (sid, "Magnus", "Viking", f"{sid}@vikes.csuohio.edu", generate_password_hash(password)),
    )


def _at(day, hour, minute):
    return datetime(day.year, day.month, day.day, hour, minute).isoformat(timespec="minutes")


def _seed_card(db, sid):
    rng = random.Random(321)
    rows = []
    balance = MEAL_PLAN["dining_dollars_cents"]
    rows.append((_at(FALL_START - timedelta(days=2), 9, 0), "Fall 2026 dining dollars", "Deposit", balance, balance))
    swipes = 0

    day = FALL_START
    while day <= PROJECT_DAY:
        weekday = day.weekday()  # 0 = Monday
        events = []

        if day in DEPOSITS:
            amount, label = DEPOSITS[day]
            events.append((_at(day, 7, 40), label, "Deposit", amount))

        if weekday < 5:
            # Lunch at the dining hall most weekdays (meal swipe)
            if rng.random() < 0.82 and day != PROJECT_DAY:
                events.append((_at(day, 12, rng.choice([5, 10, 20, 35, 45])), "Viking Marketplace", "Meal swipe", 0))
            # One or two Dining Dollar purchases
            for _ in range(rng.choice([0, 1, 1, 1, 2])):
                loc, lo, hi = rng.choices(VENDORS, WEIGHTS)[0]
                cents = -int(round(rng.uniform(lo, hi), 2) * 100)
                hour = rng.choice([8, 9, 10, 13, 14, 15, 16, 17])
                events.append((_at(day, hour, rng.randrange(0, 60, 3)), loc, "Purchase", cents))
            if day == date(2026, 8, 26):
                events.append((_at(day, 15, 12), "Viking Outfitters Campus Store", "Purchase", -2899))
        elif weekday == 6 and rng.random() < 0.35:
            events.append((_at(day, 18, 30), "Viking Marketplace", "Meal swipe", 0))

        # Project day: keep the morning realistic and recent
        if day == PROJECT_DAY:
            events = [
                (_at(day, 8, 47), "Starbucks, Student Center", "Purchase", -545),
                (_at(day, 11, 58), "Viking Marketplace", "Meal swipe", 0),
                (_at(day, 15, 6), "Campus vending", "Purchase", -200),
            ]

        for when, loc, kind, cents in sorted(events):
            if kind == "Meal swipe":
                swipes += 1
            elif kind == "Purchase" and balance + cents < 500:
                continue  # skip purchases that would overdraw
            balance += cents
            rows.append((when, loc, kind, cents, balance))
        day += timedelta(days=1)

    db.executemany(
        """INSERT INTO card_transactions (student_id, occurred_at, location, txn_type, amount_cents, balance_after_cents)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [(sid, *r) for r in rows],
    )
    db.execute(
        "INSERT INTO viking_cards (student_id, balance_cents, is_locked, issued_on) VALUES (?, ?, 0, ?)",
        (sid, balance, "2026-07-15"),
    )
    db.execute(
        """INSERT INTO meal_plans (student_id, plan_name, term, semester_rate_cents, swipes_total,
                                   swipes_remaining, dining_dollars_cents)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (sid, MEAL_PLAN["plan_name"], MEAL_PLAN["term"], MEAL_PLAN["semester_rate_cents"],
         MEAL_PLAN["swipes_total"], MEAL_PLAN["swipes_total"] - swipes, MEAL_PLAN["dining_dollars_cents"]),
    )


def _seed_alerts(db, sid):
    alerts = [
        ("transportation", "Thanksgiving break parking",
         "Campus is closed November 26 and 27. Check garage hours before you travel.",
         "bus", "transportation.parking", "2026-11-12T07:30"),
        ("schedule", "Class canceled",
         "HIS 211 will not meet on Friday, November 13. Watch Blackboard for updates from Prof. Jadav.",
         "calendar", "schedule.index", "2026-11-11T16:05"),
        ("card", "Viking Card balance updated",
         "A $40.00 deposit was added to your Viking Card.",
         "card", "viking_card.index", "2026-11-10T07:40"),
        ("deadline", "Upcoming assignment deadline",
         "ENG 102: Rhetorical Strategy Handout is due Wednesday, November 25 at 9:00 AM.",
         "clock", "schedule.index", "2026-11-09T09:00"),
        ("campus", "New campus announcement",
         "VikesGiving dinner is at Viking Marketplace on Thursday, November 19.",
         "megaphone", "dashboard.announcements_page", "2026-11-06T10:15"),
        ("orientation", "Orientation task completed",
         "Complete Viking Voyage is marked complete on your orientation checklist.",
         "flag", "orientation.index", "2026-11-03T14:20"),
    ]
    # The two newest arrived since Magnus last opened the app, so they start out new
    db.executemany(
        "INSERT INTO alerts (student_id, category, title, body, icon, link, created_at, seen_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(sid, *a, None if a[5] >= "2026-11-11" else a[5]) for a in alerts],
    )


LIVE_MOMENTS = [  # page, seconds after it opens, category, title, body, icon, link, effect
    ("dashboard.index", 4, "schedule", "Advising appointment confirmed",
     "Your meeting with your academic advisor is Tuesday, November 17 at 11:00 AM in Berkman Hall. It's on your schedule.",
     "calendar", "schedule.index", "advising"),
    ("schedule.index", 8, "schedule", "Class canceled: MTH 116 today",
     "Prof. Moore canceled today's 2:00 PM class. Watch Blackboard for a make-up assignment.",
     "calendar", "schedule.index", "cancel_mth"),
    ("viking_card.index", 6, "card", "Viking Card deposit received",
     "A $25.00 deposit from the Online Card Office was added to your Viking Card.",
     "card", "viking_card.index", "deposit"),
    ("transportation.parking", 6, "transportation", "East Garage closing early tonight",
     "East Garage closes at 9 PM tonight for a Wolstein Center event. Park in South Garage or Central Garage instead.",
     "bus", "transportation.parking", None),
    ("dashboard.announcements_page", 4, "campus", "Spring 2027 registration opens soon",
     "Check your enrollment date in CampusNet and plan your spring classes with your advisor.",
     "megaphone", "dashboard.announcements_page", None),
    ("orientation.index", 5, "orientation", "One orientation step left",
     "Join a student organization to finish orientation. Browse clubs in Events and VikesConnect, then mark the step complete.",
     "flag", "orientation.index", None),
]


def _seed_pending_updates(db, sid):
    """Live moments: each arrives once per launch, a few seconds after its page opens."""
    db.executemany(
        """INSERT INTO pending_updates (student_id, page, delay_seconds, category, title, body, icon, link, effect)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(sid, *m) for m in LIVE_MOMENTS],
    )


def _seed_announcements(db):
    db.executemany(
        "INSERT INTO announcements (category, title, body, icon, posted_on) VALUES (?, ?, ?, ?, ?)",
        [
            ("Dining", "VikesGiving at Viking Marketplace",
             "Students, faculty and staff share a Thanksgiving meal on Thursday, November 19. Meal swipes are accepted.",
             "meal", "2026-11-06"),
            ("Academics", "Spring 2027 registration",
             "Check your enrollment date in CampusNet and meet with your advisor before you register.",
             "calendar", "2026-11-02"),
            ("Campus services", "Thanksgiving break hours",
             "Dining locations, the library and campus offices keep reduced hours during Thanksgiving week.",
             "clock", "2026-10-30"),
            ("Academics", "Finals week is December 7 to 12",
             "Check Blackboard for each final's date and room. Tutoring in Berkman Hall 233 adds evening hours that week.",
             "book", "2026-10-28"),
            ("Campus life", "CABsino returns November 20",
             "The Campus Activities Board's mock casino night fills the Student Center from 7 to 10 PM. Free for CSU students.",
             "ticket", "2026-10-26"),
            ("Getting around", "Spring parking permits on sale December 1",
             "Spring 2027 permits go on sale in the CSU Online Parking System. Permits are limited and can sell out.",
             "bus", "2026-10-22"),
            ("Campus services", "Flu shots at Health and Wellness Services",
             "Walk-in flu shots are available for students in the College of Health building through November.",
             "shield", "2026-10-15"),
        ],
    )


def _seed_courses(db, sid):
    db.executemany(
        """INSERT INTO courses (student_id, code, delivery, days, start_time, end_time, location, professor)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (sid, "IST 203", "Online", None, None, None, None, "Prof. Pfahl"),
            (sid, "ENG 102", "In person", "MWF", "09:00", "09:50", "Monte Ahuja College of Business 206", "Prof. Hayes"),
            (sid, "BIO 100", "In person", "TR", "09:30", "10:45", "Science and Research Center 155", "Prof. Drzal"),
            (sid, "HIS 211", "In person", "MWF", "12:30", "13:20", "Berkman Hall 433", "Prof. Jadav"),
            (sid, "MTH 116", "In person", "TR", "14:00", "15:15", "Rhodes Tower 1260", "Prof. Moore"),
        ],
    )


# ---------------------------------------------------------------------------
# Orientation. Required steps are updated by CSU, so they start complete.
# Recommended steps are the ones the student marks in Viking Hub.
# ---------------------------------------------------------------------------
ORIENTATION_TASKS = [
    # category, title, description, requirement, link label, link, status
    # Steps are in the order CSU walks new students through them. Required steps are updated by CSU;
    # the recommended steps in Campus life are the only ones a student marks. Everything starts complete
    # except the last step, so finishing orientation takes one click.
    ("Admissions and enrollment", "Accept your offer of admission",
     "Say yes to CSU in your applicant status page so the university knows you plan to enroll.",
     "Required", "CSU welcome page", "https://www.csuohio.edu/welcome", "Complete"),
    ("Admissions and enrollment", "Pay or defer your enrollment fee",
     "First-year students pay the $120 enrollment fee, or request a deferral, before signing up for orientation.",
     "Required", "Next steps for new Vikings", "https://www.csuohio.edu/welcome-vikes", "Complete"),
    ("Admissions and enrollment", "Set up CampusNet and your CSU email",
     "Sign in to CampusNet with your CSU ID. Your email address is your CSU ID followed by @vikes.csuohio.edu.",
     "Required", "CampusNet", "https://campusnet.csuohio.edu/", "Complete"),
    ("Financial aid", "Submit your FAFSA",
     "The Free Application for Federal Student Aid is required to receive federal grants and loans. CSU receives your results directly once it's processed.",
     "Required", "studentaid.gov", "https://studentaid.gov/", "Complete"),
    ("Orientation", "Take your placement test",
     "After you register for orientation, take your math placement test so you can be placed in the right courses.",
     "Required", "Things to do before you start", "https://www.csuohio.edu/welcome/things-do", "Complete"),
    ("Orientation", "Attend New Student Orientation",
     "Orientation is mandatory for new students. The registration hold on your record is removed when you attend.",
     "Required", "Orientation", "https://www.csuohio.edu/orientation/orientation", "Complete"),
    ("Orientation", "Get your Viking Card",
     "Your Viking Card is your official CSU ID. You'll use it for meals, printing, building access and borrowing equipment.",
     "Required", "Viking Card", "viking_card.index", "Complete"),
    ("Orientation", "Complete Viking Voyage",
     "A free online course in Blackboard that introduces CSU's services, tools and resources. It's mandatory for all incoming students.",
     "Required", "Viking Voyage", "https://www.csuohio.edu/fye/viking-voyage", "Complete"),
    ("Academics", "Meet with your academic advisor",
     "New students meet with an advisor before registering. Use Starfish to see your Success Network and book appointments.",
     "Required", "Starfish", "https://www.csuohio.edu/successprograms/starfish-student", "Complete"),
    ("Academics", "Register for your classes",
     "Check your enrollment date in CampusNet and register once you've planned your schedule with your advisor.",
     "Required", "CampusNet", "https://campusnet.csuohio.edu/", "Complete"),
    ("Campus life", "Learn your way around campus",
     "Find your classrooms, the Student Center and the offices you'll visit most on the campus map.",
     "Recommended", "Campus map", "campus_map.index", "Complete"),
    ("Campus life", "Plan how you'll get to campus",
     "Compare parking permits, RTA routes and other ways to get to class.",
     "Recommended", "Plan a trip", "transportation.trip", "Complete"),
    ("Campus life", "Join a student organization",
     "Browse clubs in Events and VikesConnect and apply to one that fits your interests. Many meet during common hour.",
     "Recommended", "Student organizations", "events.index", "Not started"),
]


def _seed_orientation(db, sid):
    for i, (cat, title, desc, req, label, link, status) in enumerate(ORIENTATION_TASKS):
        cur = db.execute(
            """INSERT INTO orientation_tasks (position, category, title, description, requirement, link_label, link_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (i, cat, title, desc, req, label, link),
        )
        db.execute(
            "INSERT INTO orientation_progress (student_id, task_id, status) VALUES (?, ?, ?)",
            (sid, cur.lastrowid, status),
        )


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------
def _seed_assignments(db, sid):
    rows = [
        # Earlier in the semester (already turned in)
        ("ENG 102", "Personal narrative essay", "2026-09-18", "09:00", 1),
        ("BIO 100", "Lab report 1", "2026-09-24", "09:30", 1),
        ("HIS 211", "Chapter 3 reading quiz", "2026-10-02", "23:59", 1),
        ("IST 203", "Module 4 assignment", "2026-10-11", "23:59", 1),
        ("ENG 102", "Annotated bibliography", "2026-10-21", "09:00", 1),
        ("BIO 100", "Midterm exam", "2026-10-22", "09:30", 1),
        ("IST 203", "Module 8 quiz", "2026-11-08", "23:59", 1),
        # Coming up (the first two are from the project specification)
        ("ENG 102", "Rhetorical Strategy Handout", "2026-11-25", "09:00", 0),
        ("HIS 211", "Chapter 7 Reading", "2026-11-27", "23:59", 0),
        ("BIO 100", "Lab report 5", "2026-12-03", "09:30", 0),
        ("IST 203", "Final project", "2026-12-06", "23:59", 0),
        ("HIS 211", "Final paper", "2026-12-09", "23:59", 0),
        ("ENG 102", "Final portfolio", "2026-12-11", "09:00", 0),
    ]
    db.executemany(
        "INSERT INTO assignments (student_id, course_code, title, due_date, due_time, completed) VALUES (?, ?, ?, ?, ?, ?)",
        [(sid, *r) for r in rows],
    )
    # Days with no class: HIS 211 on Nov 13 (matches the "Class canceled" alert),
    # plus Labor Day and Thanksgiving break, when campus is closed.
    courses = {r[1]: r[0] for r in db.execute("SELECT id, code FROM courses WHERE student_id = ?", (sid,))}
    closed = ["2026-09-07", "2026-11-26", "2026-11-27"]
    rows = [(courses["HIS 211"], "2026-11-13")] if "HIS 211" in courses else []
    rows += [(cid, d) for cid in courses.values() for d in closed]
    db.executemany("INSERT OR IGNORE INTO class_cancellations (course_id, class_date) VALUES (?, ?)", rows)


def _weekly(first, last, weekday, skip=()):
    """Dates from first to last that fall on weekday (0 = Monday)."""
    d = date.fromisoformat(first)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    end = date.fromisoformat(last)
    while d <= end:
        if d.isoformat() not in skip:
            yield d.isoformat()
        d += timedelta(days=7)


def _seed_events(db, sid):
    rows = []
    # Recurring personal plans across the semester
    for d in _weekly("2026-08-28", "2026-12-11", 4, skip=("2026-11-27",)):
        rows.append(("Work shift", d, "13:30", "17:30", "Viking Outfitters, Student Center", None))
    for d in _weekly("2026-08-31", "2026-12-07", 0, skip=("2026-09-07",)):
        rows.append(("Lift at the Rec Center", d, "18:00", "19:00", "Recreation Center", None))
    for d in _weekly("2026-10-07", "2026-11-18", 2):
        rows.append(("Intramural basketball", d, "20:00", "21:00", "Recreation Center", None))
    # One-time plans
    rows += [
        ("Move-in day", "2026-08-22", "10:00", "14:00", "Fenn Tower", "Pick up keys at the front desk."),
        ("Buy textbooks", "2026-08-26", "15:00", "15:30", "Viking Outfitters, Student Center", None),
        ("Call with financial aid", "2026-09-04", "11:00", "11:30", "Berkman Hall", "Ask about spring aid."),
        ("Cedar Point trip with friends", "2026-09-19", None, None, "Sandusky", None),
        ("Dinner with family", "2026-09-26", "17:00", "19:00", None, None),
        ("BIO 100 exam study session", "2026-10-20", "18:00", "20:00", "Michael Schwartz Library", None),
        ("Haircut", "2026-10-10", "11:00", "11:45", None, None),
        ("HIS 211 study group", "2026-10-16", "15:00", "17:00", "Michael Schwartz Library", None),
        ("Halloween party", "2026-10-31", "20:00", "23:00", "Langston", None),
        ("Flu shot", "2026-11-04", "10:00", "10:20", "Health and Wellness Services, College of Health", None),
        ("BIO 100 study group", "2026-11-12", "16:00", "17:30", "Michael Schwartz Library",
         "Review chapters 9 and 10 before the quiz."),
        ("Advising appointment", "2026-11-17", "11:00", "11:30", "Berkman Hall",
         "Bring questions about spring 2027 classes."),
        ("Dentist appointment", "2026-11-19", "15:00", "16:00", None, None),
        ("Movie night with roommates", "2026-11-20", "19:30", "22:00", "Fenn Tower", None),
        ("Dinner with family", "2026-11-22", "17:00", "19:00", None, None),
        ("Drive home for Thanksgiving", "2026-11-25", "15:00", "16:30", None, None),
        ("Thanksgiving", "2026-11-26", None, None, None, None),
        ("IST 203 project meeting", "2026-12-02", "18:00", "19:30", "Student Center", None),
        ("Holiday shopping", "2026-12-05", "13:00", "16:00", None, None),
        ("BIO 100 final review", "2026-12-09", "17:00", "19:00", "Michael Schwartz Library", None),
        ("End of semester dinner", "2026-12-12", "19:00", "21:00", None, None),
    ]
    db.executemany(
        """INSERT INTO events (student_id, kind, title, event_date, start_time, end_time, location, notes)
           VALUES (?, 'personal', ?, ?, ?, ?, ?, ?)""",
        [(sid, *r) for r in rows],
    )


# ---------------------------------------------------------------------------
# Transportation: estimated open spaces at midday on November 12 (sample data)
# ---------------------------------------------------------------------------
PARKING = [  # code, capacity, open spaces
    ("WG", 1050, 212), ("CG", 820, 64), ("MG", 760, 18), ("UG", 410, 41), ("EG", 960, 305),
    ("SG", 1300, 640), ("PG", 600, 118), ("L13", 150, 22), ("L14", 160, 37), ("L20", 120, 6),
    ("L27", 90, 15), ("L40", 220, 90),
]


def _seed_parking(db):
    db.executemany("INSERT INTO parking_status (code, capacity, available, updated_at) VALUES (?, ?, ?, '2026-11-12T12:05')",
                   PARKING)


# ---------------------------------------------------------------------------
# Events: campus events and club meetings for the rest of the semester (sample data)
# ---------------------------------------------------------------------------
CAMPUS_EVENTS = [  # title, host, category, date, start, end, location, description
    ("Common hour trivia", "Campus Activities Board", "Campus event", "2026-11-12", "11:30", "12:30",
     "Student Center Atrium", "Teams of up to four play three rounds of campus and pop culture trivia. Free pizza while it lasts."),
    ("Study abroad info session", "Center for International Education", "Campus event", "2026-11-13", "12:30", "13:30",
     "Student Center 315", "Hear where CSU students study abroad, what it costs and how to apply for spring and summer programs."),
    ("Resume review drop-in", "Career Development and Exploration", "Campus event", "2026-11-16", "13:00", "14:30",
     "Student Center Atrium", "Bring a printed or digital resume and get quick feedback from a career specialist."),
    ("SWE coffee hour", "Society of Women Engineers", "Club meeting", "2026-11-17", "11:30", "12:30",
     "Washkewicz Hall", "Coffee, tea and games with the Society of Women Engineers. A relaxed way to meet people in engineering."),
    ("Vikings men's basketball home game", "Cleveland State Athletics", "Athletics", "2026-11-17", "19:00", "21:00",
     "Wolstein Center", "Cheer on the Vikings with the student section. Students get in free with a Viking Card."),
    ("De-stress with therapy dogs", "Student Wellness Programs", "Campus event", "2026-11-18", "12:00", "14:00",
     "Student Center Atrium", "Take a break before finals with certified therapy dogs and free snacks."),
    ("Campus Activities Board general meeting", "Campus Activities Board", "Club meeting", "2026-11-19", "11:30", "12:30",
     "Student Center 313", "Help plan CABsino and the end-of-semester events. New members welcome."),
    ("VikesGiving", "CSU Dining", "Campus event", "2026-11-19", "12:30", "14:00",
     "Viking Marketplace", "Students, faculty and staff share a Thanksgiving meal. Meal swipes are accepted."),
    ("CABsino", "Campus Activities Board", "Campus event", "2026-11-20", "19:00", "22:00",
     "Student Center", "The annual mock casino night with games, prizes, live music and food. Free for CSU students."),
    ("Esports open play", "Cleveland State Esports", "Club meeting", "2026-11-24", "11:30", "12:30",
     "Esports lab, Washkewicz Hall", "Drop in and play during common hour. No experience or tryout needed."),
    ("Black Student Union general meeting", "Black Student Union", "Club meeting", "2026-12-01", "11:30", "12:30",
     "Berkman Hall 146", "Plans for the spring semester and a holiday food drive."),
    ("Finals prep workshop", "Academic Support Hub", "Campus event", "2026-12-02", "15:00", "16:00",
     "Berkman Hall 233", "Build a study plan for finals week and learn which tutoring is available."),
    ("PRSSA networking hour", "Public Relations Student Society of America", "Club meeting", "2026-12-03", "11:30", "12:30",
     "Music and Communication Building", "Meet local public relations professionals and bring your questions about internships."),
    ("Winter lights at the Student Center", "Campus Activities Board", "Campus event", "2026-12-04", "17:00", "19:00",
     "Student Center Plaza", "Hot chocolate, music and the lighting of the plaza for the holidays."),
    ("Midnight breakfast", "Campus Activities Board", "Campus event", "2026-12-08", "21:00", "23:00",
     "Student Center Atrium", "Free late-night breakfast served by faculty and staff during finals week."),
    ("ASL Club holiday social", "American Sign Language Club", "Club meeting", "2026-12-10", "11:30", "12:30",
     "Rhodes Tower", "Games and practice for signers of every level."),
]
ADDED_EVENTS = ("Common hour trivia", "CABsino", "Vikings men's basketball home game")  # already on Magnus's schedule


def _seed_campus_events(db, sid):
    for row in CAMPUS_EVENTS:
        cur = db.execute(
            """INSERT INTO campus_events (title, host, category, event_date, start_time, end_time, location, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", row)
        if row[0] in ADDED_EVENTS:
            db.execute(
                """INSERT INTO events (student_id, kind, title, event_date, start_time, end_time, location, notes, source_id)
                   VALUES (?, 'campus', ?, ?, ?, ?, ?, ?, ?)""",
                (sid, row[0], row[3], row[4], row[5], row[6], f"Hosted by {row[1]}.", cur.lastrowid),
            )


# ---------------------------------------------------------------------------
# Mobile Campus: inventory (sample counts) and Magnus's calculator loan
# ---------------------------------------------------------------------------
EQUIPMENT = [  # name, kind, description, total, available, kept for 7 day loans
    ("HP laptop", "Laptop", "Windows laptop with Microsoft Office and the same software as the campus computer labs. Comes with a charger and an optional bag.", 120, 14, 4),
    ("MacBook Air", "Laptop", "macOS laptop with Microsoft Office and standard campus software. Comes with a charger and an optional bag.", 60, 3, 1),
    ("TI-84 graphing calculator", "Calculator", "Graphing calculator for math, statistics and science courses.", 80, 22, 6),
    ("TI-30XS scientific calculator", "Calculator", "Scientific calculator for chemistry, physics and general math.", 50, 0, 0),
]


def _seed_equipment(db, sid):
    ids = {}
    for row in EQUIPMENT:
        ids[row[0]] = db.execute(
            "INSERT INTO equipment (name, kind, description, total, available, seven_day) VALUES (?, ?, ?, ?, ?, ?)", row).lastrowid
    db.execute(
        """INSERT INTO equipment_requests (student_id, equipment_id, loan_type, pickup_date, due_date, status, created_at)
           VALUES (?, ?, 'Semester', '2026-08-25', '2026-12-12', 'Checked out', '2026-08-24T10:15')""",
        (sid, ids["TI-84 graphing calculator"]))


# ---------------------------------------------------------------------------
# Grade tracker: sample syllabus weights and scores. Items with no score are still to come.
# ---------------------------------------------------------------------------
GRADEBOOK = {
    "ENG 102": [
        ("Essays", 45, [("Personal narrative essay", 88, 100, "2026-09-18"), ("Annotated bibliography", 84, 100, "2026-10-21"),
                        ("Researched argument essay", None, 100, "2026-12-04")]),
        ("Handouts", 20, [("Thesis workshop handout", 9, 10, "2026-09-30"), ("Source evaluation handout", 10, 10, "2026-10-14"),
                          ("Rhetorical Strategy Handout", None, 10, "2026-11-25")]),
        ("Participation", 10, [("Participation through November", 46, 50, None)]),
        ("Final portfolio", 25, [("Final portfolio", None, 100, "2026-12-11")]),
    ],
    "BIO 100": [
        ("Exams", 40, [("Midterm exam", 78, 100, "2026-10-22"), ("Final exam", None, 100, "2026-12-10")]),
        ("Lab reports", 30, [("Lab report 1", 18, 20, "2026-09-24"), ("Lab report 2", 17, 20, "2026-10-08"),
                             ("Lab report 3", 19, 20, "2026-10-29"), ("Lab report 4", 16, 20, "2026-11-12"),
                             ("Lab report 5", None, 20, "2026-12-03")]),
        ("Quizzes", 20, [("Quiz 1", 8, 10, "2026-09-10"), ("Quiz 2", 9, 10, "2026-10-01"), ("Quiz 3", 7, 10, "2026-11-05"),
                         ("Quiz 4", None, 10, "2026-11-19")]),
        ("Participation", 10, [("Participation through November", 45, 50, None)]),
    ],
    "HIS 211": [
        ("Reading quizzes", 25, [("Chapter 3 reading quiz", 9, 10, "2026-10-02"), ("Chapter 5 reading quiz", 8, 10, "2026-10-23"),
                                 ("Chapter 7 Reading", None, 10, "2026-11-27")]),
        ("Midterm exam", 25, [("Midterm exam", 81, 100, "2026-10-16")]),
        ("Final paper", 30, [("Final paper", None, 100, "2026-12-09")]),
        ("Participation", 20, [("Participation through November", 43, 50, None)]),
    ],
    "IST 203": [
        ("Module assignments", 40, [("Module 2 assignment", 47, 50, "2026-09-20"), ("Module 4 assignment", 45, 50, "2026-10-11"),
                                    ("Module 6 assignment", 49, 50, "2026-10-25")]),
        ("Quizzes", 20, [("Module 5 quiz", 18, 20, "2026-10-18"), ("Module 8 quiz", 17, 20, "2026-11-08")]),
        ("Final project", 40, [("Final project", None, 100, "2026-12-06")]),
    ],
}


def _seed_grades(db, sid):
    # Magnus already set up each course from its syllabus, so these count as his own sections
    for course in GRADEBOOK:
        db.execute("INSERT INTO grade_courses (student_id, course_code, customized) VALUES (?, ?, 1)", (sid, course))
    for course, categories in GRADEBOOK.items():
        for pos, (name, weight, items) in enumerate(categories):
            cur = db.execute(
                "INSERT INTO grade_categories (student_id, course_code, name, weight, position) VALUES (?, ?, ?, ?, ?)",
                (sid, course, name, weight, pos))
            db.executemany(
                "INSERT INTO grade_items (category_id, title, earned, possible, due_date) VALUES (?, ?, ?, ?, ?)",
                [(cur.lastrowid, *item) for item in items])


# ---------------------------------------------------------------------------
# Rec Center group fitness: a sample weekly schedule using class types the Rec offers
# ---------------------------------------------------------------------------
REC_TYPES = {
    "Functional HIIT": ("Studio 1", 45, "Short, hard intervals with bodyweight and light equipment. Every level welcome."),
    "Cycling": ("Cycling studio", 45, "An indoor ride set to music, with climbs and sprints you set at your own pace."),
    "Zumba": ("Studio 2", 45, "Dance-based cardio with Latin and pop music. No dance experience needed."),
    "Power Yoga": ("Studio 1", 45, "A flowing, strength-focused yoga class. Mats are provided."),
    "Barre": ("Studio 2", 45, "Ballet-inspired strength and balance work with small, focused movements."),
    "Pilates": ("Studio 1", 45, "Core strength, posture and control on the mat."),
    "Water aerobics": ("Natatorium", 45, "Low-impact cardio in the shallow end of the pool."),
}
REC_WEEK = [  # weekday, start, class
    (0, "07:00", "Functional HIIT"), (0, "12:10", "Cycling"), (0, "17:30", "Zumba"), (0, "18:30", "Power Yoga"),
    (1, "07:00", "Cycling"), (1, "11:40", "Barre"), (1, "17:30", "Functional HIIT"), (1, "18:30", "Pilates"),
    (2, "07:00", "Functional HIIT"), (2, "12:10", "Water aerobics"), (2, "17:30", "Cycling"), (2, "18:30", "Zumba"),
    (3, "07:00", "Cycling"), (3, "11:40", "Power Yoga"), (3, "17:30", "Barre"), (3, "18:30", "Functional HIIT"),
    (4, "07:00", "Pilates"), (4, "12:10", "Functional HIIT"), (4, "16:00", "Zumba"),
    (5, "10:00", "Cycling"), (5, "11:00", "Power Yoga"),
    (6, "13:00", "Pilates"),
]


def _seed_rec_classes(db):
    db.executemany(
        "INSERT INTO rec_classes (weekday, start_time, minutes, name, room, description) VALUES (?, ?, ?, ?, ?, ?)",
        [(wd, start, REC_TYPES[name][1], name, REC_TYPES[name][0], REC_TYPES[name][2]) for wd, start, name in REC_WEEK])

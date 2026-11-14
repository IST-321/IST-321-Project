-- CSU Viking Hub database schema (SQLite)
-- Tables use IF NOT EXISTS so the schema can be re-applied safely as new
-- sections are added. Money is stored as integer cents.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    student_id      TEXT PRIMARY KEY CHECK (length(student_id) = 7),
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    email           TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    remember_me     INTEGER NOT NULL DEFAULT 0,
    last_login_at   TEXT,
    app_date        TEXT,                   -- the day the app shows as today, when the student moved it
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Alerts shown in the horn panel and on the home screen
CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    category        TEXT NOT NULL,          -- card, schedule, campus, orientation, deadline, transportation
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    icon            TEXT NOT NULL,
    link            TEXT NOT NULL,          -- Flask endpoint, optionally with #anchor
    actions         TEXT,                   -- optional buttons, comma separated: add_funds, lock_card
    created_at      TEXT NOT NULL,
    seen_at         TEXT,                   -- set when the student closes the alerts list after seeing it
    cleared_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_alerts_student ON alerts(student_id, cleared_at);

-- Live moments: an alert that arrives a few seconds after the student opens a certain page,
-- once per launch of the app (handy for showing alerts arriving during a presentation)
CREATE TABLE IF NOT EXISTS pending_updates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    page            TEXT NOT NULL,          -- Flask endpoint of the page that triggers it
    delay_seconds   INTEGER NOT NULL,       -- how long after the page opens
    category        TEXT NOT NULL,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    icon            TEXT NOT NULL,
    link            TEXT NOT NULL,
    effect          TEXT,                   -- what changes along with the alert, if anything
    delivered       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS announcements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT NOT NULL DEFAULT 'Campus life',
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    icon            TEXT NOT NULL,
    posted_on       TEXT NOT NULL
);

-- Viking Card
CREATE TABLE IF NOT EXISTS viking_cards (
    student_id      TEXT PRIMARY KEY REFERENCES students(student_id) ON DELETE CASCADE,
    balance_cents   INTEGER NOT NULL DEFAULT 0 CHECK (balance_cents >= 0),
    is_locked       INTEGER NOT NULL DEFAULT 0,
    locked_at       TEXT,
    issued_on       TEXT NOT NULL,
    low_alert_cents INTEGER NOT NULL DEFAULT 1000,  -- alert when the balance drops below this; 0 = off
    low_alerted     INTEGER NOT NULL DEFAULT 0      -- 1 once the low balance alert was sent, until funds are added
);

CREATE TABLE IF NOT EXISTS card_transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id          TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    occurred_at         TEXT NOT NULL,
    location            TEXT NOT NULL,
    txn_type            TEXT NOT NULL CHECK (txn_type IN ('Deposit', 'Purchase', 'Meal swipe')),
    amount_cents        INTEGER NOT NULL,   -- positive for deposits, negative for purchases, 0 for swipes
    balance_after_cents INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_txn_student ON card_transactions(student_id, occurred_at);

CREATE TABLE IF NOT EXISTS meal_plans (
    student_id          TEXT PRIMARY KEY REFERENCES students(student_id) ON DELETE CASCADE,
    plan_name           TEXT NOT NULL,
    term                TEXT NOT NULL,
    semester_rate_cents INTEGER NOT NULL,
    swipes_total        INTEGER NOT NULL,
    swipes_remaining    INTEGER NOT NULL,
    dining_dollars_cents INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS card_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    request_type    TEXT NOT NULL,
    reason          TEXT NOT NULL,
    details         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Saved',
    created_at      TEXT NOT NULL
);

-- Classes (expanded in the schedule phase)
CREATE TABLE IF NOT EXISTS courses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    code            TEXT NOT NULL,
    delivery        TEXT NOT NULL CHECK (delivery IN ('In person', 'Online')),
    days            TEXT,                   -- e.g. MWF, TR
    start_time      TEXT,                   -- HH:MM, 24-hour
    end_time        TEXT,
    location        TEXT,
    professor       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'Enrolled'
);

-- Orientation checklist
CREATE TABLE IF NOT EXISTS orientation_tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    position        INTEGER NOT NULL,
    category        TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    requirement     TEXT NOT NULL,          -- Required, Recommended
    link_label      TEXT,
    link_url        TEXT                    -- a full URL, or a Flask endpoint for pages inside Viking Hub
);

CREATE TABLE IF NOT EXISTS orientation_progress (
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    task_id         INTEGER NOT NULL REFERENCES orientation_tasks(id) ON DELETE CASCADE,
    status          TEXT NOT NULL CHECK (status IN ('Not started', 'In progress', 'Complete')),
    updated_at      TEXT,
    PRIMARY KEY (student_id, task_id)
);

-- Schedule
CREATE TABLE IF NOT EXISTS class_cancellations (
    course_id       INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    class_date      TEXT NOT NULL,
    PRIMARY KEY (course_id, class_date)
);

CREATE TABLE IF NOT EXISTS assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    course_code     TEXT NOT NULL,
    title           TEXT NOT NULL,
    due_date        TEXT NOT NULL,          -- YYYY-MM-DD
    due_time        TEXT NOT NULL,          -- HH:MM, 24-hour
    completed       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    kind            TEXT NOT NULL CHECK (kind IN ('personal', 'campus', 'imported')),
    title           TEXT NOT NULL,
    event_date      TEXT NOT NULL,          -- YYYY-MM-DD
    start_time      TEXT,                   -- HH:MM, empty for all-day
    end_time        TEXT,
    location        TEXT,
    notes           TEXT,
    source_id       INTEGER REFERENCES campus_events(id) ON DELETE SET NULL  -- set when added from Events
);

-- Campus map pins (a building pin has a code; a dropped pin has x/y map coordinates)
CREATE TABLE IF NOT EXISTS map_pins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    code            TEXT,
    x               REAL NOT NULL,
    y               REAL NOT NULL,
    label           TEXT NOT NULL,
    is_home         INTEGER NOT NULL DEFAULT 0,   -- where Leave by walks start each day
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- Phase 4: transportation, events, Mobile Campus and Lift Up Vikes
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parking_status (
    code            TEXT PRIMARY KEY,       -- garage or lot code, e.g. CG, L20
    capacity        INTEGER NOT NULL,
    available       INTEGER NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transport_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    category        TEXT NOT NULL,
    location        TEXT NOT NULL,
    description     TEXT NOT NULL,
    details         TEXT,
    status          TEXT NOT NULL DEFAULT 'Under review',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campus_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    host            TEXT NOT NULL,
    category        TEXT NOT NULL CHECK (category IN ('Campus event', 'Club meeting', 'Athletics')),
    event_date      TEXT NOT NULL,
    start_time      TEXT NOT NULL,
    end_time        TEXT NOT NULL,
    location        TEXT NOT NULL,
    description     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS club_applications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    club            TEXT NOT NULL,          -- club slug from routes/events.py
    answers         TEXT NOT NULL,          -- JSON
    created_at      TEXT NOT NULL,
    UNIQUE (student_id, club)
);

CREATE TABLE IF NOT EXISTS equipment (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL,
    description     TEXT NOT NULL,
    total           INTEGER NOT NULL,
    available       INTEGER NOT NULL,
    seven_day       INTEGER NOT NULL        -- units kept for 7 day loans
);

CREATE TABLE IF NOT EXISTS equipment_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    equipment_id    INTEGER NOT NULL REFERENCES equipment(id),
    loan_type       TEXT NOT NULL CHECK (loan_type IN ('Semester', '7 day')),
    pickup_date     TEXT NOT NULL,
    due_date        TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('Requested', 'Checked out', 'Canceled', 'Returned')),
    note            TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pantry_appointments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    appt_date       TEXT NOT NULL,
    appt_time       TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('Booked', 'Canceled')),
    created_at      TEXT NOT NULL
);

-- Grade tracker: syllabus categories and the scores inside them (sample data; official grades live in CampusNet)
CREATE TABLE IF NOT EXISTS grade_categories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    course_code     TEXT NOT NULL,
    name            TEXT NOT NULL,
    weight          INTEGER NOT NULL CHECK (weight > 0),   -- percent of the course grade
    position        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS grade_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id     INTEGER NOT NULL REFERENCES grade_categories(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    earned          REAL,                   -- empty until it's graded
    possible        REAL NOT NULL CHECK (possible > 0),
    due_date        TEXT
);

-- Per-course grade setup: whether the student changed the standard sections, and the letter scale they use
CREATE TABLE IF NOT EXISTS grade_courses (
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    course_code     TEXT NOT NULL,
    customized      INTEGER NOT NULL DEFAULT 0,  -- 1 once the student edits the sections or the scale
    scale           TEXT,                        -- JSON [["A", 93], ...]; empty = the standard scale
    PRIMARY KEY (student_id, course_code)
);

-- Settings the student chose (reset with everything else when the app restarts)
CREATE TABLE IF NOT EXISTS settings (
    student_id      TEXT PRIMARY KEY REFERENCES students(student_id) ON DELETE CASCADE,
    text_size       TEXT NOT NULL DEFAULT 'default' CHECK (text_size IN ('default', 'large', 'larger')),
    alerts_off      TEXT NOT NULL DEFAULT '',    -- comma separated alert categories turned off
    sound_horn      INTEGER NOT NULL DEFAULT 1,
    sound_war_cry   INTEGER NOT NULL DEFAULT 1,
    reduce_motion   INTEGER NOT NULL DEFAULT 0
);

-- Book a space: library rooms reserved in Viking Hub, and Rec Center group fitness classes
CREATE TABLE IF NOT EXISTS room_bookings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    room            TEXT NOT NULL,          -- room id from routes/spaces.py
    unit            INTEGER NOT NULL DEFAULT 1,   -- which of several identical rooms (video conference rooms)
    book_date       TEXT NOT NULL,
    start_time      TEXT NOT NULL,
    end_time        TEXT NOT NULL,
    details         TEXT,                   -- course and instructor for the presentation practice room
    event_id        INTEGER REFERENCES events(id) ON DELETE SET NULL,
    status          TEXT NOT NULL DEFAULT 'Reserved',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rec_classes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    weekday         INTEGER NOT NULL,       -- 0 = Monday
    start_time      TEXT NOT NULL,
    minutes         INTEGER NOT NULL,
    name            TEXT NOT NULL,
    room            TEXT NOT NULL,
    description     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rec_signups (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    class_id        INTEGER NOT NULL REFERENCES rec_classes(id),
    class_date      TEXT NOT NULL,
    event_id        INTEGER REFERENCES events(id) ON DELETE SET NULL
);

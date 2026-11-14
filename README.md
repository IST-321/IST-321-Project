# CSU Viking Hub

A student services website for Cleveland State University students, built with Flask, HTML, CSS, JavaScript and SQLite.

## Run it

1. Open this folder in VS Code.
2. Open a terminal (**Terminal → New Terminal**) and install Flask once:

   ```
   pip install -r requirements.txt
   ```

3. Start the site:

   ```
   python app.py
   ```

4. Open http://127.0.0.1:5000 in your browser.

To check that Flask installed correctly, run `python -m flask --version`.

## Sign in

| CSU ID  | Password   |
|---------|------------|
| 2000000 | Vikes2026! |

## Project layout

```
app.py              App setup, services list, error pages
config.py           Settings
db.py               SQLite connection and schema setup
seed.py             Sample data for Magnus Viking (loaded fresh on every launch)
alerts.py           Alert helpers shared by every section
formatting.py       Money and date formatting
security.py         Login rules, login_required, CSRF protection
database/schema.sql Tables (database file is created on first run)
routes/             One blueprint per section
templates/          Jinja templates (base.html is the shared layout)
static/css          style.css (mobile first) and responsive.css
static/js           main.js plus one script per interactive page
static/images       CSU logos and Viking artwork
static/audio        Optional sound files (see README.txt there)
```

The database at `database/viking_hub.db` is rebuilt from `seed.py` every time the app starts, so every launch begins with the same alerts, balances and data. Changes made while it runs (including across sign outs) last until the app is stopped.

## Pages

- **Home**: welcome with a change day button, orientation progress, Viking Card, today's schedule in order (with walking times and what's next), alerts and announcements
- **Alerts and Announcements**: new alerts are highlighted until you close the list; both can be filtered
- **Orientation** (becomes **Resources** once complete), **Viking Card**, **Schedule**, **Campus map**
- **Events and VikesConnect**, **Mobile Campus**, **Lift Up Vikes**
- **Getting around**: Parking garages and permits, Plan a trip, Viking Safety Escorts, Report an issue
- **Schedule** has Planner and Grades tabs, plus calendar files (Blackboard import and .ics export)
- **Book a space**: Michael Schwartz Library rooms and Rec Center group fitness
- **Settings** (from the profile menu): text size, alert types, sounds and motion
- **Search**: the box in the top bar, or press / or Ctrl+K anywhere

## Optional files

- `static/audio/horn.mp3` and `static/audio/war-cry.mp3`: sounds for the alerts horn and finishing orientation.

## Notes

- Integrations with CSU systems (CampusNet, Blackboard, Viking Card office and others) are simulated with sample data. The site links to the official services and does not connect to them.
- Passwords are stored as salted hashes (Werkzeug), never in plain text.
- "Remember me" saves only the CSU ID, and only for the current launch of the app.
- Parking space counts, club meeting details, campus events, equipment counts, pantry turns, grade scores, Rec class times and crowd levels, and other students' room reservations are sample data.
- **Change day** previews another day from November 12 to December 12. Things tied to the real day (tap to pay, deposits, Mobile Campus requests, bookings past their window and parking counts) stay locked to November 12 while previewing.
- Walking times are estimates measured on the campus map: about 3 mph plus a 2 minute buffer. After a break of more than 30 minutes, the next walk starts from the Home pin.

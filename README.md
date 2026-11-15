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
| 2000001 | Vikes2026! |
| 2000002 | Vikes2026! |
| 2000003 | Vikes2026! |

Every ID signs in as Magnus Viking with his full sample data, but each one keeps its own copy.
Clearing alerts, spending, bookings and other changes under one ID never show up under another.
The extra IDs are listed in `EXTRA_STUDENT_IDS` in `config.py`.

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
- **Parking near my class** (top of the Parking page, and a Parking button on each in-person class and in each building's map popup): the closest garages your permit allows at class time, with the walk, open spaces and the route drawn on the campus map
- **Schedule** has Planner and Grades tabs, plus calendar files (Blackboard import and .ics export)
- **Book a space**: Michael Schwartz Library rooms and Rec Center group fitness
- **Settings** (from the profile menu): text size, alert types, sounds and motion
- **Search**: the box in the top bar, or press / or Ctrl+K anywhere

## Live moments (for presenting)

Some pages get a new alert a few seconds after you open them, once per launch of the app: Home (4 s, advising appointment), Schedule (8 s, MTH 116 canceled today), Viking Card (6 s, $25 deposit), Parking (6 s, East Garage closing early), Announcements (4 s) and Orientation (5 s). The horn shakes, a card slides in, and the page updates. Edit the list in `LIVE_MOMENTS` in `seed.py`. They don't run while previewing another day.

## Optional files

- `static/audio/horn.mp3` and `static/audio/war-cry.mp3`: sounds for the alerts horn and finishing orientation.

## Notes

- Integrations with CSU systems (CampusNet, Blackboard, Viking Card office and others) are simulated with sample data. The site links to the official services and does not connect to them.
- Passwords are stored as salted hashes (Werkzeug), never in plain text.
- "Remember me" saves only the CSU ID, and only for the current launch of the app.
- Parking space counts, club meeting details, campus events, equipment counts, pantry turns, grade scores, Rec class times and crowd levels, and other students' room reservations are sample data.
- **Change day** previews another day from November 12 to December 12. Things tied to the real day (tap to pay, deposits, Mobile Campus requests, bookings past their window and parking counts) stay locked to November 12 while previewing.
- Installable app: on the live https site, phones can add Viking Hub to the home screen (Android Chrome: menu, Add to Home screen, Install; iPhone Safari: Share, Add to Home Screen). It opens full screen to the sign-in page. `routes/install.py` serves the manifest, the service worker (`static/js/sw.js`) and the offline screen; icons are in `static/images/app/`. Only styles, scripts and images are kept on the phone, never signed-in pages. It can't be installed from `http://` addresses such as your PC's network IP.
- Weather on Home comes from Open-Meteo (https://open-meteo.com, free, no key). The browser fetches it directly, so it works on PythonAnywhere's free plan. It's the one part of the app that isn't identical every launch, it shows real Cleveland weather for the app's "today", and it hides itself when offline or while previewing another day. Rain, snow, storms or cold under 25°F add a note to today's walk lines, with an Innerlink suggestion when the walk is on the Innerlink.
- Walking times are estimates measured on the campus map: about 3 mph plus a 2 minute buffer. After a break of more than 30 minutes, the next walk starts from the Home pin.

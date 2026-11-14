"""CSU Viking Hub: Flask application entry point.

Run with:  python app.py   then open http://127.0.0.1:5000
"""
import os

from flask import Flask, render_template, request, session

from alerts import active_alerts
from config import Config
from db import close_db, init_db, query_one
from formatting import money, nice_date
from security import BOOT_ID, check_csrf, csrf_token

from navigation import GETTING_AROUND, RESOURCES_LINK, SERVICES

FOOTER_LINKS = [
    {"label": "CampusNet", "url": "https://campusnet.csuohio.edu/"},
    {"label": "MyCSU", "url": "https://mycsu.csuohio.edu/"},
]


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    init_db(app)
    app.teardown_appcontext(close_db)
    app.before_request(check_csrf)

    from routes import ALL_BLUEPRINTS
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    # Add the file's last-change time to every static link (style.css?v=...),
    # so browsers pick up new CSS and JavaScript instead of a cached copy
    @app.url_defaults
    def static_version(endpoint, values):
        if endpoint == "static" and "filename" in values:
            path = os.path.join(app.static_folder, values["filename"])
            if os.path.isfile(path):
                values["v"] = int(os.stat(path).st_mtime)

    # Template helpers
    def icon(name, cls=""):
        # Looked up on each use so edits to icons.html show up without restarting
        return app.jinja_env.get_template("partials/icons.html").module.icon(name, cls)

    app.jinja_env.globals["icon"] = icon
    # The same icon set for page scripts
    app.jinja_env.globals["icon_paths"] = lambda: dict(app.jinja_env.get_template("partials/icons.html").module.ICONS)

    def sounds():
        """Sound files dropped into static/audio: horn.* for the alerts horn, war-cry.* for finishing orientation."""
        folder = os.path.join(app.static_folder, "audio")
        found = {}
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                stem, ext = os.path.splitext(name)
                if ext.lower() in (".mp3", ".wav", ".ogg", ".m4a", ".webm") and stem in ("horn", "war-cry"):
                    found.setdefault(stem.replace("-", "_"), f"/static/audio/{name}")
        return found
    app.jinja_env.globals["sounds"] = sounds
    # Tap to pay registers, for the card that can be tapped on any page
    from routes.viking_card import REGISTERS, place_name
    app.jinja_env.globals["tap_registers"] = REGISTERS
    app.jinja_env.globals["place_name"] = place_name
    app.jinja_env.filters["money"] = money
    app.jinja_env.filters["nice_date"] = nice_date

    @app.context_processor
    def inject_globals():
        student = None
        alerts = []
        ready = False
        services = SERVICES
        if "student_id" in session:
            student = query_one(
                "SELECT student_id, first_name, last_name, email FROM students WHERE student_id = ?",
                (session["student_id"],),
            )
            alerts = active_alerts(session["student_id"])
            from routes.dashboard import moment_for
            from routes.orientation import orientation_done
            ready = moment_for(session["student_id"], request.endpoint)
            if orientation_done(session["student_id"]):
                services = [s for s in SERVICES if s["endpoint"] != "orientation.index"] + [RESOURCES_LINK]
        from alerts import project_today
        from routes.schedule import TERM
        today = project_today()
        app_day = {"today": today, "iso": today.isoformat(), "default": app.config["PROJECT_DATE"],
                   "max": TERM["end"], "moved": today.isoformat() != app.config["PROJECT_DATE"]}
        prefs = None
        if "student_id" in session:
            from routes.settings import get_settings
            prefs = get_settings(session["student_id"])
        return {
            "prefs_global": prefs,
            "app_day": app_day,
            "alerts": alerts,
            "boot_id": BOOT_ID,
            "update_ready": ready,
            "services": services,
            "getting_around": GETTING_AROUND,
            "footer_links": FOOTER_LINKS,
            "student": student,
            "csrf_token": csrf_token,
            "current_endpoint": request.endpoint,
        }

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(500)
    def handle_error(err):
        code = getattr(err, "code", 500)
        if request.path.startswith("/api/"):
            return {"error": getattr(err, "description", "Request failed.")}, code
        messages = {
            400: "Something about that request didn't look right.",
            403: "That isn't available to change.",
            409: "That change conflicts with something already saved.",
            404: "We couldn't find that page.",
            500: "Something went wrong on our end.",
        }
        detail = getattr(err, "description", None) if code == 400 else None
        return render_template("error.html", code=code, message=messages.get(code), detail=detail), code

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

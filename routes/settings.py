"""Settings: text size, which alerts arrive, sounds and motion."""
from flask import Blueprint, abort, jsonify, render_template, request, session

from db import get_db, query_one
from security import login_required

bp = Blueprint("settings", __name__)

DEFAULTS = {"text_size": "default", "alerts_off": [], "sound_horn": True, "sound_war_cry": True, "reduce_motion": False}
TEXT_SIZES = [("default", "Default"), ("large", "Large"), ("larger", "Larger")]


def get_settings(sid):
    row = query_one("SELECT * FROM settings WHERE student_id = ?", (sid,))
    if row is None:
        return dict(DEFAULTS)
    return {"text_size": row["text_size"], "alerts_off": [c for c in row["alerts_off"].split(",") if c],
            "sound_horn": bool(row["sound_horn"]), "sound_war_cry": bool(row["sound_war_cry"]),
            "reduce_motion": bool(row["reduce_motion"])}


@bp.route("/settings")
@login_required
def index():
    from alerts import CATEGORY_LABELS
    from walking import home_point
    sid = session["student_id"]
    return render_template("settings.html", title="Settings", prefs=get_settings(sid), sizes=TEXT_SIZES,
                           categories=CATEGORY_LABELS, home=home_point(sid))


@bp.route("/api/settings", methods=["POST"])
@login_required
def save():
    from alerts import CATEGORY_LABELS
    sid = session["student_id"]
    data = request.get_json(silent=True) or {}
    prefs = get_settings(sid)
    if "text_size" in data:
        if not isinstance(data["text_size"], str) or data["text_size"] not in dict(TEXT_SIZES):
            abort(400, description="Choose a text size.")
        prefs["text_size"] = data["text_size"]
    if "alerts_off" in data:
        if not isinstance(data["alerts_off"], list):
            abort(400, description="Choose which alerts to turn off.")
        off = [c for c in data["alerts_off"] if isinstance(c, str) and c in CATEGORY_LABELS]
        prefs["alerts_off"] = off
    for key in ("sound_horn", "sound_war_cry", "reduce_motion"):
        if key in data:
            prefs[key] = bool(data[key])
    db = get_db()
    db.execute(
        """INSERT INTO settings (student_id, text_size, alerts_off, sound_horn, sound_war_cry, reduce_motion)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(student_id) DO UPDATE SET text_size = excluded.text_size, alerts_off = excluded.alerts_off,
             sound_horn = excluded.sound_horn, sound_war_cry = excluded.sound_war_cry, reduce_motion = excluded.reduce_motion""",
        (sid, prefs["text_size"], ",".join(prefs["alerts_off"]), int(prefs["sound_horn"]), int(prefs["sound_war_cry"]),
         int(prefs["reduce_motion"])))
    db.commit()
    return jsonify(prefs=prefs, message="Settings saved")

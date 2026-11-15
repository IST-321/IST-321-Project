"""Installable app: the manifest, the service worker and the offline screen.

These are served from the site root so the service worker can cover every page.
Nothing here needs a sign-in, and no signed-in page is ever saved on the phone."""
import json
from pathlib import Path

from flask import Blueprint, Response, current_app, render_template, url_for

bp = Blueprint("install", __name__)

SW_FILE = Path(__file__).resolve().parent.parent / "static" / "js" / "sw.js"


@bp.route("/manifest.webmanifest")
def manifest():
    icon = lambda name: url_for("static", filename=f"images/app/{name}")
    data = {
        "name": "CSU Viking Hub",
        "short_name": "Viking Hub",
        "description": "Student services for Cleveland State University in one place.",
        "id": "/",
        "start_url": "/login",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#006a4d",
        "theme_color": "#006a4d",
        "icons": [
            {"src": icon("icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": icon("icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": icon("icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }
    return Response(json.dumps(data), mimetype="application/manifest+json")


@bp.route("/sw.js")
def service_worker():
    # The version changes with each launch, so phones pick up new styles and scripts.
    from security import BOOT_ID
    body = SW_FILE.read_text(encoding="utf-8").replace("__VERSION__", BOOT_ID)
    resp = Response(body, mimetype="text/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@bp.route("/offline")
def offline():
    return render_template("offline.html")

"""SQLite helpers: connection handling and schema setup."""
import sqlite3

from flask import current_app, g


def get_db():
    """Return a connection for the current request."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query_one(sql, params=()):
    return get_db().execute(sql, params).fetchone()


def query_all(sql, params=()):
    return get_db().execute(sql, params).fetchall()


def init_db(app):
    """Rebuild the database from the sample data every time the app starts.

    Every launch begins from the same alerts, balances and page content.
    Changes made while the app is running (adding funds, clearing alerts,
    locking the card and so on) are saved and last until the app is closed,
    including across sign outs.
    """
    from seed import seed_all

    db = sqlite3.connect(app.config["DATABASE"])
    db.execute("PRAGMA foreign_keys = OFF")
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )]
    for name in tables:
        db.execute(f'DROP TABLE IF EXISTS "{name}"')
    db.commit()
    db.execute("PRAGMA foreign_keys = ON")
    with open(app.config["SCHEMA"], encoding="utf-8") as f:
        db.executescript(f.read())
    seed_all(db, app.config)
    db.commit()
    db.close()

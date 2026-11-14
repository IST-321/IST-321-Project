"""Application settings for CSU Viking Hub."""
import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, "database")


def _load_secret_key():
    """Use SECRET_KEY from the environment, or create one and keep it on disk
    so sessions survive an application restart."""
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    key_path = os.path.join(DATABASE_DIR, ".secret_key")
    os.makedirs(DATABASE_DIR, exist_ok=True)
    if not os.path.exists(key_path):
        with open(key_path, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(32))
    with open(key_path, encoding="utf-8") as f:
        return f.read().strip()


class Config:
    SECRET_KEY = _load_secret_key()
    DATABASE = os.path.join(DATABASE_DIR, "viking_hub.db")
    SCHEMA = os.path.join(DATABASE_DIR, "schema.sql")

    # Session cookie is not permanent, so it is cleared when the browser closes.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    REMEMBER_COOKIE = "vh_remember_id"
    REMEMBER_DAYS = 30

    # Reference date for the schedule and dashboard (project date).
    PROJECT_DATE = "2026-11-12"

    # Time of day the app starts at each launch, so every run looks the same (9:15 AM is just
    # before BIO 100). The clock then runs normally from there. Set to None to use the computer's clock.
    PRESENT_TIME = "09:15"

    # Sample account for Magnus Viking.
    SAMPLE_STUDENT_ID = "2000000"
    SAMPLE_PASSWORD = "Vikes2026!"

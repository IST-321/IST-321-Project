"""Viking Card: digital card, balance, activity, meal plan and card controls.

Balances and card controls here are kept in Viking Hub's own database. They do
not connect to the CSU Online Card Office.
"""
import re
import statistics
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, jsonify, render_template, request, session

from alerts import add_alert, day_label, previewing, project_now, project_today
from db import get_db, query_all, query_one
from formatting import money, nice_date
from security import login_required

bp = Blueprint("viking_card", __name__)

MIN_DEPOSIT = 500      # $5.00
MAX_DEPOSIT = 50000    # $500.00
REPLACEMENT_REASONS = ["Lost", "Stolen", "Damaged", "Name change"]
TERM_END = date(2026, 12, 12)      # last day of the fall semester
LOW_CHOICES = [(3, "3 days"), (7, "1 week"), (14, "2 weeks"), (0, "Off")]  # warn when the balance lasts less than this
ALMOST_EMPTY = 500        # under $5 always counts as low
ONE_TIME_MIN = 2500       # a purchase must be at least $25 (and well above usual) to count as one-time
MAX_TAP = 10000                     # $100.00 per tap purchase

# Registers a tap purchase can be made at. Viking Marketplace uses a meal swipe.
REGISTERS = [
    {"id": "starbucks", "name": "Starbucks, Student Center"},
    {"id": "chickfila", "name": "Chick-fil-A, Student Center"},
    {"id": "express", "name": "Viking Express"},
    {"id": "market", "name": "Market on Euclid"},
    {"id": "hissho", "name": "Hissho Sushi"},
    {"id": "pub", "name": "Viking Public House"},
    {"id": "store", "name": "Viking Outfitters Campus Store"},
    {"id": "vending", "name": "Campus vending"},
    {"id": "marketplace", "name": "Viking Marketplace", "swipe": True},
]
SHORT_NAMES = {
    "Starbucks, Student Center": "Starbucks", "Chick-fil-A, Student Center": "Chick-fil-A",
    "Viking Outfitters Campus Store": "Campus Store", "Campus vending": "Vending",
}


def place_name(location):
    return SHORT_NAMES.get(location, location)


def _long_date(d):
    return f"{d.strftime('%A, %B')} {d.day}"


def insights(sid):
    """Spending pace, how long the money and swipes last, and spending by place."""
    now = project_now()
    today = now.date()
    card = _card(sid)
    meal = query_one("SELECT * FROM meal_plans WHERE student_id = ?", (sid,))
    since14 = (now - timedelta(days=14)).isoformat(timespec="minutes")
    since30 = (now - timedelta(days=30)).isoformat(timespec="minutes")
    days_left = max(1, (TERM_END - today).days)
    weeks_left = days_left / 7

    pace, one_time = usual_pace(sid, now)
    money_info = {"pace": round(pace), "pace_label": money(round(pace)), "term_end": _long_date(TERM_END),
                  "one_time": one_time}
    low_days = card["low_alert_days"]
    if pace > 0:
        lasts = int(card["balance_cents"] // pace)
        runs_out = today + timedelta(days=lasts)
        before_end = runs_out < TERM_END
        need = max(0, round(pace * days_left) - card["balance_cents"])
        money_info.update(runs_out=_long_date(runs_out) if lasts < 365 else None, before_end=before_end,
                          days=lasts, need=need, need_label=money(-(-need // 100) * 100))  # rounded up to whole dollars
    else:
        money_info.update(runs_out=None, before_end=False, days=None, need=0, need_label=money(0))
    # Same rule as the low balance alert, so the warning and the alert always agree
    money_info["short"] = is_low(card["balance_cents"], pace, low_days)

    swipe_info = None
    if meal:
        used14 = query_one(
            "SELECT COUNT(*) AS n FROM card_transactions WHERE student_id = ? AND txn_type = 'Meal swipe' AND occurred_at >= ?",
            (sid, since14))["n"]
        per_week = used14 / 2
        left = meal["swipes_remaining"]
        projected = round(left - per_week * weeks_left)
        swipe_info = {"left": left, "total": meal["swipes_total"], "allowance": round(left / weeks_left),
                      "per_week": round(per_week), "projected_left": projected, "short": projected < 0}

    rows = query_all(
        """SELECT location, -SUM(amount_cents) AS spent, COUNT(*) AS n FROM card_transactions
           WHERE student_id = ? AND txn_type = 'Purchase' AND occurred_at >= ? GROUP BY location""",
        (sid, since30))
    places = {}
    for r in rows:
        name = place_name(r["location"])
        places.setdefault(name, {"place": name, "spent": 0, "count": 0})
        places[name]["spent"] += r["spent"]
        places[name]["count"] += r["n"]
    by_place = sorted(places.values(), key=lambda p: -p["spent"])
    if len(by_place) > 8:
        rest = by_place[7:]
        by_place = by_place[:7] + [{"place": "Other", "spent": sum(p["spent"] for p in rest),
                                    "count": sum(p["count"] for p in rest),
                                    "includes": [p["place"] for p in rest]}]
    for p in by_place:
        p["label"] = money(p["spent"])
    total = sum(p["spent"] for p in by_place)
    return {"balance": card["balance_cents"], "balance_label": money(card["balance_cents"]),
            "money": money_info, "swipes": swipe_info, "by_place": by_place,
            "total_30": total, "total_30_label": money(total),
            "low_alert_days": low_days, "locked": bool(card["is_locked"])}


def usual_pace(sid, now=None):
    """Average daily spending over the last two weeks, leaving out one-time purchases.

    A purchase counts as one-time when it's at least $25 and more than three times a typical
    purchase, like a $100 Campus Store order. Those would make every day look expensive.
    """
    now = now or project_now()
    since14 = (now - timedelta(days=14)).isoformat(timespec="minutes")
    since30 = (now - timedelta(days=30)).isoformat(timespec="minutes")
    recent = [-r["amount_cents"] for r in query_all(
        "SELECT amount_cents FROM card_transactions WHERE student_id = ? AND txn_type = 'Purchase' AND occurred_at >= ?",
        (sid, since30))]
    typical = statistics.median(recent) if recent else 0
    cap = max(ONE_TIME_MIN, 3 * typical)
    rows = query_all(
        """SELECT location, amount_cents FROM card_transactions
           WHERE student_id = ? AND txn_type = 'Purchase' AND occurred_at >= ? ORDER BY occurred_at""", (sid, since14))
    regular = sum(-r["amount_cents"] for r in rows if -r["amount_cents"] <= cap)
    one_time = [{"place": place_name(r["location"]), "label": money(-r["amount_cents"])}
                for r in rows if -r["amount_cents"] > cap]
    return regular / 14, one_time


def is_low(balance, pace, low_days):
    """Low means the balance won't last the chosen number of days at the usual pace, or it's almost empty."""
    if not low_days:
        return False
    return balance < ALMOST_EMPTY or (pace > 0 and balance / pace < low_days)


def _money_amount(raw):
    """A plain dollar amount like 25 or 6.45, or None. Rejects words like Infinity and NaN and forms like 1e2."""
    if not re.fullmatch(r"\d{1,6}(\.\d{1,2})?", raw or ""):
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _card(sid):
    return query_one("SELECT * FROM viking_cards WHERE student_id = ?", (sid,))


def _txn_json(row):
    return {
        "id": row["id"],
        "location": row["location"],
        "type": row["txn_type"],
        "amount": row["amount_cents"],
        "amount_label": ("+" if row["amount_cents"] > 0 else "") + money(row["amount_cents"]) if row["amount_cents"] else "1 swipe",
        "when": nice_date(row["occurred_at"], "%b %d, %I:%M %p"),
        "place": place_name(row["location"]),
    }


def card_lock():
    if previewing():
        return (f"Tap to pay and deposits happen on the real day, November 12. "
                f"You're previewing {day_label(project_today())}, so go back to November 12 to use them.")
    return None


def _check_low(sid, new_balance):
    """Send exactly one alert when the balance becomes low; re-arm once it isn't low anymore."""
    card = _card(sid)
    pace, _ = usual_pace(sid)
    low = is_low(new_balance, pace, card["low_alert_days"])
    db = get_db()
    if low and not card["low_alerted"]:
        days = int(new_balance // pace) if pace > 0 else 0
        body = (f"At your usual pace, {money(new_balance)} lasts about {days} day{'' if days == 1 else 's'}. "
                if pace > 0 and new_balance >= ALMOST_EMPTY else f"Your balance is down to {money(new_balance)}. ")
        add_alert(sid, "card", "Viking Card balance is running low",
                  body + "Add funds, or lock your card if it isn't with you.",
                  "card", "viking_card.index#add-funds", actions=["add_funds", "lock_card"])
        db.execute("UPDATE viking_cards SET low_alerted = 1 WHERE student_id = ?", (sid,))
    elif not low:
        db.execute("UPDATE viking_cards SET low_alerted = 0 WHERE student_id = ?", (sid,))


@bp.route("/viking-card")
@login_required
def index():
    sid = session["student_id"]
    transactions = query_all(
        "SELECT * FROM card_transactions WHERE student_id = ? ORDER BY occurred_at DESC, id DESC", (sid,)
    )
    requests_ = query_all(
        "SELECT * FROM card_requests WHERE student_id = ? ORDER BY created_at DESC", (sid,)
    )
    return render_template(
        "viking_card.html",
        title="Viking Card",
        card=_card(sid),
        meal=query_one("SELECT * FROM meal_plans WHERE student_id = ?", (sid,)),
        transactions=transactions,
        card_requests=requests_,
        reasons=REPLACEMENT_REASONS,
        insights=insights(sid),
        low_choices=LOW_CHOICES,
        card_lock=card_lock(),
    )


@bp.route("/api/viking-card/funds", methods=["POST"])
@login_required
def add_funds():
    sid = session["student_id"]
    if card_lock():
        return jsonify(error=card_lock()), 409
    card = _card(sid)
    if card["is_locked"]:
        return jsonify(error="Your card is locked. Unlock it before adding funds."), 409

    raw = str((request.get_json(silent=True) or {}).get("amount", "")).strip().lstrip("$")
    amount = _money_amount(raw)
    if amount is None:
        abort(400, description="Enter an amount like 25 or 25.50.")
    if amount != amount.quantize(Decimal("0.01")):
        abort(400, description="Use dollars and cents only.")
    cents = int(amount * 100)
    if cents < MIN_DEPOSIT or cents > MAX_DEPOSIT:
        abort(400, description="Add between $5.00 and $500.00 at a time.")

    new_balance = card["balance_cents"] + cents
    db = get_db()
    now = project_now().isoformat(timespec="minutes")
    cur = db.execute(
        """INSERT INTO card_transactions (student_id, occurred_at, location, txn_type, amount_cents, balance_after_cents)
           VALUES (?, ?, 'Viking Hub deposit', 'Deposit', ?, ?)""",
        (sid, now, cents, new_balance),
    )
    db.execute("UPDATE viking_cards SET balance_cents = ? WHERE student_id = ?", (new_balance, sid))
    add_alert(sid, "card", "Viking Card balance updated",
              f"{money(cents)} was added. Your balance is now {money(new_balance)}.", "card", "viking_card.index#activity")
    _check_low(sid, new_balance)
    db.commit()
    txn = query_one("SELECT * FROM card_transactions WHERE id = ?", (cur.lastrowid,))
    return jsonify(balance=new_balance, balance_label=money(new_balance), transaction=_txn_json(txn),
                   insights=insights(sid))


@bp.route("/api/viking-card/lock", methods=["POST"])
@login_required
def set_lock():
    sid = session["student_id"]
    locked = bool((request.get_json(silent=True) or {}).get("locked"))
    if bool(_card(sid)["is_locked"]) == locked:
        return jsonify(locked=locked)  # already that way (another tab, a double click): no second alert
    db = get_db()
    db.execute(
        "UPDATE viking_cards SET is_locked = ?, locked_at = ? WHERE student_id = ?",
        (1 if locked else 0, project_now().isoformat(timespec="minutes") if locked else None, sid),
    )
    if locked:
        add_alert(sid, "card", "Viking Card locked",
                  "Your card is locked in Viking Hub. Unlock it to add funds or use tap to pay.", "lock",
                  "viking_card.index")
    else:
        add_alert(sid, "card", "Viking Card unlocked", "Your card is active again.", "unlock", "viking_card.index")
    db.commit()
    return jsonify(locked=locked)


@bp.route("/api/viking-card/replacement", methods=["POST"])
@login_required
def request_replacement():
    sid = session["student_id"]
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "")
    details = " ".join(str(data.get("details", "")).split())
    if reason not in REPLACEMENT_REASONS:
        abort(400, description="Choose what happened to your card.")
    if len(details) < 5:
        abort(400, description="Add a short explanation of what happened.")
    if len(details) > 500:
        abort(400, description="Keep the explanation under 500 characters.")
    now = project_now().isoformat(timespec="minutes")
    db = get_db()
    cur = db.execute(
        "INSERT INTO card_requests (student_id, request_type, reason, details, created_at) VALUES (?, 'Replacement', ?, ?, ?)",
        (sid, reason, details, now),
    )
    db.commit()
    return jsonify(id=cur.lastrowid, reason=reason, details=details, when=nice_date(now, "%b %d, %Y"))


@bp.route("/api/viking-card/tap", methods=["POST"])
@login_required
def tap_purchase():
    """A tap to pay purchase made in Viking Hub. It only changes the Viking Hub balance; no real payment happens."""
    sid = session["student_id"]
    if card_lock():
        return jsonify(error=card_lock()), 409
    card = _card(sid)
    if card["is_locked"]:
        return jsonify(error="Your card is locked. Unlock it to use tap to pay."), 409
    data = request.get_json(silent=True) or {}
    register = next((r for r in REGISTERS if r["id"] == data.get("register")), None)
    if register is None:
        abort(400, description="Choose where you're paying.")
    db = get_db()
    now = project_now().isoformat(timespec="minutes")
    if register.get("swipe"):
        meal = query_one("SELECT swipes_remaining FROM meal_plans WHERE student_id = ?", (sid,))
        if not meal or meal["swipes_remaining"] <= 0:
            return jsonify(error="You don't have any meal swipes left."), 409
        cur = db.execute(
            """INSERT INTO card_transactions (student_id, occurred_at, location, txn_type, amount_cents, balance_after_cents)
               VALUES (?, ?, ?, 'Meal swipe', 0, ?)""", (sid, now, register["name"], card["balance_cents"]))
        db.execute("UPDATE meal_plans SET swipes_remaining = swipes_remaining - 1 WHERE student_id = ?", (sid,))
        message = "1 meal swipe used at Viking Marketplace"
        new_balance = card["balance_cents"]
    else:
        raw = str(data.get("amount", "")).strip().lstrip("$")
        amount = _money_amount(raw)
        if amount is None:
            abort(400, description="Enter an amount like 6.45.")
        if amount != amount.quantize(Decimal("0.01")) or amount <= 0:
            abort(400, description="Enter an amount like 6.45.")
        cents = int(amount * 100)
        if cents > MAX_TAP:
            abort(400, description="Tap purchases are limited to $100.00.")
        if cents > card["balance_cents"]:
            return jsonify(error=f"Not enough on your card. Your balance is {money(card['balance_cents'])}."), 409
        new_balance = card["balance_cents"] - cents
        cur = db.execute(
            """INSERT INTO card_transactions (student_id, occurred_at, location, txn_type, amount_cents, balance_after_cents)
               VALUES (?, ?, ?, 'Purchase', ?, ?)""", (sid, now, register["name"], -cents, new_balance))
        db.execute("UPDATE viking_cards SET balance_cents = ? WHERE student_id = ?", (new_balance, sid))
        _check_low(sid, new_balance)
        message = f"Paid {money(cents)} at {place_name(register['name'])}"
    db.commit()
    txn = query_one("SELECT * FROM card_transactions WHERE id = ?", (cur.lastrowid,))
    meal = query_one("SELECT swipes_remaining FROM meal_plans WHERE student_id = ?", (sid,))
    return jsonify(message=message, balance=new_balance, balance_label=money(new_balance),
                   swipes=meal["swipes_remaining"] if meal else None,
                   transaction=_txn_json(txn), insights=insights(sid))


@bp.route("/api/viking-card/low-alert", methods=["POST"])
@login_required
def set_low_alert():
    sid = session["student_id"]
    try:
        days = int((request.get_json(silent=True) or {}).get("days"))
    except (TypeError, ValueError, OverflowError):
        abort(400, description="Choose when to be warned.")
    if days not in dict(LOW_CHOICES):
        abort(400, description="Choose when to be warned.")
    card = _card(sid)
    pace, _ = usual_pace(sid)
    # Already low counts as already alerted, so changing the setting never sends an alert by itself
    low = is_low(card["balance_cents"], pace, days)
    db = get_db()
    db.execute("UPDATE viking_cards SET low_alert_days = ?, low_alerted = ? WHERE student_id = ?", (days, int(low), sid))
    db.commit()
    label = dict(LOW_CHOICES)[days]
    return jsonify(message=f"We'll warn you when your balance lasts less than {label}" if days else "Low balance warnings are off",
                   insights=insights(sid))

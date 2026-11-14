"""Formatting helpers used by templates and API responses."""
from datetime import datetime


def money(cents):
    """Format integer cents as dollars, e.g. 14250 -> $142.50."""
    cents = int(cents or 0)
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.2f}"


def nice_date(value, fmt="%b %d, %Y"):
    """Format an ISO date/datetime string without leading zeros on day or hour."""
    if not value:
        return ""
    dt = datetime.fromisoformat(str(value))
    hour12 = dt.hour % 12 or 12
    out = dt.strftime(fmt.replace("%d", "{D}").replace("%I", "{H}"))
    return out.replace("{D}", str(dt.day)).replace("{H}", str(hour12))

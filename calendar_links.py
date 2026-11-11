from datetime import datetime, timedelta
from urllib.parse import urlencode

def gcal_link(title, start_iso, end_iso=None, all_day=False, location="", details=""):
    s = datetime.fromisoformat(start_iso)
    if all_day:
        e = s + timedelta(days=1)
        dates = f"{s:%Y%m%d}/{e:%Y%m%d}"
    else:
        e = datetime.fromisoformat(end_iso) if end_iso else s + timedelta(hours=1)
        dates = f"{s:%Y%m%dT%H%M%S}/{e:%Y%m%dT%H%M%S}"   # no "Z" → uses the user's own calendar time zone
    q = urlencode({"action": "TEMPLATE", "text": title, "dates": dates,
                   "location": location, "details": details})
    return "https://calendar.google.com/calendar/render?" + q
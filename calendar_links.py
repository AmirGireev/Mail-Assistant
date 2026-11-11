import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import config


# start and end
def _times(ev):
    s = datetime.fromisoformat(ev["start"])
    if ev.get("all_day"):
        return s, s + timedelta(days=1)
    e = datetime.fromisoformat(ev["end"]) if ev.get("end") else s + timedelta(hours=1)
    return s, e


# escape text
def _esc(text):
    bs = chr(92)
    text = str(text or "").replace(bs, bs + bs).replace(";", bs + ";").replace(",", bs + ",")
    return text.replace("\r", "").replace("\n", bs + "n")


# google link
def google_link(ev):
    s, e = _times(ev)
    if ev.get("all_day"):
        dates = f"{s:%Y%m%d}/{e:%Y%m%d}"
    else:
        # local time
        dates = f"{s:%Y%m%dT%H%M%S}/{e:%Y%m%dT%H%M%S}"
    q = urlencode({"action": "TEMPLATE", "text": ev["title"], "dates": dates,
                   "location": ev.get("location", "")})
    return "https://calendar.google.com/calendar/render?" + q


# apple link
def apple_link(ev):
    base = config.get("APP_URL")
    # google fallback
    if not base:
        return google_link(ev)
    data = {"t": ev["title"], "s": ev["start"], "e": ev.get("end"),
            "a": 1 if ev.get("all_day") else 0, "l": ev.get("location", "")}
    token = base64.urlsafe_b64encode(
        json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()).decode().rstrip("=")
    return base.rstrip("/") + "/?" + urlencode({"cal": token})


# choose link
def event_link(kind, ev):
    return apple_link(ev) if kind == "apple" else google_link(ev)


# read link
def decode_event(token):
    token += "=" * (-len(token) % 4)
    d = json.loads(base64.urlsafe_b64decode(token.encode()))
    ev = {"title": str(d["t"])[:200], "start": d["s"], "end": d.get("e"),
          "all_day": bool(d.get("a")), "location": str(d.get("l") or "")[:200]}
    # validate dates
    _times(ev)
    return ev


# ics file
def make_ics(ev):
    s, e = _times(ev)
    if ev.get("all_day"):
        start, end = f"DTSTART;VALUE=DATE:{s:%Y%m%d}", f"DTEND;VALUE=DATE:{e:%Y%m%d}"
    else:
        # local time
        start, end = f"DTSTART:{s:%Y%m%dT%H%M%S}", f"DTEND:{e:%Y%m%dT%H%M%S}"
    uid = hashlib.md5(f"{ev['title']}{ev['start']}".encode()).hexdigest() + "@mail-assistant"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Mail Assistant//EN", "BEGIN:VEVENT",
             f"UID:{uid}", f"DTSTAMP:{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}",
             start, end, f"SUMMARY:{_esc(ev['title'])}"]
    if ev.get("location"):
        lines.append(f"LOCATION:{_esc(ev['location'])}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(lines) + "\r\n"
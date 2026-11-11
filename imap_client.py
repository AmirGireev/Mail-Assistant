import email
import imaplib
import re
import ssl
import time
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup


# plain body
def _body_text(msg):
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    text = part.get_content()
    # strip html
    if part.get_content_type() == "text/html":
        text = BeautifulSoup(text, "html.parser").get_text("\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# log in
def connect(host, port, user, password):
    m = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context())
    m.login(user, password)
    return m


# special folder
def find_folder(m, flag, fallbacks):
    # by flag
    _, lines = m.list()
    for raw in lines:
        s = raw.decode(errors="ignore")
        mt = re.match(r'\((?P<flags>.*?)\)\s+"?(?P<delim>[^"\s]+)"?\s+(?P<name>.+)', s)
        if mt and flag.lower() in mt["flags"].lower():
            return mt["name"].strip().strip('"')
    # by name
    for name in fallbacks:
        if m.select(f'"{name}"', readonly=True)[0] == "OK":
            return name
    return None


# new mails
def fetch_since(m, since: datetime, folder="INBOX", limit=60):
    # read only
    m.select(f'"{folder}"', readonly=True)
    day = since.strftime("%d-%b-%Y")
    _, data = m.search(None, f'(SINCE "{day}")')
    ids = data[0].split()[-limit:]
    out = []
    for i in ids:
        _, d = m.fetch(i, "(BODY.PEEK[])")
        msg = email.message_from_bytes(d[0][1], policy=policy.default)
        # parse date
        try:
            when = parsedate_to_datetime(msg["Date"])
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if when < since:
            continue
        # attachments
        atts = []
        for a in msg.iter_attachments():
            fn = a.get_filename()
            if fn:
                atts.append((fn, a.get_content_type(), a.get_payload(decode=True) or b""))
        out.append({
            "id": str(i.decode()),
            "from": str(msg["From"] or ""),
            "subject": str(msg["Subject"] or ""),
            "date": when,
            "body": _body_text(msg),
            "bulk_hint": bool(msg["List-Unsubscribe"]) or (msg["Precedence"] or "").lower() in ("bulk", "list"),
            "attachments": atts,
            "raw": msg,
        })
    return out


# sent samples
def sample_sent(m, n=25):
    folder = find_folder(m, "\\Sent", ["Sent", "Gesendet", "INBOX.Sent", "[Gmail]/Sent Mail"])
    m.select(f'"{folder}"', readonly=True)
    _, data = m.search(None, "ALL")
    samples = []
    for i in data[0].split()[-n:]:
        _, d = m.fetch(i, "(BODY.PEEK[])")
        msg = email.message_from_bytes(d[0][1], policy=policy.default)
        txt = _body_text(msg)
        # cut quotes
        txt = re.split(r"\n(On .* wrote:|Am .* schrieb.*|-----Original)", txt)[0]
        txt = "\n".join(l for l in txt.splitlines() if not l.startswith(">"))
        if len(txt) > 40:
            samples.append(txt[:800])
    return samples


# reply message
def build_reply(orig, body, my_addr):
    r = EmailMessage()
    r["From"] = my_addr
    r["To"] = orig["Reply-To"] or orig["From"]
    subj = str(orig["Subject"] or "")
    r["Subject"] = subj if subj.lower().startswith(("re:", "aw:")) else "Re: " + subj
    # thread headers
    if orig["Message-ID"]:
        r["In-Reply-To"] = orig["Message-ID"]
        r["References"] = ((orig["References"] or "") + " " + orig["Message-ID"]).strip()
    r.set_content(body)
    return r


# store draft
def save_draft(m, reply_msg):
    folder = find_folder(m, "\\Drafts", ["Drafts", "Entwürfe", "INBOX.Drafts", "[Gmail]/Drafts"])
    if not folder:
        raise RuntimeError("Drafts folder not found")
    m.append(f'"{folder}"', "\\Draft", imaplib.Time2Internaldate(time.time()), reply_msg.as_bytes())
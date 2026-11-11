import time
from datetime import datetime, timedelta, timezone
import imap_client, attachments, ai, calendar_links, crypto

INTERVAL_DAYS = {"daily": 1, "every_3_days": 3, "weekly": 7}

def run_for_user(u, session, preview=False):
    now = datetime.now(timezone.utc)
    since = u.last_run or now - timedelta(days=INTERVAL_DAYS[u.frequency])

    m = imap_client.connect(u.imap_host, u.imap_port, u.imap_user, crypto.decrypt(u.imap_password_enc))
    mails = imap_client.fetch_since(m, since)

    cl = ai.get_provider(u)          # Gemini or Claude Haiku, depending on the user's setting

    # 1. attachments → text (optional feature)
    if u.feat_attachments:
        for mail in mails:
            texts = []
            for fn, ct, data in mail["attachments"][:5]:
                text, needs_vision = attachments.extract(fn, ct, data)
                if needs_vision and len(data) < 10_000_000:
                    mime = "application/pdf" if fn.lower().endswith(".pdf") else ct
                    try:
                        text = cl.describe_file(data, mime)
                    except Exception:
                        text = ""            # unsupported file type → just skip it
                if text:
                    texts.append(f"[{fn}] {text[:3000]}")
            mail["att_text"] = "\n".join(texts)

    # 2. classify in batches of 15
    results = []
    for i in range(0, len(mails), 15):
        results += ai.analyse_batch(cl, mails[i:i+15], u.sensitivity, now.date().isoformat())
        time.sleep(5)
    by_id = {mail["id"]: mail for mail in mails}
    important = [r for r in results if r["important"]]

    # 3. calendar links (optional)
    for r in important:
        if u.feat_calendar and r.get("event"):
            ev = r["event"]
            r["cal_link"] = calendar_links.gcal_link(ev["title"], ev["start"], ev.get("end"),
                                                     ev.get("all_day", False), ev.get("location", ""))

    # 4. reply drafts (optional)
    drafts = 0
    if u.feat_drafts and u.style_profile and not preview:
        for r in important:
            if r["needs_reply"]:
                orig = by_id[r["id"]]
                body = ai.write_draft(cl, u.style_profile, orig)
                imap_client.save_draft(m, imap_client.build_reply(orig["raw"], body, u.imap_user))
                r["draft"] = True; drafts += 1
                time.sleep(4)

    # 5. build the message
    text = format_digest(u, important, drafts, cl)

    

    # 6. log the real token usage (numbers only, never email content)
    print(f"{u.username}: model={cl.name} tokens_in={cl.tokens_in} tokens_out={cl.tokens_out}")

    if not important and not u.feat_send_if_empty:
        text = None
    m.logout()
    return text      # caller sends it via the user's chosen channel (or shows it in the website when preview=True)

def format_digest(u, important, drafts, cl):
    # If there are no important emails
    if not important:
        if u.feat_send_if_empty:
            return "Nothing important today 🎉."
        return None

    # Header
    lines = ["📬 *Mail summary*"]

    # Body based on user mode
    if u.mode == "short":
        # Assuming ai.short_summary takes the client and the list of emails
        lines.append(ai.short_summary(cl, important))
        
        # In short mode, we still append any calendar links found
        for mail in important:
            if "cal_link" in mail:
                lines.append(f"📅 Add to calendar: {mail['cal_link']}")
                
    elif u.mode == "per_email":
        for mail in important:
            sender = mail.get("sender", "Unknown")
            # Using 'sentence' or falling back to 'summary' just in case
            sentence = mail.get("sentence", mail.get("summary", "")) 
            
            lines.append(f"*{sender}*: {sentence}")
            
            if "cal_link" in mail:
                lines.append(f"📅 Add to calendar: {mail['cal_link']}")

    # Footer for Drafts
    if drafts > 0:
        # Using a dynamic variable {drafts} so it adapts to the actual count
        lines.append(f"✍️ {drafts} reply drafts are waiting in your Drafts folder.")

    return "\n".join(lines)
import time
from datetime import datetime, timedelta, timezone
import imap_client, attachments, ai, calendar_links, crypto

INTERVAL_DAYS = {"daily": 1, "every_3_days": 3, "weekly": 7}


def _bullet(text, clean=False):
    if clean:                                               # remove bullets the AI may have added itself
        text = text.strip().lstrip("-•*– ")
    return "• " + text.strip()


def format_digest(u, important, drafts, cl):
    """Every sentence becomes its own bullet point, so the message is easy to scan."""
    lines = ["📬 *Mail summary*", ""]
    if not important:
        return "\n".join(lines + ["• Nothing important today 🎉"])

    if u.summary_mode == "short":
        for sentence in ai.short_summary(cl, important).splitlines():
            if sentence.strip():
                lines.append(_bullet(sentence, clean=True))
        events = [r for r in important if r.get("cal_link")]
        if events:
            lines += ["", "📅 *Add to calendar*"]
            for r in events:
                lines.append(f"• {r['event']['title']}")
                lines.append(r["cal_link"])                  # link alone on its line = tappable
    else:
        for r in important:
            lines.append(_bullet(f"*{r['sender_name']}*: {r['one_sentence']}"))
            if r.get("cal_link"):
                lines.append("   📅 Add to calendar:")
                lines.append("   " + r["cal_link"])

    if drafts:
        lines += ["", f"✍️ {drafts} reply draft(s) are waiting in your Drafts folder."]
    return "\n".join(lines)


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
            r["cal_link"] = calendar_links.event_link(u.calendar_type, r["event"])   # Google or Apple, per user

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
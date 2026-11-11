import secrets
from zoneinfo import available_timezones

import bcrypt
import streamlit as st
from sqlalchemy.exc import IntegrityError

import ai
import calendar_links
import config
import crypto
import db
import imap_client
import notifier
import pipeline
import telegram_bot

st.set_page_config(page_title="Mail Assistant", page_icon="📬")

# ---------------------------------------------------------------- constants
PRESETS = {
    "Gmail": "imap.gmail.com",
    "GMX": "imap.gmx.net",
    "web.de": "imap.web.de",
    "iCloud": "imap.mail.me.com",
    "Yahoo": "imap.mail.yahoo.com",
    "IONOS": "imap.ionos.de",
    "T-Online": "secureimap.t-online.de",
    "Outlook / Hotmail": "outlook.office365.com",
    "Other": "",
}
HINTS = {
    "Gmail": "Turn on 2-step verification, then create an **App password** (Google Account → Security).",
    "GMX": "Settings → enable POP3/IMAP access. Use an app password if 2FA is on.",
    "web.de": "Settings → enable POP3/IMAP access. Use an app password if 2FA is on.",
    "iCloud": "Create an **app-specific password** at appleid.apple.com.",
    "Yahoo": "Create an app password in your Yahoo account security settings.",
    "IONOS": "Your normal mailbox password works.",
    "T-Online": "Use the special 'email password' from the T-Online customer center.",
    "Other": "Check your provider's IMAP help page for the host name.",
}
FREQUENCIES = {"daily": "Daily", "every_3_days": "Every 3 days", "weekly": "Weekly"}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MODES = {"short": "Short summary of everything", "per_email": "One sentence per important email"}
CHANNELS = {"whatsapp": "WhatsApp (CallMeBot)", "telegram": "Telegram"}
CALENDARS = {"google": "Google Calendar", "apple": "Apple Calendar (iPhone / Mac)"}
TIMEZONES = sorted(available_timezones())

STEP4A = """**WhatsApp via CallMeBot (done once, from your own phone)**

1. Open https://www.callmebot.com and copy the **current bot phone number** (it has changed before).
   If the page says *"The bot is currently full"*, use Telegram instead and try again later.
2. Save that number as a contact, then send it this exact WhatsApp message:
   `I allow callmebot to send me messages`
3. Wait for the reply with your **API key** (nothing after 2 minutes? try again after 24 hours).
4. Enter your number (with country code, e.g. +49...) and the API key here."""

STEP4B = """**Telegram (free, official)**

1. Install Telegram on your phone.
2. Click **"1. Open Telegram and press Start"** below and press **Start** in the chat that opens.
3. Come back here and click **"2. I pressed Start"**. That's it."""


# ---------------------------------------------------------------- calendar page (public, no login)
def calendar_page(token):
    """Opened from the 'Add to calendar' link in the summary (Apple Calendar)."""
    st.title("📅 Add to calendar")
    try:
        ev = calendar_links.decode_event(token)
    except Exception:
        st.error("This calendar link is not valid.")
        return
    start, end = calendar_links._times(ev)
    st.subheader(ev["title"])
    st.write(f"🗓️ {start:%A, %d %B %Y}" if ev["all_day"] else f"🗓️ {start:%A, %d %B %Y, %H:%M} – {end:%H:%M}")
    if ev["location"]:
        st.write(f"📍 {ev['location']}")
    st.download_button("Add to Apple Calendar", calendar_links.make_ics(ev),
                       file_name="event.ics", mime="text/calendar", type="primary")
    st.caption("On iPhone / Mac, open the downloaded file and tap **Add**.")
    st.link_button("Use Google Calendar instead", calendar_links.google_link(ev))


# ---------------------------------------------------------------- helpers
def secret_input(label, saved, key):
    """Password-style field. Never shows the stored secret, returns '' when left empty."""
    return st.text_input(label, type="password", key=key,
                         placeholder="•••••••• saved (leave empty to keep)" if saved else "")


def autosave_secret(user, attr, value):
    """Encrypts and stores a typed secret, but only when it is new."""
    if value:
        try:
            same = crypto.decrypt(getattr(user, attr)) == value
        except Exception:
            same = False
        if not same:
            setattr(user, attr, crypto.encrypt(value))


def login_box():
    st.title("📬 Mail Assistant")
    tab_in, tab_up = st.tabs(["Log in", "Register"])

    with tab_in:
        with st.form("login_form"):                       # a form = pressing Enter submits it
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            go = st.form_submit_button("Log in")
        if go:
            with db.Session() as s:
                row = s.query(db.User).filter_by(username=u.strip()).first()
                if row and bcrypt.checkpw(p.encode(), row.password_hash.encode()):
                    st.session_state.uid = row.id
                    st.rerun()
                else:
                    st.error("Wrong username or password")

    with tab_up:
        with st.form("register_form"):
            u = st.text_input("Choose a username")
            p = st.text_input("Choose a password (min. 8 characters)", type="password")
            code = st.text_input("Invite code")
            go = st.form_submit_button("Create account")
        if go:
            expected = config.get("INVITE_CODE")
            if not expected or not secrets.compare_digest(code.encode(), str(expected).encode()):
                st.error("Invalid invite code")
            elif len(u.strip()) < 3 or len(p) < 8:
                st.error("Username needs 3+ characters and password 8+ characters")
            else:
                try:
                    with db.Session() as s:
                        s.add(db.User(username=u.strip(),
                                      password_hash=bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()))
                        s.commit()
                    st.success("Account created, now log in.")
                except IntegrityError:
                    st.error("That username is taken")


# ---------------------------------------------------------------- entry points
cal_token = st.query_params.get("cal")
if cal_token:
    calendar_page(cal_token)
    st.stop()

if "uid" not in st.session_state:
    login_box()
    st.stop()

with db.Session() as s:
    user = s.get(db.User, st.session_state.uid)
    if user is None:                      # account was deleted
        st.session_state.clear()
        st.rerun()

    head, out = st.columns([4, 1])
    head.title("📬 Mail Assistant")
    if out.button("Log out"):
        st.session_state.clear()          # also clears the writing-style text of this user
        st.rerun()
    st.caption(f"Logged in as **{user.username}**. Everything you change is saved automatically.")

    tab_mail, tab_notify, tab_set, tab_style, tab_prev = st.tabs(
        ["Mailbox", "Notifications", "Settings", "My writing style", "Preview"])

    # ============================================================ Mailbox
    with tab_mail:
        names = list(PRESETS)
        current = next((n for n in names if PRESETS[n] and PRESETS[n] == user.imap_host),
                       "Other" if user.imap_host else names[0])
        provider = st.selectbox("Email provider", names, index=names.index(current), key="provider")
        if provider.startswith("Outlook"):
            st.warning("Outlook.com / Hotmail no longer accept simple passwords over IMAP. "
                       "This needs the optional OAuth step (Step 17).")
        elif provider in HINTS:
            st.info(HINTS[provider])

        if provider == "Other":
            host = st.text_input("IMAP host", value=user.imap_host)
        else:
            host = PRESETS[provider]              # known provider: nothing to type, nothing to show
        address = st.text_input("Email address / login", value=user.imap_user)
        new_pw = secret_input("App password", user.imap_password_enc, "imap_pw")

        user.imap_port = 993                      # always the standard secure IMAP port
        user.imap_user = address.strip()
        if address.strip():
            user.imap_host = host.strip()
        autosave_secret(user, "imap_password_enc", new_pw)

    # ============================================================ Notifications
    with tab_notify:
        keys = list(CHANNELS)
        user.notify_channel = st.radio("Send my summary via", keys, format_func=CHANNELS.get,
                                       index=keys.index(user.notify_channel)
                                       if user.notify_channel in keys else 0,
                                       horizontal=True)
        with st.expander("How do I set this up?"):
            st.markdown(STEP4A if user.notify_channel == "whatsapp" else STEP4B)

        if user.notify_channel == "whatsapp":
            user.wa_phone = st.text_input("WhatsApp number (with country code, e.g. +49...)",
                                          value=user.wa_phone).strip()
            autosave_secret(user, "wa_apikey_enc", secret_input("CallMeBot API key", user.wa_apikey_enc, "wa_key"))
        else:
            if not user.tg_link_code:
                user.tg_link_code = secrets.token_urlsafe(8)
                s.commit()                          # keep the same code on every rerun
            try:
                st.link_button("1. Open Telegram and press Start", telegram_bot.link_for(user.tg_link_code))
            except Exception as e:
                st.error(f"Telegram bot is not set up on the server (TELEGRAM_BOT_TOKEN): {e}")
            if st.button("2. I pressed Start"):
                try:
                    cid = telegram_bot.find_chat_id(user.tg_link_code)
                except Exception as e:
                    cid = None
                    st.error(f"Could not reach Telegram: {e}")
                if cid:
                    user.tg_chat_id = str(cid)
                    s.commit()
                    st.success("Telegram connected ✅")
                else:
                    st.error("Not found yet. Press Start in Telegram, wait a few seconds, then try again.")
            if user.tg_chat_id:
                st.caption("✅ Telegram is connected")

    # ============================================================ Settings
    with tab_set:
        user.enabled = st.toggle("Assistant on", value=user.enabled)

        freq_keys = list(FREQUENCIES)
        user.frequency = st.selectbox("How often?", freq_keys, format_func=FREQUENCIES.get,
                                      index=freq_keys.index(user.frequency)
                                      if user.frequency in freq_keys else 0)
        if user.frequency == "weekly":
            user.send_weekday = WEEKDAYS.index(
                st.selectbox("On which day?", WEEKDAYS, index=int(user.send_weekday or 0)))
        user.send_hour = st.slider("Send at (hour, 0-23)", 0, 23, int(user.send_hour))
        tz_index = TIMEZONES.index(user.timezone) if user.timezone in TIMEZONES else TIMEZONES.index("Europe/Berlin")
        user.timezone = st.selectbox("Time zone", TIMEZONES, index=tz_index)

        mode_keys = list(MODES)
        user.summary_mode = st.radio("Format", mode_keys, format_func=MODES.get,
                                     index=mode_keys.index(user.summary_mode)
                                     if user.summary_mode in mode_keys else 0)
        user.sensitivity = st.select_slider("How strict is the filter?",
                                            ["strict", "normal", "relaxed"], value=user.sensitivity)
        st.caption("Strict = only what clearly needs action. Relaxed = everything except obvious ads. "
                   "If you are afraid of missing something, choose relaxed.")

        user.feat_attachments = st.toggle("Read attachments", value=user.feat_attachments)
        user.feat_drafts = st.toggle("Write reply drafts in my style", value=user.feat_drafts)
        if user.feat_drafts and not user.style_profile:
            st.warning("Drafts need your writing style. Go to the 'My writing style' tab first.")

        user.feat_calendar = st.toggle("Calendar links", value=user.feat_calendar)
        if user.feat_calendar:
            cal_keys = list(CALENDARS)
            user.calendar_type = st.radio("Which calendar do you use?", cal_keys, format_func=CALENDARS.get,
                                          index=cal_keys.index(user.calendar_type)
                                          if user.calendar_type in cal_keys else 0,
                                          horizontal=True)
            if user.calendar_type == "apple":
                st.caption("Apple link: opens a small page of this website where you tap "
                           "'Add to Apple Calendar'. Apple has no direct one-click link.")

        user.feat_send_if_empty = st.toggle("Message me even if nothing is important",
                                            value=user.feat_send_if_empty)

        st.divider()
        prov_keys = list(ai.PROVIDERS)
        user.ai_provider = st.selectbox("AI model", prov_keys, format_func=ai.PROVIDERS.get,
                                        index=prov_keys.index(user.ai_provider)
                                        if user.ai_provider in prov_keys else 0)
        if user.ai_provider == "claude":
            autosave_secret(user, "anthropic_key_enc", secret_input(
                "Own Anthropic API key (optional, otherwise the shared key is used)",
                user.anthropic_key_enc, "ak"))
        else:
            autosave_secret(user, "gemini_key_enc", secret_input(
                "Own Gemini API key (optional, otherwise the shared key is used)",
                user.gemini_key_enc, "gk"))

    # ============================================================ Writing style
    with tab_style:
        st.write("The assistant reads about 25 of your sent emails once and writes down how you write. "
                 "You can correct the result below. Only this description is stored, not your emails.")
        st.session_state.setdefault("style_text", user.style_profile)
        if st.button("Learn my style from my Sent folder"):
            try:
                with st.spinner("Reading your sent mails..."):
                    m = imap_client.connect(user.imap_host, user.imap_port, user.imap_user,
                                            crypto.decrypt(user.imap_password_enc))
                    samples = imap_client.sample_sent(m)
                    m.logout()
                    if len(samples) < 3:
                        st.error("Found too few sent emails to learn from.")
                    else:
                        st.session_state["style_text"] = ai.build_style_profile(ai.get_provider(user), samples)
                        st.success("Done. You can edit the text below, it is saved automatically.")
            except Exception as e:
                st.error(f"Could not learn your style: {e}")
        st.text_area("My writing style (editable)", key="style_text", height=260)
        user.style_profile = st.session_state["style_text"]

    # ============================================================ Preview
    with tab_prev:
        st.write("Creates a summary right now from the same time window the next real run would use. "
                 "It does not use up that run and does not write any drafts.")
        also_send = st.checkbox("Also send it to me via my notification channel")
        if st.button("Create a summary now"):
            s.commit()                          # make sure the latest settings are used
            try:
                with st.spinner("Reading and summarising your mails... this can take a minute"):
                    text = pipeline.run_for_user(user, s, preview=True)
                if text:
                    with st.container(border=True):
                        st.markdown(text.replace("\n", "  \n"))
                    if also_send:
                        notifier.send(user, text)
                        st.success("Sent")
                else:
                    st.info("Nothing important found in this period.")
            except Exception as e:
                st.error(f"Preview failed: {e}")

    # ============================================================ Danger zone
    with st.expander("Delete my account and data"):
        st.write("This removes your account, saved settings and stored passwords/keys. "
                 "To also revoke access at the source, delete the app password in your mail provider.")
        if st.checkbox("Yes, delete everything"):
            if st.button("Delete my account now"):
                s.delete(user)
                s.commit()
                st.session_state.clear()
                st.rerun()

    s.commit()                                  # auto-save: everything changed above is stored
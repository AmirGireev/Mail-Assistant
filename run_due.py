from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import db, pipeline, notifier, crypto

INTERVAL_DAYS = {"daily": 1, "every_3_days": 3, "weekly": 7}


def is_due(u, now_utc):
    now = now_utc.astimezone(ZoneInfo(u.timezone))
    if now.hour < u.send_hour:
        return False
    if u.frequency == "weekly" and now.weekday() != u.send_weekday:
        return False
    if u.last_run is None:
        return True
    last = u.last_run.astimezone(ZoneInfo(u.timezone))
    return (now.date() - last.date()).days >= INTERVAL_DAYS[u.frequency]


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    with db.Session() as s:
        for u in s.query(db.User).filter_by(enabled=True).all():
            if not (u.imap_host and notifier.is_configured(u)) or not is_due(u, now):
                continue
            try:
                text = pipeline.run_for_user(u, s)
                if text:
                    notifier.send(u, text)
                u.last_run = now
                s.commit()
            except Exception as e:  # one broken user must never stop the others
                print(f"user {u.username} failed: {e}")

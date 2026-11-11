from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import db
import notifier
import pipeline


# due check
def is_due(u, now_utc):
    now = now_utc.astimezone(ZoneInfo(u.timezone))
    # too early
    if now.hour < u.send_hour:
        return False
    # wrong weekday
    if u.frequency == "weekly" and now.weekday() != u.send_weekday:
        return False
    # first run
    if u.last_run is None:
        return True
    last = u.last_run.astimezone(ZoneInfo(u.timezone))
    return (now.date() - last.date()).days >= pipeline.INTERVAL_DAYS[u.frequency]


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    with db.Session() as s:
        for u in s.query(db.User).filter_by(enabled=True).all():
            # skip users
            if not (u.imap_host and notifier.is_configured(u)) or not is_due(u, now):
                continue
            try:
                text = pipeline.run_for_user(u)
                if text:
                    notifier.send(u, text)
                u.last_run = now
                s.commit()
            # isolate failures
            except Exception as e:
                print(f"user {u.username} failed: {e}")
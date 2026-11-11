import db
import crypto

def create_user():
    with db.Session() as s:
        # Prüfen, ob der Nutzer schon existiert
        u = s.query(db.User).filter_by(username="Amir").first()
        if not u:
            u = db.User(username="Amir")
            s.add(u)
            print("Neuer Nutzer 'Amir' wurde erstellt.")
        else:
            print("Nutzer 'Amir' existiert bereits. Daten werden aktualisiert.")

        # Grundlegende Einstellungen
        u.password_hash = "testpasswort" # Nur für den Web-Login relevant
        u.enabled = True
        u.notify_channel = "telegram"
        u.ai_provider = "gemini"         # oder "claude"
        
        # Einstellungen für run_due.py anpassen, damit es SOFORT startet
        u.frequency = "daily"
        u.send_hour = 0                  # 0 zwingt das Skript zum sofortigen Start
        u.last_run = None                # Verhindert, dass das Intervall blockiert
        
        # --- IMAP DATEN EINTRAGEN ---
        u.imap_host = "imap.gmail.com"   # oder dein Anbieter
        u.imap_port = 993
        u.imap_user = "amir.gireev05@gmail.com" # DEINE E-MAIL HIER
        u.imap_password_enc = crypto.encrypt("jjag tyqm ctor eoly") # DEIN PASSWORT HIER
        
        # --- TELEGRAM CHAT ID EINTRAGEN ---
        # Ohne Chat-ID kann der Notifier die Nachricht nicht schicken.
        # Finde deine Chat-ID (z.B. über Telegram Bot @userinfobot)
        u.tg_chat_id = "9261159383"       # DEINE TELEGRAM CHAT ID HIER
        
        s.commit()
        print("Nutzerdaten gespeichert! Du kannst jetzt 'python run_due.py' testen.")

if __name__ == "__main__":
    create_user()
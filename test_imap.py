import email
from email.header import decode_header
import imaplib

# Configuration
IMAP_SERVER = "imap.gmail.com"  # e.g., imap.gmail.com, outlook.office365.com
IMAP_PORT = 993
EMAIL_ACCOUNT = "amir.gireev05@gmail.com"
APP_PASSWORD = "jjag tyqm ctor eoly"  # Use an App Password, not normal password!
SINCE_DATE = "01-Nov-2026"  # Format: DD-Mon-YYYY (e.g., 01-Nov-2026)


def decode_str(header_value):
    """Helper to decode encoded email headers (like subjects)."""
    if not header_value:
        return ""
    decoded_parts = decode_header(header_value)
    text = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            text += part.decode(encoding or "utf-8", errors="ignore")
        else:
            text += part
    return text


def connect():
    """Establish SSL connection and log in."""
    print(f"Connecting to {IMAP_SERVER}...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_ACCOUNT, APP_PASSWORD)
    print("Login successful!")
    return mail


def fetch_since(mail, since_date):
    """Select INBOX and fetch subjects for emails since `since_date`."""
    mail.select("INBOX", readonly=True)

    # Search for emails since the given date
    status, data = mail.search(None, f'SINCE "{since_date}"')
    if status != "OK":
        print("Error searching for messages.")
        return

    msg_ids = data[0].split()
    print(f"Found {len(msg_ids)} messages since {since_date}.\n")

    for msg_id in msg_ids:
        # Fetch only header data (BODY.PEEK[HEADER.FIELDS (SUBJECT)]) to stay lightweight
        status, msg_data = mail.fetch(msg_id, "(BODY.PEEK[HEADER.FIELDS (SUBJECT)])")
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = decode_str(msg["Subject"])
                print(f"ID {msg_id.decode()}: {subject}")


if __name__ == "__main__":
    try:
        connection = connect()
        fetch_since(connection, SINCE_DATE)
        connection.logout()
    except imaplib.IMAP4.error as e:
        print(f"\n[IMAP Error] Authentication or command failed: {e}")
        print("Check:")
        print("1. Is IMAP enabled in your provider's settings?")
        print("2. Are you using an 16-character App Password (not your main password)?")
    except Exception as e:
        print(f"\n[Error] {e}")
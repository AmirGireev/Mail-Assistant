import time

import requests


# split message
def split_text(text, limit=900):
    chunks, cur = [], ""
    # keep lines
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit and cur:
            chunks.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur)
    return chunks


# send whatsapp
def send(phone, apikey, text):
    # missing data
    if not phone or not apikey:
        raise RuntimeError("WhatsApp number or CallMeBot API key is missing")
    for chunk in split_text(text):
        r = requests.get("https://api.callmebot.com/whatsapp.php",
                         params={"phone": phone, "text": chunk, "apikey": apikey}, timeout=30)
        r.raise_for_status()
        # check answer
        if "queued" not in r.text.lower():
            raise RuntimeError(f"CallMeBot answered: {r.text[:200]}")
        # rate limit
        time.sleep(5)
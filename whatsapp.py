import time, requests

def split_text(text, limit=900):
    chunks, cur = [], ""
    for line in text.split("\n"):            # split on lines so links never get cut in half
        if len(cur) + len(line) + 1 > limit and cur:
            chunks.append(cur); cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur)
    return chunks

def send(phone, apikey, text):
    for chunk in split_text(text):
        r = requests.get("https://api.callmebot.com/whatsapp.php",
                         params={"phone": phone, "text": chunk, "apikey": apikey}, timeout=30)
        r.raise_for_status()
        time.sleep(5)                         # CallMeBot is rate-limited; don't hammer it
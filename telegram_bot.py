import requests

import config
from whatsapp import split_text


# api call
def _api(method, **params):
    token = config.get("TELEGRAM_BOT_TOKEN")
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=30)
    r.raise_for_status()
    return r.json()


# start link
def link_for(code):
    return f"https://t.me/{_api('getMe')['result']['username']}?start={code}"


# find chat
def find_chat_id(code):
    for upd in _api("getUpdates")["result"]:
        msg = upd.get("message") or {}
        if msg.get("text", "").strip() == f"/start {code}":
            return msg["chat"]["id"]
    return None


# send telegram
def send(chat_id, text):
    for chunk in split_text(text, 3500):
        _api("sendMessage", chat_id=chat_id, text=chunk, link_preview_options={"is_disabled": True})
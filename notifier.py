import crypto, whatsapp, telegram_bot

def is_configured(u):
    if u.notify_channel == "telegram":
        return bool(u.tg_chat_id)
    return bool(u.wa_phone and u.wa_apikey_enc)

def send(u, text):
    if u.notify_channel == "telegram":
        telegram_bot.send(u.tg_chat_id, text.replace("*", ""))     # Telegram shows *bold* markers literally, so remove them
    else:
        whatsapp.send(u.wa_phone, crypto.decrypt(u.wa_apikey_enc), text)
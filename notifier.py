import crypto
import telegram_bot
import whatsapp


# channel ready
def is_configured(u):
    if u.notify_channel == "telegram":
        return bool(u.tg_chat_id)
    return bool(u.wa_phone and u.wa_apikey_enc)


# send message
def send(u, text):
    if u.notify_channel == "telegram":
        # no bold
        telegram_bot.send(u.tg_chat_id, text.replace("*", ""))
    else:
        whatsapp.send(u.wa_phone, crypto.decrypt(u.wa_apikey_enc), text)
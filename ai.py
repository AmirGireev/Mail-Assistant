import base64
import json
import re
import time

import config
import crypto

# file prompt
DESCRIBE_PROMPT = "Describe this document in max 3 sentences. Include dates, amounts and deadlines."

# model names
PROVIDERS = {
    "gemini": "Gemini Flash (free)",
    "claude": "Claude Haiku 5.5 (paid, about cents per month)",
}

# filter rules
SENSITIVITY = {
    "strict": "Only keep mails that clearly require action or contain time-sensitive/financial/legal/personal information.",
    "normal": "Keep mails from real people, appointments, deadlines, bills, authorities, school/work, deliveries needing action.",
    "relaxed": "Keep everything except obvious advertising and automated notifications.",
}

# noise senders
NOISE_SENDERS = ("accounts.google.com", "linkedin.com", "xing.com", "indeed.com", "glassdoor.com",
                 "stepstone.de", "facebookmail.com", "instagram.com", "pinterest.com", "quora.com", "medium.com")

# code mails
CODE_WORDS = re.compile(
    r"verification code|verifizierungscode|best[äa]tigungscode|sicherheitscode|security code|login code|"
    r"anmeldecode|one[- ]time|einmalpasswort|\botp\b|\b(your|dein|ihr)\w* code", re.I)
CODE_NUMBER = re.compile(r"\b\d{4,8}\b")


# parse json
def _parse_json(text):
    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


# gemini model
class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key=None):
        from google import genai
        from google.genai import types

        self.types = types
        # model order
        self.models = [config.get("GEMINI_MODEL", "gemini-3.5-flash"),
                       config.get("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")]
        self.client = genai.Client(api_key=api_key or config.get("GEMINI_API_KEY"))
        self.tokens_in = self.tokens_out = 0

    # api call
    def _call(self, contents, json_mode):
        cfg = self.types.GenerateContentConfig(
            response_mime_type="application/json" if json_mode else None)
        for attempt in range(3):
            # flash, then lite
            for model in self.models:
                try:
                    r = self.client.models.generate_content(model=model, contents=contents, config=cfg)
                    # count tokens
                    u = r.usage_metadata
                    if u:
                        self.tokens_in += u.prompt_token_count or 0
                        self.tokens_out += u.candidates_token_count or 0
                    return r.text
                except Exception as e:
                    # busy only
                    if not any(w in str(e) for w in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "overloaded")):
                        raise
            # wait, retry
            time.sleep(20 * (attempt + 1))
        raise RuntimeError("Gemini is busy, try again later")

    # json answer
    def json(self, prompt):
        return _parse_json(self._call([prompt], True))

    # text answer
    def text(self, prompt):
        return self._call([prompt], False).strip()

    # read file
    def describe_file(self, data: bytes, mime: str):
        part = self.types.Part.from_bytes(data=data, mime_type=mime)
        return self._call([part, DESCRIBE_PROMPT], False).strip()


# claude model
class ClaudeProvider:
    name = "claude"

    def __init__(self, api_key=None):
        import anthropic

        self.model = config.get("ANTHROPIC_MODEL", "claude-haiku-5-5")
        self.client = anthropic.Anthropic(api_key=api_key or config.get("ANTHROPIC_API_KEY"), max_retries=4)
        self.tokens_in = self.tokens_out = 0

    # api call
    def _call(self, content):
        r = self.client.messages.create(model=self.model, max_tokens=4096,
                                        messages=[{"role": "user", "content": content}])
        self.tokens_in += r.usage.input_tokens
        self.tokens_out += r.usage.output_tokens
        return "".join(b.text for b in r.content if b.type == "text")

    # json answer
    def json(self, prompt):
        # retry once
        for _ in range(2):
            raw = self._call(prompt + "\n\nReturn ONLY the JSON object, no other text.")
            try:
                return _parse_json(raw)
            except ValueError:
                continue
        raise RuntimeError("Claude did not return valid JSON")

    # text answer
    def text(self, prompt):
        return self._call(prompt).strip()

    # read file
    def describe_file(self, data: bytes, mime: str):
        b64 = base64.standard_b64encode(data).decode()
        kind = "document" if mime == "application/pdf" else "image"
        block = {"type": kind, "source": {"type": "base64", "media_type": mime, "data": b64}}
        return self._call([block, {"type": "text", "text": DESCRIBE_PROMPT}]).strip()


# pick model
def get_provider(u):
    if u.ai_provider == "claude":
        return ClaudeProvider(crypto.decrypt(u.anthropic_key_enc) or None)
    return GeminiProvider(crypto.decrypt(u.gemini_key_enc) or None)


# skip noise
def is_noise(mail):
    # known senders
    if any(d in mail["from"].lower() for d in NOISE_SENDERS):
        return True
    # short code mail
    head = mail["subject"] + " " + mail["body"][:500]
    return len(mail["body"]) < 800 and bool(CODE_WORDS.search(head)) and bool(CODE_NUMBER.search(head))


# sort mails
def analyse_batch(cl, mails, sensitivity="normal", today_iso=""):
    items = [{
        "id": m["id"], "from": m["from"], "subject": m["subject"],
        "bulk_hint": m["bulk_hint"], "text": m["body"][:1500],
        "attachments_text": m.get("att_text", "")[:3000],
    } for m in mails]
    prompt = f"""You triage emails for a person who hates reading email. Today is {today_iso}.
Rule: {SENSITIVITY[sensitivity]}
NOT important, always exclude: newsletters, marketing and promotions, social-media and job-platform notifications
(LinkedIn, Xing, Indeed, job alerts, "someone viewed your profile"), automatic digests, verification / confirmation /
login codes, routine account and security notifications (Google, Apple, Microsoft: "security alert", "new sign-in",
"password changed").
Important: mails from a real person to the user, appointments, deadlines, bills and payment demands, authorities,
school / university / work, contracts, and real fraud such as a suspicious payment.
An automated mail that needs no action from the user is NOT important. If a mail from a real person is unclear, mark it important.
Answer in the language of each email.
Return JSON: {{"emails":[{{
  "id": str,
  "important": bool,
  "sender_name": str,
  "one_sentence": str,            // what it is and what (if anything) the user must do
  "needs_reply": bool,
  "event": null | {{"title": str, "start": "YYYY-MM-DDTHH:MM:SS", "end": "YYYY-MM-DDTHH:MM:SS or null",
                    "all_day": bool, "location": str}}   // only for real appointments/deadlines with a concrete date
}}]}}
Emails: {json.dumps(items, ensure_ascii=False)}"""
    return cl.json(prompt)["emails"]


# short overview
def short_summary(cl, important):
    lines = "\n".join(f"- {m['sender_name']}: {m['one_sentence']}" for m in important)
    return cl.text(f"""Write a short overview (max 5 sentences, same language as the notes) of these important emails.
Put every sentence on its own line. Mention what needs action first.
No greeting, no bullet characters, no markdown headings.
{lines}""")


# writing style
def build_style_profile(cl, samples):
    return cl.text("Analyse these emails written by one person. Describe in 8 bullet points how they write: "
                   "language, formality, greeting, sign-off, sentence length, typical phrases, emoji use, punctuation habits. "
                   "Be concrete.\n\n" + "\n\n---\n\n".join(samples))


# reply draft
def write_draft(cl, style_profile, original_mail):
    return cl.text(f"""Write a reply to this email, exactly in this writing style:
{style_profile}

Rules: same language as the original; short; do NOT invent facts, prices, dates or commitments;
where information is missing write [PLEASE FILL IN]. Output only the email body, no subject.

Original from {original_mail['from']}:
{original_mail['body'][:3000]}""")
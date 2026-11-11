from cryptography.fernet import Fernet

import config

# cipher
_f = Fernet(config.get("ENCRYPTION_KEY").encode())


# lock text
def encrypt(text: str) -> str:
    return _f.encrypt(text.encode()).decode() if text else ""


# unlock text
def decrypt(token: str) -> str:
    return _f.decrypt(token.encode()).decode() if token else ""
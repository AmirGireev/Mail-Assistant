from cryptography.fernet import Fernet
import config

_f = Fernet(config.get("ENCRYPTION_KEY").encode())

def encrypt(text: str) -> str:
    return _f.encrypt(text.encode()).decode() if text else ""

def decrypt(token: str) -> str:
    return _f.decrypt(token.encode()).decode() if token else ""
import base64
import hashlib
from cryptography.fernet import Fernet

from dymo_saas_core.core.config import settings

def get_fernet() -> Fernet:
    try:
        # Check if the configured key is directly valid
        key_bytes = settings.ENCRYPTION_KEY.strip().encode()
        return Fernet(key_bytes)
    except Exception:
        # Fallback to deriving a valid 32-byte URL-safe base64 key using SHA-256
        raw_key = settings.ENCRYPTION_KEY.encode()
        hashed = hashlib.sha256(raw_key).digest()
        derived_key = base64.urlsafe_b64encode(hashed)
        return Fernet(derived_key)

_fernet = get_fernet()

def encrypt_secret(plain_text: str) -> str:
    if not plain_text:
        return ""
    return _fernet.encrypt(plain_text.encode()).decode()

def decrypt_secret(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    try:
        return _fernet.decrypt(cipher_text.encode()).decode()
    except Exception:
        # If decryption fails, return the cipher text as is (or log the failure)
        return cipher_text

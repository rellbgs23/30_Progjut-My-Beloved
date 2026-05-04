from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def get_fernet():
    if not settings.FIELD_ENCRYPTION_KEY:
        raise ValueError("FIELD_ENCRYPTION_KEY is not configured.")

    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


def encrypt_text(plain_text):
    if plain_text is None:
        plain_text = ""

    return get_fernet().encrypt(plain_text.encode()).decode()


def decrypt_text(cipher_text):
    try:
        return get_fernet().decrypt(cipher_text.encode()).decode()
    except InvalidToken:
        raise ValueError("Invalid encrypted data.")
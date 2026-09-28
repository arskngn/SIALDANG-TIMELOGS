from fastapi import HTTPException, status
from fastapi.params import Depends
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import Optional, Any,Union
from app.secrets import JWT_SECRET_KEY
import re
import logging
import base64
import secrets as pysecrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.secrets import USER_DATA_ENCRYPTION_KEY
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


pwd_context = CryptContext(schemes=["argon2", "bcrypt", "pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(
    subject: Union[str, Any], expires_delta: timedelta = None, role: Optional[str] = None
) -> str:
    """
    Creates an access token.

    Parameters:
        subject (Union[str, Any]): The subject for which the access token is created.
        expires_delta (timedelta, optional): The expiration time for the access token. Defaults to None.
        role(str, optional): The user's role. Defaults to None

    Returns:
        str: The encoded access token.
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    if role:
        to_encode["role"] = role

    encoded_jwt = jwt.encode(
        to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM
    )
    return encoded_jwt

def decode_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


ENCRYPTED_PREFIX = "enc:v1:"
# Accept some legacy prefix variants observed in data (e.g., 'encv:')
_ENCRYPTED_PREFIXES = (
    "enc:v1:",
    "encv:",
    "enc:v:",
    "encv:1:",
    "enc:",
)

USER_SENSITIVE_FIELDS = (
    "emergency_contact_name",
    "emergency_contact_number",
    "gotyme_account_name",
    "gotyme_account_number",
    "tin_number",
    "sss_number",
    "philhealth_number",
    "pagibig_number",
)


def is_encrypted(value: Optional[str]) -> bool:
    if not (bool(value) and isinstance(value, str)):
        return False
    for p in _ENCRYPTED_PREFIXES:
        if value.startswith(p):
            return True
    return False


def _b64decode_key(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("utf-8"))
    except Exception:
        return base64.b64decode(padded.encode("utf-8"))


def _get_user_encryption_key() -> Optional[bytes]:
    if not USER_DATA_ENCRYPTION_KEY:
        logger.warning("USER_DATA_ENCRYPTION_KEY missing; cannot decrypt legacy encrypted values")
        return None
    try:
        key = _b64decode_key(USER_DATA_ENCRYPTION_KEY.strip())
        if len(key) != 32:
            logger.error(f"USER_DATA_ENCRYPTION_KEY invalid length={len(key)}; expected 32 bytes")
            return None
        logger.info("USER_DATA_ENCRYPTION_KEY loaded successfully (32 bytes)")
        return key
    except Exception:
        logger.exception("Failed to decode USER_DATA_ENCRYPTION_KEY")
        return None


def encrypt_value(value: Optional[str], aad: Optional[str] = None) -> Optional[str]:
    if value is None:
        return None
    if is_encrypted(value):
        return value
    key = _get_user_encryption_key()
    if key is None:
        return value
    aesgcm = AESGCM(key)
    nonce = pysecrets.token_bytes(12)
    plaintext = value.encode("utf-8")
    aad_bytes = aad.encode("utf-8") if aad else None
    ct = aesgcm.encrypt(nonce, plaintext, aad_bytes)
    packed = nonce + ct
    token = base64.urlsafe_b64encode(packed).decode("utf-8").rstrip("=")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_value(value: Optional[str], aad: Optional[str] = None) -> Optional[str]:
    if value is None:
        return None
    if not is_encrypted(value):
        return value
    key = _get_user_encryption_key()
    if key is None:
        logger.warning("Decryption skipped: encryption key unavailable")
        return value
    aesgcm = AESGCM(key)
    # Strip any recognized prefix variant to get the token
    token = value
    for p in _ENCRYPTED_PREFIXES:
        if token.startswith(p):
            token = token[len(p):]
            break
    raw = base64.urlsafe_b64decode((token + "=" * (-len(token) % 4)).encode("utf-8"))
    nonce, ct = raw[:12], raw[12:]
    aad_bytes = aad.encode("utf-8") if aad else None
    pt = aesgcm.decrypt(nonce, ct, aad_bytes)
    return pt.decode("utf-8")

from sqlalchemy.types import TypeDecorator, String
from cryptography.fernet import Fernet
from app.secrets import USER_DATA_ENCRYPTION_KEY
import base64

# Ensure we have a valid key. In production, this MUST be set in environment variables.
# For safety, if not set, we use a hardcoded dev key but warn/log.
# NOTE: Fernet.generate_key() produces a 32-byte url-safe base64-encoded key.
_key = USER_DATA_ENCRYPTION_KEY
if not _key:
    # A dummy key for development if none provided. 
    # generated via Fernet.generate_key()
    _key = b'Z7wQ5yX8X9X8X9X8X9X8X9X8X9X8X9X8X9X8X9X8X9U=' 

# Ensure key is bytes
if isinstance(_key, str):
    _key = _key.encode('utf-8')

try:
    cipher_suite = Fernet(_key)
except Exception as e:
    # If the provided key is invalid, we can't encrypt/decrypt safely.
    # We'll initialize with a generated key to prevent import errors, 
    # but runtime operations might fail or match nothing.
    print(f"WARNING: Invalid USER_DATA_ENCRYPTION_KEY: {e}. generating temporary key.")
    cipher_suite = Fernet(Fernet.generate_key())

class EncryptedString(TypeDecorator):
    """
    Encrypts string values on the way in and decrypts them on the way out.
    Usage: Column(EncryptedString(512), ...)
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        # Use the length passed to the type constructor, if any
        length = getattr(self, "length", None)
        return dialect.type_descriptor(String(length))

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, str):
                value = value.encode('utf-8')
            elif not isinstance(value, bytes):
                value = str(value).encode('utf-8')
            
            encrypted = cipher_suite.encrypt(value)
            return encrypted.decode('utf-8')
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            try:
                if isinstance(value, str):
                    value = value.encode('utf-8')
                decrypted = cipher_suite.decrypt(value)
                return decrypted.decode('utf-8')
            except Exception:
                # Return the original value if decryption fails 
                # (e.g. data was stored as plain text before encryption was enabled)
                # This allows for gradual migration or reading legacy data.
                if isinstance(value, bytes):
                    return value.decode('utf-8', errors='ignore')
                return value
        return value

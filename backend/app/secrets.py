from dotenv import load_dotenv
import os
import secrets as pysecrets
from pathlib import Path

# Load environment variables from .env file.
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)

# Access variables loaded from .env
DB_USER = os.getenv("DB_USER")
DATABASE = os.getenv("DATABASE")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or "dev_insecure_secret_change_me"
USER_DATA_ENCRYPTION_KEY = os.getenv("USER_DATA_ENCRYPTION_KEY")


# Default timezone used by the backend when converting datetimes
# Can be overridden by setting DEFAULT_TIMEZONE in the environment (e.g. "UTC" or "Asia/Manila")
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE")


# Default to Asia/Manila for local development when not explicitly set.
# If DEFAULT_TIMEZONE env var is provided, that value is used instead.
if DEFAULT_TIMEZONE is None:
	try:
		from datetime import datetime, timezone

		_local_tz = datetime.now(timezone.utc).astimezone().tzinfo
		_tzname = getattr(_local_tz, "key", None) or getattr(_local_tz, "zone", None)
		if _tzname:
			DEFAULT_TIMEZONE = _tzname
		else:
			# Last-resort: try environment TZ, else use Asia/Manila for locals
			DEFAULT_TIMEZONE = os.getenv("TZ", "Asia/Manila")
	except Exception:
		DEFAULT_TIMEZONE = os.getenv("TZ", "Asia/Manila") or "Asia/Manila"

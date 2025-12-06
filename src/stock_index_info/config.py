"""Configuration for the Stock Index Info Telegram Bot."""

import os
from pathlib import Path


# Telegram Bot Token - must be set via environment variable
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Allowed Telegram user IDs - comma-separated list in env var
# Example: ALLOWED_USER_IDS=123456789,987654321
_allowed_ids_str = os.environ.get("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: set[int] = {
    int(uid.strip()) for uid in _allowed_ids_str.split(",") if uid.strip()
}

# Database path
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DATA_DIR / "indices.db"

# Scheduled sync settings
# Hour of day to run sync (0-23), default 2 AM
SYNC_HOUR: int = int(os.environ.get("SYNC_HOUR", "2"))
SYNC_MINUTE: int = int(os.environ.get("SYNC_MINUTE", "0"))


def validate_config() -> list[str]:
    """Validate configuration and return list of errors."""
    errors: list[str] = []
    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN environment variable is not set")
    if not ALLOWED_USER_IDS:
        errors.append("ALLOWED_USER_IDS environment variable is not set or empty")
    return errors

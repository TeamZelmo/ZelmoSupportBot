"""Configuration loader for the Telegram Support Bot.

Values are read from the ``.env`` file (or real environment variables).
Call :func:`validate_config` once at start-up to get a clear error message
if anything is missing or invalid.
"""

import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class ConfigError(Exception):
    """Raised when the configuration is missing or invalid."""


def _get_env(name: str) -> str:
    return os.getenv(name, "").strip()


def _is_placeholder(value: str) -> bool:
    return not value or value.upper().startswith("YOUR_")


def _to_int(value: str) -> Optional[int]:
    """Safely convert a string to int. Returns None if not possible."""
    if _is_placeholder(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _resolve_db_path(raw: str) -> str:
    path = Path(raw or "data/bot.db")
    if not path.is_absolute():
        path = BASE_DIR / path
    return str(path)


BOT_TOKEN: str = _get_env("BOT_TOKEN")

PARTNER1_ID: Optional[int] = _to_int(_get_env("PARTNER1_ID"))
PARTNER2_ID: Optional[int] = _to_int(_get_env("PARTNER2_ID"))
PARTNER3_ID: Optional[int] = _to_int(_get_env("PARTNER3_ID"))

PARTNER_IDS = tuple(
    pid for pid in (PARTNER1_ID, PARTNER2_ID, PARTNER3_ID) if pid is not None
)

PARTNER_GROUP_ID: Optional[int] = _to_int(_get_env("PARTNER_GROUP_ID"))

DATABASE_PATH: str = _resolve_db_path(_get_env("DATABASE_PATH"))


def validate_config() -> None:
    """Validate configuration. Raises ConfigError listing every problem."""
    errors: List[str] = []

    if _is_placeholder(BOT_TOKEN) or ":" not in BOT_TOKEN:
        errors.append("BOT_TOKEN missing/invalid (BotFather se mila token .env me daalein).")

    for index, pid in enumerate((PARTNER1_ID, PARTNER2_ID, PARTNER3_ID), start=1):
        if pid is None:
            errors.append(f"PARTNER{index}_ID missing/invalid (numeric Telegram ID chahiye).")
        elif pid <= 0:
            errors.append(f"PARTNER{index}_ID positive number hona chahiye.")

    if len(set(PARTNER_IDS)) != len(PARTNER_IDS):
        errors.append("PARTNER1_ID, PARTNER2_ID, PARTNER3_ID alag-alag hone chahiye.")

    if PARTNER_GROUP_ID is None:
        errors.append("PARTNER_GROUP_ID missing/invalid (jaise -1001234567890).")

    if errors:
        raise ConfigError(
            "Configuration error:\n" + "\n".join(f" - {e}" for e in errors)
        )

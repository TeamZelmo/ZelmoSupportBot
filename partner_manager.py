"""Partner-related business logic (authorisation, status, availability)."""

import logging
from typing import Optional, Tuple

import config
import database

logger = logging.getLogger(__name__)

AVAILABLE = "available"
BUSY = "busy"
OFFLINE = "offline"


def is_partner(user_id: Optional[int]) -> bool:
    """True only for the partner IDs configured in .env."""
    return user_id is not None and user_id in config.PARTNER_IDS


def register_configured_partners() -> None:
    """Make sure every configured partner has a row in the partners table."""
    for partner_id in config.PARTNER_IDS:
        database.add_partner(partner_id)


def get_status(partner_id: int) -> Optional[str]:
    return database.get_partner_status(partner_id)


def change_status(partner_id: int, status: str) -> bool:
    """Change a partner's status. Unauthorised users / bad status -> False."""
    if not is_partner(partner_id) or status not in database.VALID_STATUSES:
        return False
    database.add_partner(partner_id)  # no-op if already registered
    return database.set_partner_status(partner_id, status)


def get_availability_state() -> str:
    """Overall team state: 'available', 'busy' or 'offline'."""
    if database.get_available_partners():
        return AVAILABLE
    statuses = [database.get_partner_status(pid) for pid in config.PARTNER_IDS]
    if any(s == database.STATUS_BUSY for s in statuses):
        return BUSY
    return OFFLINE


def can_take_chat(partner_id: int) -> Tuple[bool, str]:
    """Return (allowed, reason). reason is 'ok', 'unauthorized' or 'offline'."""
    if not is_partner(partner_id):
        return False, "unauthorized"
    if database.get_partner_status(partner_id) in (None, database.STATUS_OFFLINE):
        return False, "offline"
    return True, "ok"


def can_manage_customer(partner_id: int, customer_id: int) -> bool:
    """A partner may reply/close only chats currently assigned to them."""
    if not is_partner(partner_id):
        return False
    return database.get_customer_partner(customer_id) == partner_id

"""Customer-related business logic."""

import logging
from typing import Any, Dict, List, Optional

import database

logger = logging.getLogger(__name__)


def parse_customer_id(callback_data: Optional[str], prefix: str) -> Optional[int]:
    """Extract the id from '<prefix>:<id>'. Returns None if malformed."""
    if not callback_data:
        return None
    parts = callback_data.split(":")
    if len(parts) != 2 or parts[0] != prefix or not parts[1].isdigit():
        return None
    return int(parts[1])


def display_name(customer: Optional[Dict[str, Any]], fallback_id: Optional[int] = None) -> str:
    if customer and customer.get("first_name"):
        return customer["first_name"]
    return f"Customer {fallback_id}" if fallback_id is not None else "Customer"


def register_customer(user) -> Dict[str, Any]:
    """Register a new customer or refresh the name/username of an existing one."""
    return database.add_customer(user.id, user.first_name, user.username)


def get_customer(customer_id: int) -> Optional[Dict[str, Any]]:
    return database.get_customer(customer_id)


def save_customer_message(customer_id: int, telegram_message_id: int, text: str) -> int:
    return database.save_message(
        customer_id, telegram_message_id, customer_id, database.DIRECTION_CUSTOMER, text
    )


def save_partner_reply(
    customer_id: int, partner_id: int, telegram_message_id: int, text: str
) -> int:
    return database.save_message(
        customer_id, telegram_message_id, partner_id, database.DIRECTION_PARTNER, text
    )


def get_recent_messages(customer_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    return database.get_customer_messages(customer_id, limit)


def get_assigned_partner(customer_id: int) -> Optional[int]:
    return database.get_customer_partner(customer_id)


def get_open_chat(customer_id: int) -> Optional[Dict[str, Any]]:
    return database.get_open_chat(customer_id)


def get_pending_chat(customer_id: int) -> Optional[Dict[str, Any]]:
    chat = database.get_open_chat(customer_id)
    if chat and chat["status"] == database.CHAT_PENDING:
        return chat
    return None


def create_pending_chat(customer_id: int, group_message_id: int) -> int:
    return database.create_chat(customer_id, group_message_id)


def get_pending_customers() -> List[Dict[str, Any]]:
    return database.get_pending_customers()


def assign_chat(customer_id: int, partner_id: int) -> bool:
    """Atomically give the customer to a partner. False if already taken."""
    if not database.set_customer_partner(customer_id, partner_id, only_if_unassigned=True):
        return False
    if not database.set_chat_active(customer_id, partner_id):
        # No pending chat row (e.g. stale button): create an active one.
        database.create_chat(customer_id, None)
        database.set_chat_active(customer_id, partner_id)
    return True


def rollback_assignment(customer_id: int) -> None:
    """Undo assign_chat (used when the partner cannot be messaged)."""
    database.set_customer_partner(customer_id, None)
    database.set_chat_pending(customer_id)


def finish_chat(customer_id: int) -> Optional[Dict[str, Any]]:
    """Close the customer's chat and remove the assignment.

    Returns the chat row as it was before closing (to update the group message).
    """
    chat = database.get_open_chat(customer_id)
    database.close_chat(customer_id)
    return chat

"""All InlineKeyboardMarkup builders.

Callback data formats (must match the patterns in main.py):
    status_available | status_busy | status_offline
    take_chat:<customer_id>
    reply:<customer_id>
    close_chat:<customer_id>
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

CB_STATUS_AVAILABLE = "status_available"
CB_STATUS_BUSY = "status_busy"
CB_STATUS_OFFLINE = "status_offline"
CB_TAKE_CHAT = "take_chat"
CB_REPLY = "reply"
CB_CLOSE_CHAT = "close_chat"


def partner_status_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🟢 Available", callback_data=CB_STATUS_AVAILABLE)],
            [InlineKeyboardButton("🟡 Busy", callback_data=CB_STATUS_BUSY)],
            [InlineKeyboardButton("🔴 Offline", callback_data=CB_STATUS_OFFLINE)],
        ]
    )


def take_chat_keyboard(customer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎯 Take Chat", callback_data=f"{CB_TAKE_CHAT}:{customer_id}")]]
    )


def reply_keyboard(customer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💬 Reply", callback_data=f"{CB_REPLY}:{customer_id}"),
                InlineKeyboardButton(
                    "❌ Close Chat", callback_data=f"{CB_CLOSE_CHAT}:{customer_id}"
                ),
            ]
        ]
    )

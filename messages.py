"""All user-facing texts (plain text, no parse_mode) in one place."""

from typing import Dict, List, Optional

MAX_TEXT_LENGTH = 3500  # keeps notification + header below Telegram's 4096 limit

STATUS_LABELS: Dict[str, str] = {
    "available": "🟢 Available",
    "busy": "🟡 Busy",
    "offline": "🔴 Offline",
}


def truncate(text: str, limit: int = MAX_TEXT_LENGTH) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _customer_line(name: str, username: Optional[str]) -> str:
    return f"{name} (@{username})" if username else name


# ---------------------------------------------------------------- customer side
def welcome_message() -> str:
    return (
        "👋 Welcome to Customer Support!\n\n"
        "अपना सवाल या समस्या यहाँ भेजें।\n\n"
        "हमारी support team जल्द ही आपकी मदद करेगी।"
    )


def message_received_message() -> str:
    return "✅ आपका message support team तक पहुँच गया है।\nकृपया थोड़ी देर प्रतीक्षा करें।"


def all_offline_message() -> str:
    return "🔴 हमारी support team अभी offline है।\n\nकृपया कुछ समय बाद दोबारा message करें।"


def all_busy_message() -> str:
    return "🟡 हमारी सभी support executives इस समय busy हैं।\n\nकृपया थोड़ी देर प्रतीक्षा करें।"


def chat_taken_message() -> str:
    return (
        "👨‍💼 हमारी support team का एक member अब आपकी chat संभाल रहा है।\n\n"
        "आप अपना message भेज सकते हैं।"
    )


def chat_closed_customer_message() -> str:
    return (
        "✅ आपकी support chat close कर दी गई है।\n\n"
        "अगर आपको फिर से सहायता चाहिए तो नया message भेज सकते हैं।"
    )


def partner_reply_to_customer_message(text: str) -> str:
    return f"👨‍💼 Support Team:\n\n{text}"


def text_only_message() -> str:
    return "⚠️ कृपया अपना सवाल text message के रूप में भेजें।"


def delivery_failed_message() -> str:
    return "⚠️ आपका message अभी deliver नहीं हो पाया। कृपया थोड़ी देर बाद दोबारा कोशिश करें।"


def generic_error_message() -> str:
    return "⚠️ कुछ गड़बड़ हो गई। कृपया थोड़ी देर बाद दोबारा कोशिश करें।"


# ---------------------------------------------------------------- group texts
def new_customer_message(
    customer_name: str, customer_id: int, text: str, username: Optional[str] = None
) -> str:
    return (
        "📩 NEW CUSTOMER MESSAGE\n\n"
        f"👤 Customer: {_customer_line(customer_name, username)}\n"
        f"🆔 Customer ID: {customer_id}\n\n"
        f"💬 Message:\n{truncate(text)}"
    )


def pending_followup_message(customer_name: str, customer_id: int, text: str) -> str:
    return (
        "➕ ADDITIONAL MESSAGE (chat abhi tak koi nahi le paaya)\n\n"
        f"👤 Customer: {customer_name}\n"
        f"🆔 Customer ID: {customer_id}\n\n"
        f"💬 Message:\n{truncate(text)}"
    )


def chat_taken_group_message(customer_name: str, customer_id: int, partner_name: str) -> str:
    return (
        "✅ CHAT TAKEN\n\n"
        f"👤 Customer: {customer_name}\n"
        f"🆔 Customer ID: {customer_id}\n"
        f"👨‍💼 Handled by: {partner_name}"
    )


def chat_closed_group_message(customer_name: str, customer_id: int, partner_name: str) -> str:
    return (
        "🔒 CHAT CLOSED\n\n"
        f"👤 Customer: {customer_name}\n"
        f"🆔 Customer ID: {customer_id}\n"
        f"👨‍💼 Closed by: {partner_name}"
    )


# ---------------------------------------------------------------- partner side
def partner_welcome_message() -> str:
    return (
        "👨‍💼 Partner account verified.\n\n"
        "/panel - अपना status बदलें\n"
        "/pending - waiting customers देखें\n\n"
        "Customer chats यहीं (private chat में) आएँगी।"
    )


def panel_message(current_status: Optional[str]) -> str:
    label = STATUS_LABELS.get(current_status or "", "—")
    return f"👨‍💼 Partner Panel\n\nवर्तमान status: {label}\n\nनया status चुनें:"


def status_updated_message(status: str) -> str:
    return f"✅ Status update हो गया: {STATUS_LABELS.get(status, status)}"


def unauthorized_message() -> str:
    return "⛔ आप authorized partner नहीं हैं।"


def partner_idle_message() -> str:
    return (
        "ℹ️ अभी कोई reply mode active नहीं है।\n"
        "Customer को reply करने के लिए उसके message के नीचे 💬 Reply button दबाएँ।"
    )


def partner_offline_cannot_take_message() -> str:
    return "🔴 आप Offline हैं। Chat लेने के लिए पहले /panel से Available या Busy करें।"


def chat_already_taken_message() -> str:
    return "⚠️ यह chat पहले ही किसी partner ने ले ली है।"


def chat_taken_alert_message() -> str:
    return "✅ Chat आपको assign हो गई। Bot के private chat में देखें।"


def partner_must_start_bot_message() -> str:
    return "⚠️ पहले bot को private chat में खोलकर /start भेजें, फिर दोबारा Take Chat दबाएँ।"


def invalid_request_message() -> str:
    return "⚠️ Invalid request."


def invalid_customer_message() -> str:
    return "⚠️ Customer नहीं मिला।"


def not_your_chat_message() -> str:
    return "⛔ यह chat आपको assign नहीं है।"


def partner_chat_started_message(
    customer_name: str, customer_id: int, history: List[dict], username: Optional[str] = None
) -> str:
    lines = [
        "🎯 आपने यह chat ले ली है।",
        "",
        f"👤 Customer: {_customer_line(customer_name, username)}",
        f"🆔 Customer ID: {customer_id}",
        "",
        "📜 Recent messages:",
    ]
    for item in history:
        who = "👤" if item["direction"] == "customer" else "👨‍💼"
        lines.append(f"{who} {truncate(item['message_text'], 300)}")
    return truncate("\n".join(lines), 3900)


def customer_message_to_partner(customer_name: str, customer_id: int, text: str) -> str:
    return (
        "💬 Customer का नया message\n\n"
        f"👤 {customer_name} (ID: {customer_id})\n\n"
        f"{truncate(text)}"
    )


def reply_prompt_message() -> str:
    return (
        "✍️ अपना reply लिखें।\n"
        "आपका अगला message सीधे customer को भेजा जाएगा।\n\n"
        "❌ Cancel करने के लिए /cancel भेजें।"
    )


def reply_sent_message() -> str:
    return "✅ आपका reply customer को भेज दिया गया।"


def reply_cancelled_message() -> str:
    return "❌ Reply cancel कर दिया गया।"


def reply_text_only_message() -> str:
    return "⚠️ कृपया text reply भेजें, या /cancel करें।"


def reply_too_long_message() -> str:
    return f"⚠️ Reply बहुत लंबा है (अधिकतम {MAX_TEXT_LENGTH} अक्षर)। छोटा करके भेजें।"


def reply_not_allowed_message() -> str:
    return "⛔ यह chat अब आपको assigned नहीं है (शायद close हो चुकी है)।"


def customer_unreachable_message() -> str:
    return "⚠️ Customer तक message नहीं पहुँचा (शायद उन्होंने bot block किया है)।"


def chat_closed_partner_message(customer_name: str, customer_id: int) -> str:
    return f"🔒 Chat closed: {customer_name} (ID: {customer_id})"


def chat_closed_alert_message() -> str:
    return "✅ Chat close हो गई।"


def pending_list_message(customers: List[dict]) -> str:
    if not customers:
        return "✅ कोई customer waiting में नहीं है।"
    lines = [f"⏳ Waiting customers: {len(customers)}", ""]
    for c in customers:
        name = c.get("first_name") or "Customer"
        lines.append(f"• {name} (ID: {c['telegram_id']})")
    lines.append("\nइन्हें partner group में Take Chat button से लें।")
    return "\n".join(lines)

"""Telegram handlers (all async)."""

import logging
from typing import Optional

from telegram import Update
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import ContextTypes, ConversationHandler

import config
import customer_manager
import keyboards
import messages as msg
import partner_manager

logger = logging.getLogger(__name__)

# ConversationHandler state: partner is typing a reply
WAITING_REPLY = 1

REPLY_KEY = "reply_customer_id"


# ----------------------------------------------------------------- helpers
async def _safe_edit(query, text: str, reply_markup=None) -> None:
    """Edit the message of a callback query, ignoring harmless errors."""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            logger.warning("edit_message_text failed: %s", exc)
    except TelegramError as exc:
        logger.warning("edit_message_text failed: %s", exc)


async def _safe_send(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, **kwargs):
    """Send a message; return the Message or None on Telegram errors."""
    try:
        return await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
    except TelegramError as exc:
        logger.warning("send_message to %s failed: %s", chat_id, exc)
        return None


# ----------------------------------------------------------------- /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return
    if partner_manager.is_partner(user.id):
        await message.reply_text(msg.partner_welcome_message())
        return
    customer_manager.register_customer(user)
    await message.reply_text(msg.welcome_message())


# ----------------------------------------------------------------- customer
async def _forward_to_partner(update, context, partner_id: int, text: str) -> None:
    user = update.effective_user
    sent = await _safe_send(
        context,
        partner_id,
        msg.customer_message_to_partner(user.first_name or f"Customer {user.id}", user.id, text),
        reply_markup=keyboards.reply_keyboard(user.id),
    )
    if sent is None:
        await update.effective_message.reply_text(msg.delivery_failed_message())


async def customer_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return

    # Partners are never treated as customers.
    if partner_manager.is_partner(user.id):
        await message.reply_text(msg.partner_idle_message())
        return

    text = (message.text or "").strip()
    if not text:
        await message.reply_text(msg.text_only_message())
        return

    customer = customer_manager.register_customer(user)
    customer_manager.save_customer_message(user.id, message.message_id, text)
    name = customer_manager.display_name(customer, user.id)

    # 1) Already assigned -> forward to that partner
    partner_id = customer_manager.get_assigned_partner(user.id)
    if partner_id is not None and not partner_manager.is_partner(partner_id):
        # Assigned partner is no longer configured: drop the stale assignment.
        customer_manager.finish_chat(user.id)
        partner_id = None
    if partner_id is not None:
        await _forward_to_partner(update, context, partner_id, text)
        return

    # 2) Waiting in the group already -> post follow-up there
    pending = customer_manager.get_pending_chat(user.id)
    if pending is not None:
        kwargs = {}
        if pending.get("group_message_id"):
            kwargs = {"reply_to_message_id": pending["group_message_id"]}
        sent = await _safe_send(
            context,
            config.PARTNER_GROUP_ID,
            msg.pending_followup_message(name, user.id, text),
            **kwargs,
        )
        if sent is None:
            # Group reply target may be gone; retry without reply reference.
            sent = await _safe_send(
                context,
                config.PARTNER_GROUP_ID,
                msg.pending_followup_message(name, user.id, text),
            )
        if sent is None:
            await message.reply_text(msg.delivery_failed_message())
        else:
            await message.reply_text(msg.message_received_message())
        return

    # 3) New conversation -> check partner availability
    state = partner_manager.get_availability_state()
    if state == partner_manager.OFFLINE:
        await message.reply_text(msg.all_offline_message())
        return
    if state == partner_manager.BUSY:
        await message.reply_text(msg.all_busy_message())
        return

    sent = await _safe_send(
        context,
        config.PARTNER_GROUP_ID,
        msg.new_customer_message(name, user.id, text, user.username),
        reply_markup=keyboards.take_chat_keyboard(user.id),
    )
    if sent is None:
        await message.reply_text(msg.delivery_failed_message())
        return
    customer_manager.create_pending_chat(user.id, sent.message_id)
    await message.reply_text(msg.message_received_message())


# ----------------------------------------------------------------- partner panel
async def partner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return
    if not partner_manager.is_partner(user.id):
        await message.reply_text(msg.unauthorized_message())
        return
    partner_manager.register_configured_partners()
    await message.reply_text(
        msg.panel_message(partner_manager.get_status(user.id)),
        reply_markup=keyboards.partner_status_keyboard(),
    )


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.effective_message
    if user is None or message is None:
        return
    if not partner_manager.is_partner(user.id):
        await message.reply_text(msg.unauthorized_message())
        return
    await message.reply_text(msg.pending_list_message(customer_manager.get_pending_customers()))


async def status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    user = query.from_user
    if not partner_manager.is_partner(user.id):
        await query.answer(msg.unauthorized_message(), show_alert=True)
        return

    status = (query.data or "").replace("status_", "", 1)
    if not partner_manager.change_status(user.id, status):
        await query.answer(msg.invalid_request_message(), show_alert=True)
        return

    await query.answer(msg.status_updated_message(status))
    await _safe_edit(
        query,
        msg.panel_message(status) + "\n\n" + msg.status_updated_message(status),
        reply_markup=keyboards.partner_status_keyboard(),
    )


# ----------------------------------------------------------------- Take Chat
async def take_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    partner = query.from_user

    # Only react to buttons posted in the configured partner group.
    if query.message is None or query.message.chat.id != config.PARTNER_GROUP_ID:
        await query.answer(msg.invalid_request_message(), show_alert=True)
        return

    allowed, reason = partner_manager.can_take_chat(partner.id)
    if not allowed:
        text = (
            msg.unauthorized_message()
            if reason == "unauthorized"
            else msg.partner_offline_cannot_take_message()
        )
        await query.answer(text, show_alert=True)
        return

    customer_id = customer_manager.parse_customer_id(query.data, keyboards.CB_TAKE_CHAT)
    if customer_id is None:
        await query.answer(msg.invalid_request_message(), show_alert=True)
        return

    customer = customer_manager.get_customer(customer_id)
    if customer is None:
        await query.answer(msg.invalid_customer_message(), show_alert=True)
        return

    # Atomic: only one partner can win.
    if not customer_manager.assign_chat(customer_id, partner.id):
        await query.answer(msg.chat_already_taken_message(), show_alert=True)
        return

    customer_name = customer_manager.display_name(customer, customer_id)
    history = customer_manager.get_recent_messages(customer_id)
    sent = await _safe_send(
        context,
        partner.id,
        msg.partner_chat_started_message(
            customer_name, customer_id, history, customer.get("username")
        ),
        reply_markup=keyboards.reply_keyboard(customer_id),
    )
    if sent is None:
        # Partner never opened the bot privately: undo the assignment.
        customer_manager.rollback_assignment(customer_id)
        await query.answer(msg.partner_must_start_bot_message(), show_alert=True)
        return

    await query.answer(msg.chat_taken_alert_message())
    await _safe_edit(
        query, msg.chat_taken_group_message(customer_name, customer_id, partner.full_name)
    )
    await _safe_send(context, customer_id, msg.chat_taken_message())


# ----------------------------------------------------------------- Reply flow
async def reply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    partner = query.from_user

    customer_id = customer_manager.parse_customer_id(query.data, keyboards.CB_REPLY)
    if customer_id is None:
        await query.answer(msg.invalid_request_message(), show_alert=True)
        return ConversationHandler.END

    if not partner_manager.is_partner(partner.id):
        await query.answer(msg.unauthorized_message(), show_alert=True)
        return ConversationHandler.END

    if not partner_manager.can_manage_customer(partner.id, customer_id):
        await query.answer(msg.not_your_chat_message(), show_alert=True)
        return ConversationHandler.END

    await query.answer()
    context.user_data[REPLY_KEY] = customer_id
    await _safe_send(context, partner.id, msg.reply_prompt_message())
    return WAITING_REPLY


async def send_partner_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    partner = update.effective_user
    message = update.effective_message
    if partner is None or message is None:
        return ConversationHandler.END

    customer_id: Optional[int] = context.user_data.get(REPLY_KEY)
    if customer_id is None or not partner_manager.can_manage_customer(partner.id, customer_id):
        context.user_data.pop(REPLY_KEY, None)
        await message.reply_text(msg.reply_not_allowed_message())
        return ConversationHandler.END

    text = (message.text or "").strip()
    if not text:
        await message.reply_text(msg.reply_text_only_message())
        return WAITING_REPLY
    if len(text) > msg.MAX_TEXT_LENGTH:
        await message.reply_text(msg.reply_too_long_message())
        return WAITING_REPLY

    try:
        await context.bot.send_message(
            chat_id=customer_id, text=msg.partner_reply_to_customer_message(text)
        )
    except Forbidden:
        await message.reply_text(msg.customer_unreachable_message())
        return WAITING_REPLY
    except TelegramError as exc:
        logger.warning("Reply to customer %s failed: %s", customer_id, exc)
        await message.reply_text(msg.customer_unreachable_message())
        return WAITING_REPLY

    customer_manager.save_partner_reply(customer_id, partner.id, message.message_id, text)
    context.user_data.pop(REPLY_KEY, None)
    await message.reply_text(
        msg.reply_sent_message(), reply_markup=keyboards.reply_keyboard(customer_id)
    )
    return ConversationHandler.END


async def cancel_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop(REPLY_KEY, None)
    message = update.effective_message
    if message is not None:
        await message.reply_text(msg.reply_cancelled_message())
    return ConversationHandler.END


# ----------------------------------------------------------------- Close Chat
async def close_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    partner = query.from_user

    customer_id = customer_manager.parse_customer_id(query.data, keyboards.CB_CLOSE_CHAT)
    if customer_id is None:
        await query.answer(msg.invalid_request_message(), show_alert=True)
        return

    if not partner_manager.is_partner(partner.id):
        await query.answer(msg.unauthorized_message(), show_alert=True)
        return

    if not partner_manager.can_manage_customer(partner.id, customer_id):
        await query.answer(msg.not_your_chat_message(), show_alert=True)
        return

    customer = customer_manager.get_customer(customer_id)
    customer_name = customer_manager.display_name(customer, customer_id)
    chat = customer_manager.finish_chat(customer_id)
    context.user_data.pop(REPLY_KEY, None)

    await query.answer(msg.chat_closed_alert_message())
    await _safe_edit(query, msg.chat_closed_partner_message(customer_name, customer_id))

    # Update the original message in the partner group.
    if chat and chat.get("group_message_id"):
        try:
            await context.bot.edit_message_text(
                chat_id=config.PARTNER_GROUP_ID,
                message_id=chat["group_message_id"],
                text=msg.chat_closed_group_message(customer_name, customer_id, partner.full_name),
            )
        except TelegramError as exc:
            logger.warning("Could not update group message: %s", exc)

    await _safe_send(context, customer_id, msg.chat_closed_customer_message())


# ----------------------------------------------------------------- errors
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception", exc_info=context.error)
    if isinstance(update, Update):
        try:
            if update.callback_query is not None:
                await update.callback_query.answer(msg.generic_error_message(), show_alert=True)
            elif update.effective_message is not None:
                await update.effective_message.reply_text(msg.generic_error_message())
        except TelegramError as exc:
            logger.warning("Could not send error notice: %s", exc)

import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from database import db
from config import LOG_CHANNEL, ADMIN_ID
from utils.formatters import calculate_expiry_date, clean_username
from utils.translator import translate_text

logger = logging.getLogger(__name__)

ADMIN_MENTION_LINK = "[🦋 ༄Nìśẳntℎ༄ 🦋](https://t.me/aLooser)"
ADMIN_CONTACT_URL = "https://t.me/aLooser"

async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    action, sub_id_str = data.split("_")[0], data.split("_")[1]
    sub_id = int(sub_id_str)

    sub = db.get_subscription(sub_id)
    if not sub:
        await query.edit_message_caption("❌ Record no longer found in the database.")
        return

    if sub["status"] != "Pending":
        await query.edit_message_caption(f"⚠️ This request has already been processed (Current Status: {sub['status']}).")
        return

    admin_name = query.from_user.first_name

    if action == "approve":
        start_date = datetime.now().strftime("%d/%m/%Y")
        expiry_date = calculate_expiry_date(start_date, sub["duration"])

        db.update_subscription_status(sub_id, status="Paid", start_date=start_date, expiry_date=expiry_date)
        updated_sub = db.get_subscription(sub_id)

        # 1. Delete original review card in log channel / admin chat
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete original review card: {e}")

        # 2. Post exactly formatted details to channel
        channel_details_text = (
            "💎 **PREMIUM USER DETAILS** 💎\n\n"
            "━━━━━━━━━━━━━━━\n"
            "**User details** :-\n\n"
            f"👤 **User Name** : [{clean_username(updated_sub['username'])}]({updated_sub['profile_link']})\n\n"
            f"🆔 **User ID** : `{updated_sub['user_id']}`\n\n"
            f"🔗 **Profile Link** : [Click Here]({updated_sub['profile_link']})\n\n"
            "━━━━━━━━━━━━━━━\n"
            "**Plan details** :-\n\n"
            f"📦 **Selected Plan** : {updated_sub['plan_name']}\n\n"
            f"🆔 **Plan Id** : {updated_sub['plan_id']}\n\n"
            f"⏰ **Plan Duration** : {updated_sub['duration']}\n\n"
            f"📅 **Start Date** : {updated_sub['start_date']}\n\n"
            f"📅 **Expiry Date** : {updated_sub['expiry_date']}\n\n"
            "━━━━━━━━━━━━━━━\n"
            "**Payment details** :-\n\n"
            f"💵 **Total Amount paid** : {updated_sub['amount']}\n\n"
            "💰 **Payment Status** : ✅ Paid\n\n"
            "📝 **Notes** : N/A\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            "⚡ **Premium activated successfully** 🚀"
        )

        try:
            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text=channel_details_text,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Failed to send approved details to channel: {e}")

        # 3. Notify User with Receipt Card + Persistent Get Channel Link Button
        user_card_text = (
            "🎉 **Premium Subscription Activated!** 🎉\n\n"
            "━━━━━━━━━━━━━━━\n"
            "**Plan details** :-\n\n"
            f"📦 **Selected Plan** : {updated_sub['plan_name']}\n\n"
            f"🆔 **Plan Id** : {updated_sub['plan_id']}\n\n"
            f"⏰ **Plan Duration** : {updated_sub['duration']}\n\n"
            f"📅 **Start Date** : {updated_sub['start_date']}\n\n"
            f"📅 **Expiry Date** : {updated_sub['expiry_date']}\n\n"
            "━━━━━━━━━━━━━━━\n"
            "**Payment details** :-\n\n"
            f"💵 **Total Amount paid** : {updated_sub['amount']}\n\n"
            "💰 **Payment Status** : ✅ Paid\n\n"
            "📝 **Notes** : N/A\n\n"
            "━━━━━━━━━━━━━━━\n\n"
            "⚡ **Welcome to Premium VIP Access** 🚀"
        )

        user_buttons = [[InlineKeyboardButton("🔗 Get Channel Link", callback_data=f"get_link_{sub_id}")]]
        try:
            await context.bot.send_message(
                chat_id=updated_sub["user_id"],
                text=user_card_text,
                reply_markup=InlineKeyboardMarkup(user_buttons),
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Failed to send activated card to user {updated_sub['user_id']}: {e}")

    elif action == "decline":
        db.update_subscription_status(sub_id, status="Declined", notes=f"Declined by {admin_name}")

        decline_msg = (
            "❌ **Your payment could not be verified.**\n\n"
            "Please contact support or resubmit your payment screenshot using /plan."
        )
        try:
            await context.bot.send_message(chat_id=sub["user_id"], text=decline_msg, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Failed to notify user {sub['user_id']}: {e}")

        await query.edit_message_caption(
            caption=f"❌ **Request Declined by {admin_name}**\n\nUser: {sub['username']} (`{sub['user_id']}`)",
            parse_mode="Markdown"
        )

async def handle_get_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    sub_id = int(query.data.split("_")[-1])
    sub = db.get_subscription(sub_id)
    if not sub:
        await query.message.reply_text("❌ Subscription record not found.")
        return

    # Remove the "Get Channel Link" button from the receipt card
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception as e:
        logger.warning(f"Failed to remove Get Link button: {e}")

    plan_link = db.get_setting(f"plan_link_{sub['plan_id']}", "https://t.me/TamilanlinkssSubscription_bot")

    link_msg_text = (
        "🚨 **SECURE VIP CHANNEL INVITE** 🚨\n\n"
        "Use the protected button below to join your premium channel.\n\n"
        "⏳ **CRITICAL**: For security reasons, this join link is forward-restricted and **will be automatically deleted in exactly 3 minutes (180 seconds)**. Please join immediately!\n\n"
        "💬 If you face any issues or are unable to join the channel, please contact Admin via the button below directly."
    )

    link_buttons = [
        [InlineKeyboardButton("🔗 Join Premium Channel (Protected)", url=plan_link)]
    ]

    import json
    custom_btns_json = db.get_setting(f"link_custom_buttons_{sub['plan_id']}")
    if custom_btns_json:
        try:
            custom_btns = json.loads(custom_btns_json)
            for b in custom_btns:
                link_buttons.append([InlineKeyboardButton(b["text"], url=b["url"])])
        except Exception as e:
            logger.warning(f"Could not load custom link buttons for plan {sub['plan_id']}: {e}")

    link_buttons.append([InlineKeyboardButton("👤 Contact Admin 🦋 ༄Nìśẳntℎ༄ 🦋", url=ADMIN_CONTACT_URL)])

    try:
        sent_link = await context.bot.send_message(
            chat_id=sub["user_id"],
            text=link_msg_text,
            reply_markup=InlineKeyboardMarkup(link_buttons),
            parse_mode="Markdown",
            protect_content=True,
            disable_web_page_preview=True
        )

        # Schedule deletion job in 180 seconds
        context.job_queue.run_once(
            delete_invite_link_job,
            when=180,
            data={
                "chat_id": sub["user_id"],
                "message_id": sent_link.message_id,
                "admin_mention": ADMIN_MENTION_LINK
            }
        )
    except Exception as e:
        logger.error(f"Failed to send secure join link to user: {e}")

async def delete_invite_link_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    msg_id = job_data["message_id"]
    admin_mention = job_data["admin_mention"]

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except Exception as e:
        logger.warning(f"Failed to delete expired link message {msg_id}: {e}")

    followup_text = (
        "⏳ **Invite Link Expired & Removed**\n\n"
        "For VIP security reasons, your temporary channel join link has been automatically deleted.\n\n"
        f"💬 If you experienced any difficulty or were unable to join the channel within the 3 minutes, please contact Admin {admin_mention} for direct manual access!"
    )
    try:
        await context.bot.send_message(chat_id=chat_id, text=followup_text, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        logger.warning(f"Failed to send link expiry followup to {chat_id}: {e}")

def get_approval_handlers() -> list:
    return [
        CallbackQueryHandler(handle_approval_callback, pattern="^(approve|decline)_"),
        CallbackQueryHandler(handle_get_link_callback, pattern="^get_link_")
    ]

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import LOG_CHANNEL, ADMIN_ID
from database import db
from utils.formatters import build_premium_user_details, clean_username
from utils.exporter import export_subscriptions_to_docx
from handlers.admin_modules import SUB_REVOKE_REASON, ADMIN_MENTION_LINK

logger = logging.getLogger(__name__)

async def show_subs_menu(query):
    count = db.count_subscriptions()
    plans = db.get_all_plans()
    text = (
        f"👥 **Subscriber Management** 👥\n\n"
        f"Total Subscriptions in DB: **{count}**\n\n"
        "Select a subscription plan below to view and manage its active subscribers:"
    )
    keyboard = []
    for p in plans:
        clean_name = p['name'].split('\n')[0][:40]
        keyboard.append([InlineKeyboardButton(f"📦 {clean_name}", callback_data=f"admin_plan_subs_{p['plan_id']}")])

    keyboard.append([InlineKeyboardButton("🌐 View All Subscribers (All Plans)", callback_data="admin_plan_subs_0")])
    keyboard.append([InlineKeyboardButton("➕ Manually Grant VIP Access / Add User", callback_data="grant_start")])
    keyboard.append([InlineKeyboardButton("📥 Download Subscribers (.doc)", callback_data="admin_download_doc")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def start_revoke_sub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.split("_")[-1])
    sub = db.get_subscription(sub_id)
    if not sub:
        await query.edit_message_text("❌ Record not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu", callback_data="menu_subs")]]))
        return ConversationHandler.END

    context.user_data["action_sub"] = sub
    keyboard = [[InlineKeyboardButton("❌ Cancel / Back", callback_data=f"admin_manage_sub_{sub_id}")]]
    await query.edit_message_text(
        f"🗑️ **Revoking & Deleting Subscription #{sub_id} ({sub['username']})**\n\n"
        "Please send the reason or confirmation notes for terminating this user's premium access and removing their record from the database\n"
        "(e.g., `Subscription expired / Terms violation`):\n\n"
        "Type /cancel to abort.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return SUB_REVOKE_REASON

async def receive_revoke_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    reason = update.message.text.strip()
    sub = context.user_data["action_sub"]
    sub_id = sub["sub_id"]
    admin_name = update.effective_user.first_name

    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    notify_status = "⚠️ Note: Could not send direct termination notice to user (User may have blocked the bot or not started it)."
    revoke_notice = (
        "⚠️ **Premium Subscription Notice** ⚠️\n\n"
        f"Dear subscriber, your premium subscription access for **{sub['plan_name']}** has been revoked and removed from our active database by the Administrator.\n\n"
        f"📋 **Reason**: {reason}\n\n"
        f"💬 If you believe this was an error or wish to renew your subscription, please contact Admin {ADMIN_MENTION_LINK} anytime. Thank you!"
    )
    try:
        await context.bot.send_message(chat_id=sub["user_id"], text=revoke_notice, parse_mode="Markdown", disable_web_page_preview=True)
        notify_status = f"✅ Termination notice successfully sent to user `{sub['user_id']}`."
    except Exception as e:
        logger.warning(f"Failed to notify revoked user {sub['user_id']}: {e}")

    log_chan = db.get_setting("log_channel_id", LOG_CHANNEL)
    audit_text = (
        "🚨 **AUDIT LOG: USER SUBSCRIPTION REVOKED & DELETED** 🚨\n\n"
        f"👤 **User**: [{clean_username(sub['username'])}]({sub['profile_link']}) (`{sub['user_id']}`)\n"
        f"📦 **Plan**: {sub['plan_name']}\n"
        f"🆔 **Sub ID**: #{sub_id}\n"
        f"📋 **Reason / Notes**: {reason}\n"
        f"👑 **Action by**: Admin {admin_name}"
    )
    sent_channel = False
    if log_chan and log_chan not in ["Not Configured", "Not Set", "None", ""]:
        try:
            await context.bot.send_message(chat_id=log_chan, text=audit_text, parse_mode="Markdown", disable_web_page_preview=True)
            sent_channel = True
        except Exception as e:
            logger.warning(f"Failed to send audit log to log_channel {log_chan} ({e}). Falling back to Admin ID.")

    if not sent_channel:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=audit_text, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Failed to send audit log to Admin ID {ADMIN_ID}: {e}")

    db.delete_subscription(sub_id)

    keyboard = [[InlineKeyboardButton("🔙 Back to Subscriber Management", callback_data="menu_subs")]]
    await context.bot.send_message(
        chat_id=update.message.chat_id,
        text=f"✅ **Subscription record #{sub_id} successfully revoked & deleted from the database.**\n\n{notify_status}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    context.user_data.clear()
    return ConversationHandler.END

async def list_plan_subscribers_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.split("_")[-1])

    if plan_id == 0:
        subs = db.get_all_subscriptions(offset=0, limit=500)
        plan_title = "All Active Subscribers"
    else:
        subs = db.get_subscriptions_by_plan(plan_id)
        plan = db.get_plan(plan_id)
        plan_title = plan['name'].split('\n')[0] if plan else f"Plan #{plan_id}"

    if not subs:
        keyboard = [[InlineKeyboardButton("🔙 Back to Subscriber Management", callback_data="menu_subs")]]
        await query.edit_message_text(f"👥 **{plan_title}**\n\n📭 There are currently no subscribers for this plan.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    text = f"👥 **Subscribers for: {plan_title}** (Total: {len(subs)})\n\nClick a subscriber below to view and manage their access details:"
    keyboard = []
    for s in subs:
        status_icon = "👑" if s['status'] == "Granted" else ("✅" if s['status'] == "Paid" else "❌")
        user_display = f"{status_icon} {clean_username(s['username'])} (ID: {s['user_id']})"[:45]
        keyboard.append([InlineKeyboardButton(user_display, callback_data=f"admin_manage_sub_{s['sub_id']}")])

    keyboard.append([InlineKeyboardButton("🔙 Back to Subscriber Management", callback_data="menu_subs")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def manage_subscriber_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.split("_")[-1])
    sub = db.get_subscription(sub_id)

    if not sub:
        keyboard = [[InlineKeyboardButton("🔙 Back to Subscriber Management", callback_data="menu_subs")]]
        await query.edit_message_text("❌ Subscription record not found.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return

    details_text = build_premium_user_details(sub)
    keyboard = [
        [InlineKeyboardButton("🚫 Revoke Access & Remove from DB", callback_data=f"sub_rem_{sub_id}")],
        [InlineKeyboardButton("🔙 Back to Subscribers List", callback_data=f"admin_plan_subs_{sub['plan_id']}")],
        [InlineKeyboardButton("🔙 Subscriber Management Menu", callback_data="menu_subs")]
    ]
    await query.edit_message_text(f"🛠️ **Subscriber Control Panel**\n\n{details_text}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def download_doc_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    subs = db.get_all_subscriptions(offset=0, limit=1000)
    filename = export_subscriptions_to_docx(subs)

    with open(filename, "rb") as f:
        await query.message.reply_document(
            document=f,
            filename="Subscribers_Report.docx",
            caption="📥 **Premium Subscribers Export Report**",
            parse_mode="Markdown"
        )

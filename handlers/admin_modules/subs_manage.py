import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import LOG_CHANNEL, ADMIN_ID
from database import db
from utils.formatters import build_premium_user_details, clean_username
from utils.exporter import export_subscriptions_to_docx
from handlers.admin_modules import SUB_REVOKE_REASON, ADMIN_MENTION_LINK
from handlers.approval import live_timer_update_job
from handlers.user_modules import ADMIN_CONTACT_URL
import json

logger = logging.getLogger(__name__)

async def show_subs_menu(query):
    from utils.keyboard_helper import build_grid_keyboard
    count = db.count_subscriptions()
    plans = db.get_all_plans()
    text = (
        f"👥 **Subscriber Management** 👥\n\n"
        f"Total Subscriptions in DB: **{count}**\n\n"
        "Select a subscription plan below to view and manage its active subscribers:"
    )
    buttons = []
    for p in plans:
        clean_name = p['name'].split('\n')[0][:40]
        buttons.append(InlineKeyboardButton(f"📦 {clean_name}", callback_data=f"admin_plan_subs_{p['plan_id']}"))

    buttons.append(InlineKeyboardButton("🌐 View All", callback_data="admin_plan_subs_0"))
    buttons.append(InlineKeyboardButton("➕ Manually Grant Access", callback_data="grant_start"))
    buttons.append(InlineKeyboardButton("📥 Download Report", callback_data="admin_download_doc"))

    back_btn = InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)

async def start_revoke_sub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.split("_")[-1])
    sub = db.get_subscription(sub_id)
    if not sub:
        back_btn = InlineKeyboardButton("🔙 Menu", callback_data="menu_subs")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text("❌ Record not found.", reply_markup=reply_markup, disable_web_page_preview=True)
        return ConversationHandler.END

    context.user_data["action_sub"] = sub
    back_btn = InlineKeyboardButton("❌ Cancel / Back", callback_data=f"admin_manage_sub_{sub_id}")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await query.edit_message_text(
        f"🗑️ **Revoking & Deleting Subscription #{sub_id} ({sub['username']})**\n\n"
        "Please send the reason or confirmation notes for terminating this user's premium access and removing their record from the database\n"
        "(e.g., `Subscription expired / Terms violation`):\n\n"
        "Type /cancel to abort.",
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return SUB_REVOKE_REASON

async def receive_revoke_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
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

    log_chan = db.get_setting("sub_log_channel_id", "")
    if not log_chan or log_chan in ["Not Configured", "Not Set", "None", ""]:
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

    back_btn = InlineKeyboardButton("🔙 Back to Subscriber Management", callback_data="menu_subs")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await context.bot.send_message(
        chat_id=update.message.chat_id,
        text=f"✅ **Subscription record #{sub_id} successfully revoked & deleted from the database.**\n\n{notify_status}",
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    context.user_data.clear()
    return ConversationHandler.END

async def list_plan_subscribers_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.split("_")[-1])

    if plan_id == 0:
        subs = db.get_active_paid_subscriptions()
        plan_title = "All Active Subscribers"
    else:
        subs = db.get_subscriptions_by_plan(plan_id)
        plan = db.get_plan(plan_id)
        plan_title = plan['name'].split('\n')[0] if plan else f"Plan #{plan_id}"

    if not subs:
        back_btn = InlineKeyboardButton("🔙 Back to Subscriber Management", callback_data="menu_subs")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text(f"👥 **{plan_title}**\n\n📭 There are currently no subscribers for this plan.", reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
        return

    text = f"👥 **Subscribers for: {plan_title}** (Total: {len(subs)})\n\nClick a subscriber below to view and manage their access details:"
    buttons = []
    for s in subs:
        status_icon = "👑" if s['status'] == "Granted" else ("✅" if s['status'] == "Paid" else "❌")
        user_display = f"{status_icon} {clean_username(s['username'])} (ID: {s['user_id']})"[:45]
        buttons.append(InlineKeyboardButton(user_display, callback_data=f"admin_manage_sub_{s['sub_id']}"))

    back_btn = InlineKeyboardButton("🔙 Back to Subscriber Management", callback_data="menu_subs")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)

async def manage_subscriber_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    sub_id = int(query.data.split("_")[-1])
    sub = db.get_subscription(sub_id)

    if not sub:
        from utils.keyboard_helper import build_grid_keyboard
        back_btn = InlineKeyboardButton("🔙 Back to Subscriber Management", callback_data="menu_subs")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text("❌ Subscription record not found.", reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
        return

    details_text = build_premium_user_details(sub)
    keyboard = [
        [
            InlineKeyboardButton("🔗 Send Plan Link", callback_data=f"admin_send_link_{sub_id}"),
            InlineKeyboardButton("📺 Send Indiv. Links", callback_data=f"admin_send_ind_links_{sub_id}")
        ],
        [
            InlineKeyboardButton("🚫 Revoke Access & Remove", callback_data=f"sub_rem_{sub_id}")
        ],
        [
            InlineKeyboardButton("🔙 Back to Subscribers List", callback_data=f"admin_plan_subs_{sub['plan_id']}"),
            InlineKeyboardButton("🔙 Management Menu", callback_data="menu_subs")
        ]
    ]
    await query.edit_message_text(f"🛠️ **Subscriber Control Panel**\n\n{details_text}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown", disable_web_page_preview=True)

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

async def admin_send_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    sub_id = int(query.data.split("_")[-1])
    sub = db.get_subscription(sub_id)
    if not sub:
        await query.message.reply_text("❌ Subscription record not found.", disable_web_page_preview=True)
        return

    plan_link = db.get_setting(f"plan_link_{sub['plan_id']}", "https://t.me/TamilanlinkssSubscription_bot")

    try:
        expiry_mins = int(db.get_setting("link_expiry_minutes", "3"))
    except:
        expiry_mins = 3

    timer_notice = f"⏳ **CRITICAL**: For security reasons, this join link is forward-restricted and **will be automatically deleted in {expiry_mins} minutes**. Please join immediately!\n\n{{TIMER_PLACEHOLDER}}\n\n"

    link_msg_text = (
        "🚨 **SECURE VIP CHANNEL INVITE** 🚨\n\n"
        "Use the protected button below to join your premium channel.\n\n"
        f"{timer_notice}"
        "💬 If you face any issues or are unable to join the channel, please contact Admin via the button below directly."
    )

    link_buttons = [
        [InlineKeyboardButton("🔗 Join Premium Channel (Protected)", url=plan_link)]
    ]

    custom_btns_json = db.get_setting(f"link_custom_buttons_{sub['plan_id']}")
    if custom_btns_json:
        try:
            custom_btns = json.loads(custom_btns_json)
            for b in custom_btns:
                link_buttons.append([InlineKeyboardButton(b["text"], url=b["url"])])
        except Exception as e:
            logger.warning(f"Could not load custom link buttons for plan {sub['plan_id']}: {e}")

    link_buttons.append([InlineKeyboardButton("👤 Contact Admin 🦋 ༄Nìśẳntℎ༄ 🦋", url=ADMIN_CONTACT_URL)])
    reply_markup = InlineKeyboardMarkup(link_buttons)

    initial_text = link_msg_text.replace("{TIMER_PLACEHOLDER}", f"⏳ **Auto-Deleting in: {expiry_mins:02d}:00** ⏳")

    try:
        sent_link = await context.bot.send_message(
            chat_id=sub["user_id"],
            text=initial_text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
            protect_content=True,
            disable_web_page_preview=True
        )

        import time
        jq = context.job_queue or context.application.job_queue
        if jq:
            jq.run_repeating(
                live_timer_update_job,
                interval=5,
                first=5,
                data={
                    "chat_id": sub["user_id"],
                    "message_id": sent_link.message_id,
                    "admin_mention": ADMIN_MENTION_LINK,
                    "end_time": time.time() + (expiry_mins * 60),
                    "original_text": link_msg_text,
                    "reply_markup": reply_markup
                }
            )
            success_text = f"✅ Secure invite link successfully sent to user `{sub['user_id']}`!"
        else:
            success_text = f"✅ Secure invite link successfully sent to user `{sub['user_id']}`! (Note: Auto-delete disabled - Scheduler Offline)"

        await query.message.reply_text(success_text, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Failed to send secure join link to user: {e}")
        await query.message.reply_text(f"❌ Failed to send link to user. They might have blocked the bot.", disable_web_page_preview=True)

async def admin_send_ind_links_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    sub_id = int(query.data.split("_")[-1])
    sub = db.get_subscription(sub_id)
    if not sub:
        await query.message.reply_text("❌ Subscription record not found.", disable_web_page_preview=True)
        return

    channels = db.get_channels_for_plan(sub["plan_id"])
    if not channels:
        await query.message.reply_text("⚠️ No individual channels configured/mapped for this plan.", disable_web_page_preview=True)
        return

    try:
        expiry_mins = int(db.get_setting("link_expiry_minutes", "3"))
    except:
        expiry_mins = 3

    timer_notice = f"⏳ **CRITICAL**: For security reasons, these join links are forward-restricted and **will be automatically deleted in {expiry_mins} minutes**. Please join immediately!\n\n{{TIMER_PLACEHOLDER}}\n\n"

    msg_text = (
        "💎 **INDIVIDUAL VIP CHANNEL ACCESS** 💎\n\n"
        "The Administrator has dispatched individual invite links for each channel included in your plan.\n\n"
        "👇 **Click the buttons below to join each channel**:\n\n"
        f"{timer_notice}"
        "💬 *If you experience any difficulties or have questions, contact the Admin directly.*"
    )

    link_buttons = []
    for c in channels:
        link_buttons.append([InlineKeyboardButton(f"📺 Join {c['title']}", url=c['invite_link'])])

    link_buttons.append([InlineKeyboardButton("👤 Contact Admin 🦋 ༄Nìśẳntℎ༄ 🦋", url=ADMIN_CONTACT_URL)])
    
    initial_text = msg_text.replace("{TIMER_PLACEHOLDER}", f"⏳ **Auto-Deleting in: {expiry_mins:02d}:00** ⏳")
    
    try:
        sent_link = await context.bot.send_message(
            chat_id=sub["user_id"],
            text=initial_text,
            reply_markup=InlineKeyboardMarkup(link_buttons),
            parse_mode="Markdown",
            protect_content=True,
            disable_web_page_preview=True
        )
        
        import time
        jq = context.job_queue or context.application.job_queue
        jq.run_repeating(
            live_timer_update_job,
            interval=5,
            first=5,
            data={
                "chat_id": sub["user_id"],
                "message_id": sent_link.message_id,
                "admin_mention": ADMIN_MENTION_LINK,
                "end_time": time.time() + (expiry_mins * 60),
                "original_text": msg_text,
                "reply_markup": InlineKeyboardMarkup(link_buttons)
            }
        )
        await query.message.reply_text(f"✅ Individual invite links successfully sent to user `{sub['user_id']}` (restricted and secure)!", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Failed to send individual links to user: {e}")
        await query.message.reply_text(f"❌ Failed to send links to user. They might have blocked the bot.", disable_web_page_preview=True)

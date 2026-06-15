import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from database import db
from config import LOG_CHANNEL, ADMIN_ID
from utils.formatters import calculate_expiry_date, clean_username, duration_to_days
from utils.subscription_helpers import check_user_active_sub, calculate_extended_expiry, send_user_instructions
from utils.translator import translate_text

logger = logging.getLogger(__name__)

ADMIN_MENTION_LINK = "[🦋 ༄Nìśẳntℎ༄ 🦋](https://t.me/aLooser)"
ADMIN_CONTACT_URL = "https://t.me/aLooser"

async def approve_subscription(sub_id: int, context: ContextTypes.DEFAULT_TYPE, admin_name: str = "System Auto-Verify", query=None) -> None:
    sub = db.get_subscription(sub_id)
    if not sub:
        if query:
            await query.edit_message_caption("❌ Record no longer found in the database.")
        return

    if sub["status"] != "Pending":
        if query:
            await query.edit_message_caption(f"⚠️ This request has already been processed (Current Status: {sub['status']}).")
        return

    pay_method = sub.get("notes") or ("UPI App" if sub["screenshot_file_id"] == "UPI_APP_AUTO" else "QR Code")

    active_sub, is_active = check_user_active_sub(sub["user_id"])
    file_bot = db.get_setting("file_store_bot_username", "TamilanlinkssSubscription_bot")
    channels = db.get_all_premium_channels()
    
    # Filter Movies channels
    movies_channels = [c for c in channels if any(x in c['title'].lower() for x in ['movie', 'db', 'theatre', 'hd'])]
    
    import re
    clean_bot = file_bot.lstrip("@")
    chan_links_text = (
        "\n\n🤖 **For Series:** Check this bot for Series available! Start the bot to check the series categories and browse our collection:\n"
        f"👉 [Start Series Bot](https://t.me/{clean_bot}?start=availableseries)\n\n"
        "🍿 **Movies Channels:**\n"
    )
    if movies_channels:
        for c in movies_channels:
            title = c['title']
            title = re.sub(r'^[🔹🔸♦️🔷🔶•\-\s]+', '', title)
            chan_links_text += f"🎬 {title}\n"
    else:
        chan_links_text += "*(No movie channels configured)*"

    log_chan = db.get_setting("sub_log_channel_id", "")
    if not log_chan or log_chan in ["Not Configured", "Not Set", "None", ""]:
        log_chan = db.get_setting("log_channel_id", LOG_CHANNEL)
    target_chat = log_chan if (log_chan and log_chan not in ["Not Configured", "Not Set", "None", ""]) else (query.message.chat.id if query else ADMIN_ID)

    if is_active:
        if active_sub["plan_id"] == sub["plan_id"]:
            # --- CASE 1: Renewal of the SAME plan ---
            new_expiry = calculate_extended_expiry(active_sub["expiry_date"], sub["duration"])
            
            db.renew_subscription_record(
                sub_id=active_sub["sub_id"],
                expiry_date=new_expiry,
                duration=sub["duration"],
                amount=sub["amount"],
                screenshot_file_id=sub["screenshot_file_id"]
            )
            
            db.delete_subscription(sub_id)
            updated_sub = db.get_subscription(active_sub["sub_id"])

            if query:
                try:
                    await query.message.delete()
                except Exception as e:
                    logger.warning(f"Failed to delete original review card: {e}")

            channel_details_text = (
                "💎 **PREMIUM USER DETAILS (RENEWED)** 💎\n\n"
                "━━━━━━━━━━━━━━━\n"
                "**User details** :-\n\n"
                f"👤 **User Name** : [{clean_username(updated_sub['username'])}]({updated_sub['profile_link']})\n\n"
                f"🆔 **User ID** : `{updated_sub['user_id']}`\n\n"
                f"🔗 **Profile Link** : [Click Here]({updated_sub['profile_link']})\n\n"
                "━━━━━━━━━━━━━━━\n"
                "**Plan details** :-\n\n"
                f"📦 **Selected Plan** : {updated_sub['plan_name']}\n\n"
                f"🆔 **Plan Id** : {updated_sub['plan_id']}\n\n"
                f"⏰ **Plan Duration** : {updated_sub['duration']} (Extended)\n\n"
                f"📅 **Start Date** : {updated_sub['start_date']}\n\n"
                f"📅 **Expiry Date** : {updated_sub['expiry_date']}\n\n"
                "━━━━━━━━━━━━━━━\n"
                "**Payment details** :-\n\n"
                f"💵 **Total Amount paid** : {updated_sub['amount']}\n\n"
                "💰 **Payment Status** : ✅ Renewed\n\n"
                f"💳 **Payment Method** : {pay_method}\n\n"
                f"📝 **Notes** : {sub['screenshot_file_id'] if sub['screenshot_file_id'] == 'UPI_APP_AUTO' else 'Renewed before expiry'}\n\n"
                "━━━━━━━━━━━━━━━\n\n"
                "⚡ **Premium extended successfully** 🚀"
            )

            edited_log = False
            if log_chan and updated_sub.get("log_message_id"):
                try:
                    await context.bot.edit_message_text(
                        chat_id=log_chan,
                        message_id=int(updated_sub["log_message_id"]),
                        text=channel_details_text,
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )
                    edited_log = True
                except Exception as e:
                    logger.warning(f"Failed to edit existing log message: {e}")

            if not edited_log:
                try:
                    sent_msg = await context.bot.send_message(
                        chat_id=target_chat,
                        text=channel_details_text,
                        parse_mode="Markdown",
                        disable_web_page_preview=True
                    )
                    db.update_subscription_log_message(updated_sub["sub_id"], str(sent_msg.message_id))
                except Exception as e:
                    logger.error(f"Failed to send renewed details to channel: {e}")

            user_card_text = (
                "🎉 **Premium Subscription Renewed & Extended!** 🎉\n\n"
                "━━━━━━━━━━━━━━━\n"
                "**Plan details** :-\n\n"
                f"📦 **Selected Plan** : {updated_sub['plan_name']}\n\n"
                f"🆔 **Plan Id** : {updated_sub['plan_id']}\n\n"
                f"⏰ **Plan Duration** : {updated_sub['duration']}\n\n"
                f"📅 **Expiry Date** : {updated_sub['expiry_date']} (Extended)\n\n"
                "━━━━━━━━━━━━━━━\n"
                "**Payment details** :-\n\n"
                f"💵 **Total Amount paid** : {updated_sub['amount']}\n\n"
                "💰 **Payment Status** : ✅ Renewed\n\n"
                f"💳 **Payment Method** : {pay_method}\n\n"
                "━━━━━━━━━━━━━━━\n\n"
                "⚡ **Your premium access has been successfully extended!** 🚀"
                f"{chan_links_text}"
            )

            user_buttons = [
                [InlineKeyboardButton("🤖 Activate Series Bot", url=f"https://t.me/{file_bot}?start=premium_{updated_sub['user_id']}")],
                [InlineKeyboardButton("🍿 Get Link for Movies Channel", callback_data=f"get_link_{updated_sub['sub_id']}")]
            ]
            try:
                await context.bot.send_message(
                    chat_id=updated_sub["user_id"],
                    text=user_card_text,
                    reply_markup=InlineKeyboardMarkup(user_buttons),
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(f"Failed to send activated card to user: {e}")

            return

        else:
            # --- CASE 2: Upgrade / Downgrade (Different Plan) ---
            try:
                active_expiry = datetime.strptime(active_sub["expiry_date"], "%d/%m/%Y").replace(hour=23, minute=59, second=59)
                remaining = active_expiry - datetime.now()
                remaining_days = max(0, remaining.days)
            except Exception:
                remaining_days = 0

            db.delete_subscription(active_sub["sub_id"])

            start_date = datetime.now().strftime("%d/%m/%Y")
            new_plan_days = duration_to_days(sub["duration"])
            total_days = new_plan_days + remaining_days

            new_expiry_dt = datetime.now() + timedelta(days=total_days)
            new_expiry = new_expiry_dt.strftime("%d/%m/%Y")

            notes = f"Carried forward {remaining_days} days from Plan #{active_sub['plan_id']} | Method: {pay_method}"
            if sub['screenshot_file_id'] == 'UPI_APP_AUTO':
                notes += " (Auto-verified)"
            db.update_subscription_status(sub_id, status="Paid", start_date=start_date, expiry_date=new_expiry, notes=notes)
            db.delete_other_user_subscriptions(sub["user_id"], sub_id)
            updated_sub = db.get_subscription(sub_id)

            if query:
                try:
                    await query.message.delete()
                except Exception as e:
                    logger.warning(f"Failed to delete original review card: {e}")

            channel_details_text = (
                "💎 **PREMIUM USER DETAILS (PLAN CHANGE)** 💎\n\n"
                "━━━━━━━━━━━━━━━\n"
                "**User details** :-\n\n"
                f"👤 **User Name** : [{clean_username(updated_sub['username'])}]({updated_sub['profile_link']})\n\n"
                f"🆔 **User ID** : `{updated_sub['user_id']}`\n\n"
                f"🔗 **Profile Link** : [Click Here]({updated_sub['profile_link']})\n\n"
                "━━━━━━━━━━━━━━━\n"
                "**Plan details** :-\n\n"
                f"📦 **Selected Plan** : {updated_sub['plan_name']} (Change)\n\n"
                f"🆔 **Plan Id** : {updated_sub['plan_id']}\n\n"
                f"⏰ **Plan Duration** : {updated_sub['duration']}\n\n"
                f"📅 **Start Date** : {updated_sub['start_date']}\n\n"
                f"📅 **Expiry Date** : {updated_sub['expiry_date']} (Added {remaining_days} carried days)\n\n"
                "━━━━━━━━━━━━━━━\n"
                "**Payment details** :-\n\n"
                f"💵 **Total Amount paid** : {updated_sub['amount']}\n\n"
                "💰 **Payment Status** : ✅ Paid\n\n"
                f"💳 **Payment Method** : {pay_method}\n\n"
                f"📝 **Notes** : Carried {remaining_days} days from plan {active_sub['plan_name']}\n\n"
                "━━━━━━━━━━━━━━━\n\n"
                "⚡ **New plan activated successfully** 🚀"
            )

            try:
                sent_msg = await context.bot.send_message(
                    chat_id=target_chat,
                    text=channel_details_text,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
                db.update_subscription_log_message(sub_id, str(sent_msg.message_id))
            except Exception as e:
                logger.error(f"Failed to send plan change details: {e}")

            user_card_text = (
                "🎉 **Premium Plan Activated!** 🎉\n\n"
                "━━━━━━━━━━━━━━━\n"
                "**Plan details** :-\n\n"
                f"📦 **Selected Plan** : {updated_sub['plan_name']}\n\n"
                f"🆔 **Plan Id** : {updated_sub['plan_id']}\n\n"
                f"⏰ **Plan Duration** : {updated_sub['duration']}\n\n"
                f"📅 **Expiry Date** : {updated_sub['expiry_date']} (Carried remaining {remaining_days} days!)\n\n"
                "━━━━━━━━━━━━━━━\n"
                "**Payment details** :-\n\n"
                f"💵 **Total Amount paid** : {updated_sub['amount']}\n\n"
                "💰 **Payment Status** : ✅ Paid\n\n"
                f"💳 **Payment Method** : {pay_method}\n\n"
                "━━━━━━━━━━━━━━━\n\n"
                "⚡ **Your new VIP Access is ready!** 🚀"
                f"{chan_links_text}"
            )

            user_buttons = [
                [InlineKeyboardButton("🤖 Activate Series Bot", url=f"https://t.me/{file_bot}?start=premium_{updated_sub['user_id']}")],
                [InlineKeyboardButton("🍿 Get Link for Movies Channel", callback_data=f"get_link_{sub_id}")]
            ]
            try:
                await context.bot.send_message(
                    chat_id=updated_sub["user_id"],
                    text=user_card_text,
                    reply_markup=InlineKeyboardMarkup(user_buttons),
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(f"Failed to send activated card to user: {e}")

            return

    # Fallback / Default new subscription flow
    start_date = datetime.now().strftime("%d/%m/%Y")
    expiry_date = calculate_expiry_date(start_date, sub["duration"])

    notes = f"Method: {pay_method}"
    if sub['screenshot_file_id'] == 'UPI_APP_AUTO':
        notes = "Auto-verified UPI Payment"
    db.update_subscription_status(sub_id, status="Paid", start_date=start_date, expiry_date=expiry_date, notes=notes)
    db.delete_other_user_subscriptions(sub["user_id"], sub_id)
    updated_sub = db.get_subscription(sub_id)

    if query:
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete original review card: {e}")

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
        f"💳 **Payment Method** : {pay_method}\n\n"
        f"📝 **Notes** : {notes}\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "⚡ **Premium activated successfully** 🚀"
    )

    try:
        sent_msg = await context.bot.send_message(
            chat_id=target_chat,
            text=channel_details_text,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        db.update_subscription_log_message(sub_id, str(sent_msg.message_id))
    except Exception as e:
        logger.error(f"Failed to send approved details to channel: {e}")

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
        f"💳 **Payment Method** : {pay_method}\n\n"
        f"📝 **Notes** : {notes}\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "⚡ **Welcome to Premium VIP Access** 🚀"
        f"{chan_links_text}"
    )

    user_buttons = [
        [InlineKeyboardButton("🤖 Activate Series Bot", url=f"https://t.me/{file_bot}?start=premium_{updated_sub['user_id']}")],
        [InlineKeyboardButton("🍿 Get Link for Movies Channel", callback_data=f"get_link_{sub_id}")]
    ]
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
        await approve_subscription(sub_id, context, admin_name, query)

    elif action == "decline":
        db.update_subscription_status(sub_id, status="Declined", notes=f"Declined by {admin_name}")

        decline_msg = (
            "❌ **Your payment could not be verified.**\n\n"
            "The payment screenshot you provided appears to be incorrect or invalid.\n\n"
            "If you have already made the payment and believe this is an error, please contact the Admin using the button below.\n\n"
            "Otherwise, please use /plan to try again and resubmit a valid screenshot."
        )
        decline_keyboard = [[InlineKeyboardButton("👤 Contact Admin 🦋 ༄Nìśẳntℎ༄ 🦋", url=ADMIN_CONTACT_URL)]]
        try:
            await context.bot.send_message(
                chat_id=sub["user_id"],
                text=decline_msg,
                reply_markup=InlineKeyboardMarkup(decline_keyboard),
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
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

    delivery_type = db.get_setting("link_delivery_type", "folder")
    protect = db.get_setting("restrict_link_sharing", "1") == "1"
    all_channels = db.get_channels_for_plan(sub['plan_id'])
    channels = [c for c in all_channels if any(x in c['title'].lower() for x in ['movie', 'db', 'theatre', 'hd'])]

    try:
        expiry_mins = int(db.get_setting("link_expiry_minutes", "3"))
    except:
        expiry_mins = 3

    timer_notice = f"⏳ **CRITICAL**: For security reasons, these join links are forward-restricted and **will be automatically deleted in {expiry_mins} minutes**. Please join immediately!\n\n{{TIMER_PLACEHOLDER}}\n\n"
    timer_notice_single = f"⏳ **CRITICAL**: For security reasons, this join link is forward-restricted and **will be automatically deleted in {expiry_mins} minutes**. Please join immediately!\n\n{{TIMER_PLACEHOLDER}}\n\n"

    if delivery_type == "individual" and channels:
        link_msg_text = (
            "🚨 **SECURE VIP CHANNEL INVITES** 🚨\n\n"
            "Use the protected buttons below to join each premium channel in your plan.\n\n"
            f"{timer_notice}"
            "💬 If you face any issues, please contact Admin via the button below directly."
        )
        link_buttons = []
        for c in channels:
            link_buttons.append([InlineKeyboardButton(f"📺 Join {c['title']} (Protected)", url=c['invite_link'])])
    else:
        plan_link = db.get_setting(f"plan_link_{sub['plan_id']}", "https://t.me/TamilanlinkssSubscription_bot")
        link_msg_text = (
            "🚨 **SECURE VIP CHANNEL INVITE** 🚨\n\n"
            "Use the protected button below to join your premium channel.\n\n"
            f"{timer_notice_single}"
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
    reply_markup = InlineKeyboardMarkup(link_buttons)

    initial_text = link_msg_text.replace("{TIMER_PLACEHOLDER}", f"⏳ **Auto-Deleting in: {expiry_mins:02d}:00** ⏳")

    try:
        sent_link = await context.bot.send_message(
            chat_id=sub["user_id"],
            text=initial_text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
            protect_content=protect,
            disable_web_page_preview=True
        )

        import time
        auto_delete = db.get_setting("link_auto_delete", "1") == "1"
        jq = context.application.job_queue if hasattr(context, 'application') else None
        if jq is None:
            try:
                jq = context.job_queue
            except Exception:
                jq = None

        if auto_delete and jq:
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
        elif auto_delete and not jq:
            logger.error("Auto-delete is enabled but job_queue is unavailable. Install python-telegram-bot[job-queue].")
        else:
            logger.info("Auto-delete is disabled by admin setting.")
    except Exception as e:
        logger.error(f"Failed to send secure join link to user: {e}")

async def live_timer_update_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    msg_id = job_data["message_id"]
    admin_mention = job_data["admin_mention"]
    end_time = job_data["end_time"]
    original_text = job_data["original_text"]
    reply_markup = job_data["reply_markup"]

    import time
    remaining = int(end_time - time.time())

    if remaining <= 0:
        # Time's up! Delete and cancel job
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.warning(f"Failed to delete expired link message {msg_id}: {e}")
        
        followup_text = (
            "⏳ **Invite Link Expired & Removed**\n\n"
            "For VIP security reasons, your temporary channel join link has been automatically deleted.\n\n"
            f"💬 If you experienced any difficulty or were unable to join the channel in time, please contact Admin {admin_mention} for direct manual access!"
        )
        try:
            await context.bot.send_message(chat_id=chat_id, text=followup_text, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            logger.warning(f"Failed to send link expiry followup to {chat_id}: {e}")
            
        context.job.schedule_removal()
        return

    # Update message text with remaining time
    mins, secs = divmod(remaining, 60)
    timer_line = f"⏳ **Auto-Deleting in: {mins:02d}:{secs:02d}** ⏳"
    new_text = original_text.replace("{TIMER_PLACEHOLDER}", timer_line)

    try:
        from telegram.error import BadRequest
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=new_text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.warning(f"Failed to update timer message {msg_id}: {e}")

def get_approval_handlers() -> list:
    return [
        CallbackQueryHandler(handle_approval_callback, pattern="^(approve|decline)_"),
        CallbackQueryHandler(handle_get_link_callback, pattern="^get_link_")
    ]

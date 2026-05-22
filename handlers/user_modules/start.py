import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db
from config import LOG_CHANNEL, ADMIN_ID
from utils.formatters import clean_username
from utils.translator import translate_text
from handlers.user_modules import ADMIN_MENTION_LINK, ADMIN_CONTACT_URL

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = user.language_code if user else "en"

    # Intercept for Testing Mode
    from handlers.admin_modules.menu import is_admin
    test_mode = db.get_setting("testing_mode_enabled", "0")
    if test_mode == "1":
        test_users = db.get_setting("testing_mode_users", "")
        test_user_list = [u.strip() for u in test_users.split(",") if u.strip().isdigit()]
        if not is_admin(user.id) and str(user.id) not in test_user_list:
            fallback = db.get_setting("fallback_channel_link", "")
            msg = "🚧 **Bot is in Testing Mode.**\n\nThe bot is currently undergoing maintenance and testing. You cannot use it right now."
            if fallback:
                msg += f"\n\nPlease join our channel for updates: {fallback}"
            await update.message.reply_text(msg, parse_mode="Markdown")
            return

    # --- Start Auto-Activation for UPI App payment redirection ---
    if context.args and context.args[0].startswith("pay_success_"):
        try:
            parts = context.args[0].split("_")
            if len(parts) == 5:
                uid_str, pid_str, dur_idx_str = parts[2], parts[3], parts[4]
                target_uid = int(uid_str)
                pid = int(pid_str)
                dur_idx = int(dur_idx_str)

                # Security check: verify this matches the current user
                if user.id != target_uid:
                    await update.message.reply_text(
                        "⚠️ **Security Alert**\n\nThis payment verification link belongs to a different user and cannot be activated on this account.",
                        parse_mode="Markdown"
                    )
                    return

                # Get plan details
                plan = db.get_plan(pid)
                if not plan:
                    await update.message.reply_text("❌ **Error**: Plan details not found or deleted.", parse_mode="Markdown")
                    return

                try:
                    durations = plan["durations"]
                    if isinstance(durations, str):
                        durations = json.loads(durations)
                    selected_dur = durations[dur_idx]
                except Exception as e:
                    logger.error(f"Failed to parse durations or get index {dur_idx}: {e}")
                    await update.message.reply_text("❌ **Error**: Invalid plan duration specified.", parse_mode="Markdown")
                    return

                duration_str = selected_dur["duration"]
                amount = selected_dur["price"]
                user_clean_name = clean_username(user.first_name or user.username or "User")
                profile_link = f"https://t.me/{user.username}" if user.username else f"tg://user?id={user.id}"

                # Add a pending subscription record with UPI_APP_AUTO as the screenshot_file_id
                sub_id = db.add_subscription(
                    user_id=user.id,
                    username=user_clean_name,
                    profile_link=profile_link,
                    plan_id=plan["plan_id"],
                    plan_name=plan["name"].split('\n')[0],
                    duration=duration_str,
                    amount=amount,
                    screenshot_file_id="UPI_APP_AUTO"
                )

                if not sub_id:
                    await update.message.reply_text("❌ **Error**: Failed to initialize payment record in database.", parse_mode="Markdown")
                    return

                # Save the payment method as UPI App in the database
                db.update_subscription_status(sub_id, status="Pending", notes="UPI App")

                # Notify user that verification is running
                verifying_msg = await update.message.reply_text(
                    "🔄 **Auto-Verifying Payment...**\n\nPlease wait a moment while we process your VIP subscription.",
                    parse_mode="Markdown"
                )

                # Import approve_subscription dynamically to avoid circular dependencies
                from handlers.approval import approve_subscription

                # Approve the subscription automatically
                await approve_subscription(sub_id, context, admin_name="UPI App Auto-Verify")

                try:
                    await verifying_msg.delete()
                except Exception:
                    pass
                return
        except Exception as e:
            logger.error(f"Failed in deep-link auto-activation: {e}")
            await update.message.reply_text("❌ An unexpected error occurred while processing your auto-activation. Please contact Admin.", parse_mode="Markdown")
            return
    # --- End Auto-Activation logic ---

    # --- Start Cancellation/Failure logic for UPI App payment redirection ---
    elif context.args and context.args[0].startswith("pay_cancel_"):
        try:
            parts = context.args[0].split("_")
            if len(parts) == 5:
                uid_str, pid_str, dur_idx_str = parts[2], parts[3], parts[4]
                target_uid = int(uid_str)

                # Security check: verify this matches the current user
                if user.id != target_uid:
                    await update.message.reply_text(
                        "⚠️ **Security Alert**\n\nThis payment cancellation link belongs to a different user.",
                        parse_mode="Markdown"
                    )
                    return

                keyboard = [
                    [InlineKeyboardButton("👤 Contact Admin 🦋 ༄Nìśẳntℎ༄ 🦋", url=ADMIN_CONTACT_URL)]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Send friendly cancellation/failure message with Contact Admin button
                cancel_msg = (
                    "❌ **Payment Cancelled / Not Completed** ❌\n\n"
                    "Your payment process was not completed, and your premium subscription has not been activated.\n\n"
                    "💡 *Paid but faced an issue?* If you actually paid but your subscription did not activate, please tap the button below to contact our Admin directly for a manual checkout verification!"
                )
                await update.message.reply_text(
                    translate_text(cancel_msg, lang),
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
                return
        except Exception as e:
            logger.error(f"Failed in deep-link cancellation: {e}")
            await update.message.reply_text("❌ An unexpected error occurred.", parse_mode="Markdown")
            return
    # --- End Cancellation/Failure logic ---

    from handlers.admin_modules.menu import is_admin
    if is_admin(user.id):
        admin_msg = (
            f"👑 **Welcome back, Admin {user.first_name}!** 👑\n\n"
            "Use your master control panel below to manage subscriptions, plans, payment methods, and database records."
        )
        admin_keyboard = [
            [InlineKeyboardButton("🛠️ Master Admin Panel (/settings)", callback_data="menu_main")]
        ]
        try:
            await update.message.reply_text(
                admin_msg,
                reply_markup=InlineKeyboardMarkup(admin_keyboard),
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            if "can't parse" in str(e).lower() or "entity" in str(e).lower():
                logger.warning(f"Markdown parsing failed for admin welcome message, falling back to raw text: {e}")
                await update.message.reply_text(
                    admin_msg,
                    reply_markup=InlineKeyboardMarkup(admin_keyboard),
                    parse_mode=None,
                    disable_web_page_preview=True
                )
            else:
                raise e
        return

    user_clean = clean_username(user.first_name or user.username or "User")
    profile_link = f"https://t.me/{user.username}" if user.username else f"tg://user?id={user.id}"
    
    import asyncio
    async def process_new_user():
        try:
            is_new_user = await asyncio.to_thread(db.add_user, user.id, user.username or "", user.first_name or "")
            log_chan = await asyncio.to_thread(db.get_setting, "log_channel_id", LOG_CHANNEL)
            
            if is_new_user:
                start_log_msg = (
                    "👤 **NEW USER STARTED BOT** 👤\n\n"
                    "━━━━━━━━━━━━━━━\n"
                    f"👤 **User Name** : [{user_clean}]({profile_link})\n\n"
                    f"🆔 **User ID** : `{user.id}`\n\n"
                    f"🔗 **Profile Link** : [Click Here]({profile_link})\n\n"
                    f"🌐 **Language** : {lang.upper()}\n\n"
                    "━━━━━━━━━━━━━━━"
                )
                if log_chan and log_chan not in ["Not Configured", "Not Set", "None", ""]:
                    await context.bot.send_message(chat_id=log_chan, text=start_log_msg, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            logger.info(f"Failed to process/log user start: {e}")

    asyncio.create_task(process_new_user())

    custom_welcome = await asyncio.to_thread(db.get_setting, "welcome_msg_text")
    if custom_welcome:
        welcome_msg = custom_welcome
    else:
        welcome_msg = (
            "👋 **Welcome to our Premium VIP Subscription Bot!**\n\n"
            "Unlock exclusive premium features, high-speed downloads, and VIP channel access instantly.\n\n"
            "🚀 Type /plan or click below to browse available subscription plans and start your premium journey today!\n\n"
            f"💬 *Facing any issues or have questions?*\n"
            f"Please contact our Admin {ADMIN_MENTION_LINK} directly anytime for prompt assistance!"
        )

    keyboard = []
    custom_btns = await asyncio.to_thread(db.get_setting, "welcome_custom_buttons")
    if custom_btns:
        try:
            btns_list = json.loads(custom_btns)
            for b in btns_list:
                keyboard.append([InlineKeyboardButton(b["text"], url=b["url"])])
        except Exception as e:
            logger.warning(f"Could not load custom welcome buttons: {e}")

    keyboard.append([
        InlineKeyboardButton("📦 Browse Plans", callback_data="select_plans_menu"),
        InlineKeyboardButton("👤 Contact Admin", url=ADMIN_CONTACT_URL)
    ])

    try:
        await update.message.reply_text(
            translate_text(welcome_msg, lang),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        if "can't parse" in str(e).lower() or "entity" in str(e).lower():
            logger.warning(f"Markdown parsing failed for user welcome message, falling back to raw text: {e}")
            await update.message.reply_text(
                translate_text(welcome_msg, lang),
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=None,
                disable_web_page_preview=True
            )
        else:
            raise e

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    lang = user.language_code if user else "en"
    
    user_clean = clean_username(user.first_name or user.username or "User")
    profile_link = f"https://t.me/{user.username}" if user.username else f"tg://user?id={user.id}"
    
    msg = (
        "🆔 **Your Telegram ID Details** 🆔\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **User:** [{user_clean}]({profile_link})\n\n"
        f"🔢 **ID:** `{user.id}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    
    await update.message.reply_text(
        translate_text(msg, lang),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

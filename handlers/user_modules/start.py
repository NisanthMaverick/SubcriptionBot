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

    if str(user.id) == str(ADMIN_ID):
        admin_msg = (
            f"👑 **Welcome back, Admin {user.first_name}!** 👑\n\n"
            "Use your master control panel below to manage subscriptions, plans, payment methods, and database records."
        )
        admin_keyboard = [
            [InlineKeyboardButton("🛠️ Master Admin Panel (/settings)", callback_data="menu_main")]
        ]
        await update.message.reply_text(
            admin_msg,
            reply_markup=InlineKeyboardMarkup(admin_keyboard),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        return

    user_clean = clean_username(user.first_name or user.username or "User")
    is_new_user = db.add_user(user.id, user.username or "", user.first_name or "")
    profile_link = f"https://t.me/{user.username}" if user.username else f"tg://user?id={user.id}"
    log_chan = db.get_setting("log_channel_id", LOG_CHANNEL)

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
            try:
                await context.bot.send_message(chat_id=log_chan, text=start_log_msg, parse_mode="Markdown", disable_web_page_preview=True)
            except Exception as e:
                logger.info(f"Failed to log user start to channel: {e}")

    custom_welcome = db.get_setting("welcome_msg_text")
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
    custom_btns = db.get_setting("welcome_custom_buttons")
    if custom_btns:
        try:
            btns_list = json.loads(custom_btns)
            for b in btns_list:
                keyboard.append([InlineKeyboardButton(b["text"], url=b["url"])])
        except Exception as e:
            logger.warning(f"Could not load custom welcome buttons: {e}")

    keyboard.append([InlineKeyboardButton("📦 Browse Premium Plans", callback_data="select_plans_menu")])
    keyboard.append([InlineKeyboardButton("👤 Contact Admin 🦋 ༄Nìśẳntℎ༄ 🦋", url=ADMIN_CONTACT_URL)])

    await update.message.reply_text(
        translate_text(welcome_msg, lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

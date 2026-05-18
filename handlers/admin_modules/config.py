import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from handlers.admin_modules import WELCOME_EDIT_TEXT, WELCOME_ADD_BTN, PLAN_ADD_EXT_BTN, LOG_CHAN_ID

logger = logging.getLogger(__name__)

async def show_config_menu(query):
    log_chan = db.get_setting("log_channel_id", "Not Configured")
    text = f"⚙️ **Bot Configurations & Automation** ⚙️\n\nCurrent Log Channel: `{log_chan}`\n\nSelect an action:"
    keyboard = [
        [InlineKeyboardButton("💬 Customize Welcome Screen (/start)", callback_data="welcome_config_menu")],
        [InlineKeyboardButton("📋 Configure Log Channel", callback_data="admin_log_channel")],
        [InlineKeyboardButton("⏰ Expiry Notification Settings", callback_data="admin_expiry_notify")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_welcome_config_menu(query, alert=""):
    cur_text = db.get_setting("welcome_msg_text", "Default Welcome Message")
    cur_btns_json = db.get_setting("welcome_custom_buttons", "None")

    text = f"{alert}\n\n" if alert else ""
    text += (
        "💬 **Welcome Screen (/start) Customization** 💬\n\n"
        "Configure the welcome message and custom buttons displayed to users when they start the bot.\n\n"
        f"**Current Text Snapshot**:\n`{cur_text[:120]}...`\n\n"
        f"**Custom Buttons Configured**:\n`{cur_btns_json}`\n\n"
        "Choose an option below:"
    )
    keyboard = [
        [InlineKeyboardButton("📝 Edit Welcome Text", callback_data="welcome_edit_text")],
        [InlineKeyboardButton("➕ Add Welcome Button", callback_data="welcome_add_btn"),
         InlineKeyboardButton("🗑️ Reset Buttons", callback_data="welcome_reset_btns")],
        [InlineKeyboardButton("🔙 Back to Configurations", callback_data="menu_config")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def start_welcome_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ Cancel / Back", callback_data="welcome_config_menu")]]
    await query.edit_message_text(
        "📝 **Edit Welcome Message Text**\n\n"
        "Please send the new welcome message formatted in Markdown.\n\n"
        "Type /cancel to abort.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return WELCOME_EDIT_TEXT

async def receive_welcome_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass
    db.set_setting("welcome_msg_text", text)
    keyboard = [[InlineKeyboardButton("🔙 Back to Welcome Customization", callback_data="welcome_config_menu")]]
    await context.bot.send_message(chat_id=update.message.chat_id, text="✅ Welcome message text successfully updated.", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def start_welcome_add_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ Cancel / Back", callback_data="welcome_config_menu")]]
    await query.edit_message_text(
        "➕ **Add Custom Welcome Button**\n\n"
        "Please send the button title and URL separated by `-`\n"
        "(e.g., `Official Website - https://example.com`):\n\n"
        "Type /cancel to abort.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return WELCOME_ADD_BTN

async def receive_welcome_add_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    if "-" not in text:
        keyboard = [[InlineKeyboardButton("🔙 Back to Welcome Customization", callback_data="welcome_config_menu")]]
        await context.bot.send_message(chat_id=update.message.chat_id, text="❌ Invalid format. Please use `Title - URL`.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return ConversationHandler.END

    parts = text.split("-", 1)
    title = parts[0].strip()
    url = parts[1].strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    cur_btns = db.get_setting("welcome_custom_buttons")
    btns_list = []
    if cur_btns:
        try:
            btns_list = json.loads(cur_btns)
        except Exception:
            pass
    btns_list.append({"text": title, "url": url})
    db.set_setting("welcome_custom_buttons", json.dumps(btns_list))

    keyboard = [[InlineKeyboardButton("🔙 Back to Welcome Customization", callback_data="welcome_config_menu")]]
    await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ Custom button `{title}` successfully added.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ConversationHandler.END

async def start_ep_extbtn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    context.user_data["edit_ext_pid"] = pid
    keyboard = [[InlineKeyboardButton("❌ Cancel / Back", callback_data=f"edit_plan_{pid}")]]
    await query.edit_message_text(
        f"➕ **Add Extra Join Link Button for Plan #{pid}**\n\n"
        "Please send the button title and URL separated by `-`\n"
        "(e.g., `Channel Rules - https://t.me/rules`):\n\n"
        "Type /cancel to abort.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return PLAN_ADD_EXT_BTN

async def receive_ep_extbtn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    pid = context.user_data.get("edit_ext_pid", 0)
    if "-" not in text:
        keyboard = [[InlineKeyboardButton("🔙 Back to Plan Editing", callback_data=f"edit_plan_{pid}")]]
        await context.bot.send_message(chat_id=update.message.chat_id, text="❌ Invalid format. Please use `Title - URL`.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return ConversationHandler.END

    parts = text.split("-", 1)
    title = parts[0].strip()
    url = parts[1].strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    cur_btns = db.get_setting(f"link_custom_buttons_{pid}")
    btns_list = []
    if cur_btns:
        try:
            btns_list = json.loads(cur_btns)
        except Exception:
            pass
    btns_list.append({"text": title, "url": url})
    db.set_setting(f"link_custom_buttons_{pid}", json.dumps(btns_list))

    keyboard = [[InlineKeyboardButton("🔙 Back to Plan Editing", callback_data=f"edit_plan_{pid}")]]
    await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ Extra link button `{title}` successfully added to Plan #{pid}.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ConversationHandler.END

async def start_log_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    current_log = db.get_setting("log_channel_id", "Not Set (Fallback to Admin ID)")
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_log_setup")]]
    await query.edit_message_text(
        f"📋 **Log Channel Configuration**\n\nCurrent Log Channel: `{current_log}`\n\n"
        "Please send a valid Channel ID starting with `-` (e.g., `-1001234567890`) or username (`@mychannel`).\n\n"
        "Type /cancel to abort.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return LOG_CHAN_ID

async def receive_log_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chan = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")]]
    if not (chan.startswith("-") or chan.startswith("@") or chan.isdigit()):
        sent_msg = await context.bot.send_message(chat_id=update.message.chat_id, text="⚠️ Invalid log channel ID format. Must start with `-`, `@`, or be numeric. Please try again or type /cancel.", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["prompt_msg_id"] = sent_msg.message_id
        context.user_data["prompt_chat_id"] = sent_msg.chat_id
        return LOG_CHAN_ID

    db.set_setting("log_channel_id", chan)
    await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ Log channel successfully updated to: `{chan}`", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

async def expiry_notify_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    enabled = db.get_setting("expiry_notify_enabled", "0")
    hours = db.get_setting("expiry_notify_hours", "24")

    status_str = "🟢 ENABLED" if enabled == "1" else "🔴 DISABLED"

    text = (
        "⏰ **Automated Expiry Notification Settings** ⏰\n\n"
        f"**Current Status**: {status_str}\n"
        f"**Warning Interval**: Intimate users {hours} hours before plan expiration.\n\n"
        "Select an action below:"
    )

    toggle_btn = "🔴 Disable Notifications" if enabled == "1" else "🟢 Enable Notifications"
    toggle_val = "0" if enabled == "1" else "1"

    keyboard = [
        [InlineKeyboardButton(toggle_btn, callback_data=f"set_exp_en_{toggle_val}")],
        [InlineKeyboardButton("⏱ 12 Hours Before", callback_data="set_exp_hr_12"),
         InlineKeyboardButton("⏱ 24 Hours Before", callback_data="set_exp_hr_24"),
         InlineKeyboardButton("⏱ 48 Hours Before", callback_data="set_exp_hr_48")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def handle_expiry_notify_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("set_exp_en_"):
        val = data.split("_")[-1]
        db.set_setting("expiry_notify_enabled", val)
    elif data.startswith("set_exp_hr_"):
        val = data.split("_")[-1]
        db.set_setting("expiry_notify_hours", val)

    await expiry_notify_settings(update, context)

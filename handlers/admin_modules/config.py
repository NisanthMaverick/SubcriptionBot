import logging
import json
import io
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import db
from handlers.admin_modules import WELCOME_EDIT_TEXT, WELCOME_ADD_BTN, PLAN_ADD_EXT_BTN, LOG_CHAN_ID, IMPORT_SETTINGS_FILE

logger = logging.getLogger(__name__)

async def edit_message_safely(query, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.warning(f"Error editing message safely: {e}")

async def show_config_menu(query):
    from utils.keyboard_helper import build_grid_keyboard
    log_chan = db.get_setting("log_channel_id", "Not Configured")
    text = f"⚙️ **Bot Configurations & Automation** ⚙️\n\nCurrent Log Channel: `{log_chan}`\n\nSelect an action:"
    buttons = [
        InlineKeyboardButton("💬 Customize Welcome Screen (/start)", callback_data="welcome_config_menu"),
        InlineKeyboardButton("📋 Configure Log Channel", callback_data="admin_log_channel"),
        InlineKeyboardButton("⏰ Expiry Notification Settings", callback_data="admin_expiry_notify"),
        InlineKeyboardButton("📺 Premium Channels", callback_data="chan_menu"),
        InlineKeyboardButton("👮 Channel Protection (Raid)", callback_data="raid_menu")
    ]
    back_btn = InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    await edit_message_safely(query, text, reply_markup)

async def show_welcome_config_menu(query, alert=""):
    from utils.keyboard_helper import build_grid_keyboard
    cur_text = db.get_setting("welcome_msg_text", "Default Welcome Message")
    cur_btns_json = db.get_setting("welcome_custom_buttons", "None")
    text = f"{alert}\n\n" if alert else ""
    text += (
        "💬 **Welcome Screen Customization** 💬\n\n"
        f"**Current Text Snapshot**:\n`{cur_text[:120]}...`\n\n"
        f"**Custom Buttons**:\n`{cur_btns_json}`"
    )
    buttons = [
        InlineKeyboardButton("📝 Edit Welcome Text", callback_data="welcome_edit_text"),
        InlineKeyboardButton("➕ Add Welcome Button", callback_data="welcome_add_btn"),
        InlineKeyboardButton("🗑️ Reset Buttons", callback_data="welcome_reset_btns")
    ]
    back_btn = InlineKeyboardButton("🔙 Back to Configurations", callback_data="menu_config")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    await edit_message_safely(query, text, reply_markup)

async def start_welcome_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("❌ Cancel / Back", callback_data="welcome_config_menu"))
    await edit_message_safely(query, "📝 **Edit Welcome Message Text**\n\nSend the welcome message formatted in Markdown.\n\nType /cancel to abort.", reply_markup)
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return WELCOME_EDIT_TEXT

async def receive_welcome_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    text = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception: pass
    if "prompt_msg_id" in context.user_data:
        try: await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception: pass
    db.set_setting("welcome_msg_text", text)
    reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("🔙 Back to Welcome Customization", callback_data="welcome_config_menu"))
    await context.bot.send_message(chat_id=update.message.chat_id, text="✅ Welcome message text successfully updated.", reply_markup=reply_markup)
    return ConversationHandler.END

async def start_welcome_add_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("❌ Cancel / Back", callback_data="welcome_config_menu"))
    await edit_message_safely(query, "➕ **Add Custom Welcome Button**\n\nSend title and URL separated by `-` (e.g. `Rules - https://t.me/rules`):\n\nType /cancel to abort.", reply_markup)
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return WELCOME_ADD_BTN

async def receive_welcome_add_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    text = update.message.text.strip()
    try: await update.message.delete()
    except Exception: pass
    if "prompt_msg_id" in context.user_data:
        try: await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception: pass

    if "-" not in text:
        reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("🔙 Back to Welcome Customization", callback_data="welcome_config_menu"))
        await context.bot.send_message(chat_id=update.message.chat_id, text="❌ Invalid format. Please use `Title - URL`.", reply_markup=reply_markup)
        return ConversationHandler.END

    parts = text.split("-", 1)
    title, url = parts[0].strip(), parts[1].strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    cur_btns = db.get_setting("welcome_custom_buttons")
    btns_list = json.loads(cur_btns) if cur_btns else []
    btns_list.append({"text": title, "url": url})
    db.set_setting("welcome_custom_buttons", json.dumps(btns_list))

    reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("🔙 Back to Welcome Customization", callback_data="welcome_config_menu"))
    await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ Custom button `{title}` successfully added.", reply_markup=reply_markup)
    return ConversationHandler.END

async def start_ep_extbtn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    context.user_data["edit_ext_pid"] = pid
    reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("❌ Cancel / Back", callback_data=f"edit_plan_{pid}"))
    await edit_message_safely(query, f"➕ **Add Extra Link Button for Plan #{pid}**\n\nSend title and URL separated by `-`:\n\nType /cancel to abort.", reply_markup)
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return PLAN_ADD_EXT_BTN

async def receive_ep_extbtn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    text = update.message.text.strip()
    try: await update.message.delete()
    except Exception: pass
    if "prompt_msg_id" in context.user_data:
        try: await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception: pass

    pid = context.user_data.get("edit_ext_pid", 0)
    if "-" not in text:
        reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("🔙 Back to Plan Editing", callback_data=f"edit_plan_{pid}"))
        await context.bot.send_message(chat_id=update.message.chat_id, text="❌ Invalid format. Please use `Title - URL`.", reply_markup=reply_markup)
        return ConversationHandler.END

    parts = text.split("-", 1)
    title, url = parts[0].strip(), parts[1].strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    cur_btns = db.get_setting(f"link_custom_buttons_{pid}")
    btns_list = json.loads(cur_btns) if cur_btns else []
    btns_list.append({"text": title, "url": url})
    db.set_setting(f"link_custom_buttons_{pid}", json.dumps(btns_list))

    reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("🔙 Back to Plan Editing", callback_data=f"edit_plan_{pid}"))
    await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ Extra link button `{title}` successfully added to Plan #{pid}.", reply_markup=reply_markup)
    return ConversationHandler.END

async def start_log_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    current_log = db.get_setting("log_channel_id", "Not Set")
    reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("❌ Cancel", callback_data="cancel_log_setup"))
    await edit_message_safely(query, f"📋 **Log Channel Configuration**\n\nCurrent Log Channel: `{current_log}`\n\nSend a Channel ID starting with `-` or username (`@channel`).\n\nType /cancel to abort.", reply_markup)
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return LOG_CHAN_ID

async def receive_log_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    chan = update.message.text.strip()
    try: await update.message.delete()
    except Exception: pass
    if "prompt_msg_id" in context.user_data:
        try: await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception: pass

    back_btn = InlineKeyboardButton("🔙 Back to Configurations", callback_data="menu_config")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    if not (chan.startswith("-") or chan.startswith("@") or chan.isdigit()):
        sent_msg = await context.bot.send_message(chat_id=update.message.chat_id, text="⚠️ Invalid format. Must start with `-` or `@`.", reply_markup=reply_markup)
        context.user_data["prompt_msg_id"] = sent_msg.message_id
        context.user_data["prompt_chat_id"] = sent_msg.chat_id
        return LOG_CHAN_ID

    db.set_setting("log_channel_id", chan)
    await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ Log channel updated to: `{chan}`", reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END

async def expiry_notify_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    enabled = db.get_setting("expiry_notify_enabled", "0")
    hours = db.get_setting("expiry_notify_hours", "24")
    status_str = "🟢 ENABLED" if enabled == "1" else "🔴 DISABLED"
    text = (
        "⏰ **Expiry Notification Settings** ⏰\n\n"
        f"**Current Status**: {status_str}\n"
        f"**Warning Interval**: {hours} hours before plan expiration."
    )
    toggle_btn = "🔴 Disable Notifications" if enabled == "1" else "🟢 Enable Notifications"
    toggle_val = "0" if enabled == "1" else "1"
    
    buttons = [
        InlineKeyboardButton(toggle_btn, callback_data=f"set_exp_en_{toggle_val}"),
        InlineKeyboardButton("⏱ 12 Hours Before", callback_data="set_exp_hr_12"),
        InlineKeyboardButton("⏱ 24 Hours Before", callback_data="set_exp_hr_24"),
        InlineKeyboardButton("⏱ 48 Hours Before", callback_data="set_exp_hr_48")
    ]
    back_btn = InlineKeyboardButton("🔙 Back to Configurations", callback_data="menu_config")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    await edit_message_safely(query, text, reply_markup)

async def handle_expiry_notify_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("set_exp_en_"):
        db.set_setting("expiry_notify_enabled", data.split("_")[-1])
    elif data.startswith("set_exp_hr_"):
        db.set_setting("expiry_notify_hours", data.split("_")[-1])
    await expiry_notify_settings(update, context)

# Export Settings
async def export_bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        data = {
            "settings": db.get_all_settings(),
            "plans": db.get_all_plans(),
            "premium_channels": db.get_all_premium_channels(),
            "channel_mappings": db.get_all_channel_mappings()
        }
        json_str = json.dumps(data, indent=4, ensure_ascii=False)
        file_bytes = io.BytesIO(json_str.encode("utf-8"))
        file_bytes.name = f"bot_settings_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=file_bytes,
            filename=file_bytes.name,
            caption="📤 **Settings Exported Successfully!**\n\nUpload this JSON file in other bot settings to apply.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Settings export failed: {e}")
        await query.message.reply_text(f"❌ **Export failed:** {e}")

# Import Settings Conversation
async def start_import_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    back_btn = InlineKeyboardButton("❌ Cancel", callback_data="cancel_import")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await edit_message_safely(
        query,
        "📥 **Import Bot Settings**\n\nPlease upload and send the `.json` file that you exported previously.\n\nType /cancel to abort.",
        reply_markup
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return IMPORT_SETTINGS_FILE

async def receive_import_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    doc = update.message.document
    try: await update.message.delete()
    except Exception: pass
    if "prompt_msg_id" in context.user_data:
        try: await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception: pass

    back_btn = InlineKeyboardButton("🔙 Back to Backup Menu", callback_data="menu_backup_restore")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    if not doc or not doc.file_name.endswith(".json"):
        await context.bot.send_message(chat_id=update.message.chat_id, text="❌ **Invalid File.** Upload a `.json` settings file.", reply_markup=reply_markup)
        return ConversationHandler.END

    try:
        file_obj = await context.bot.get_file(doc.file_id)
        file_bytes = await file_obj.download_as_bytearray()
        import_data = json.loads(file_bytes.decode("utf-8"))

        # Clear existing configurations to ensure a clean restore of everything
        db.clear_settings()
        db.clear_plans()
        db.clear_premium_channels()
        db.clear_channel_mappings()

        # Apply settings
        settings = import_data.get("settings", {})
        for k, v in settings.items():
            db.set_setting(k, v)
        
        # Seed defaults for any missing key
        db._seed_default_settings()

        # Apply plans
        plans = import_data.get("plans", [])
        for p in plans:
            db.save_plan(p["plan_id"], p["name"], p.get("description", ""), p.get("amount", ""), p.get("durations", []))

        # Apply channels & mappings
        channels = import_data.get("premium_channels", [])
        for c in channels:
            db.add_premium_channel(c["channel_id"], c["title"], c.get("invite_link", ""))

        mappings = import_data.get("channel_mappings", [])
        for m in mappings:
            db.add_channel_mapping(m["channel_id"], m["plan_id"])

        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f"✅ **Settings Imported Successfully!**\n\n⚙️ Settings: `{len(settings)}` applied.\n📦 Plans: `{len(plans)}` plans configured.\n📺 Channels: `{len(channels)}` channels.\n🔗 Mappings: `{len(mappings)}` mapped links.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Import failed: {e}")
        await context.bot.send_message(chat_id=update.message.chat_id, text=f"❌ **Failed to import settings:**\n\n`{e}`", reply_markup=reply_markup)

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_import(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query: await query.answer()
    context.user_data.clear()
    if query:
        await show_backup_menu(query)
    return ConversationHandler.END

async def show_backup_menu(query) -> None:
    from utils.keyboard_helper import build_grid_keyboard
    text = (
        "📤📥 **Backup & Restore Settings** 📥📤\n\n"
        "Manage bot configuration backups:\n\n"
        "• **Export settings**: Creates a JSON backup of settings, plans, premium channels, and mapping tables.\n"
        "• **Import settings**: Upload a settings JSON backup file to overwrite current state."
    )
    buttons = [
        InlineKeyboardButton("📤 Export Settings (JSON)", callback_data="admin_export_settings"),
        InlineKeyboardButton("📥 Import Settings (JSON)", callback_data="admin_import_settings")
    ]
    back_btn = InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    await edit_message_safely(query, text, reply_markup)

settings_import_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_import_settings, pattern="^admin_import_settings$")],
    states={IMPORT_SETTINGS_FILE: [MessageHandler(filters.Document.ALL & ~filters.COMMAND, receive_import_file)]},
    fallbacks=[CommandHandler("cancel", cancel_import), CallbackQueryHandler(cancel_import, pattern="^cancel_import$")],
    per_message=False
)

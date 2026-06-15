import logging
import json
import io
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import db
from handlers.admin_modules import WELCOME_EDIT_TEXT, WELCOME_ADD_BTN, PLAN_ADD_EXT_BTN, LOG_CHAN_ID, IMPORT_SETTINGS_FILE, TEST_MODE_USERS, SUB_LOG_CHAN_ID

logger = logging.getLogger(__name__)

async def edit_message_safely(query, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.warning(f"Error editing message safely: {e}")

async def show_config_menu(query):
    from utils.keyboard_helper import build_grid_keyboard
    test_mode = db.get_setting("testing_mode_enabled", "0")
    test_mode_str = "🟢 ON" if test_mode == "1" else "🔴 OFF"
    test_users = db.get_setting("testing_mode_users", "None")
    log_chan = db.get_setting("log_channel_id", "Not Configured")
    sub_log_chan = db.get_setting("sub_log_channel_id", "Not Configured")
    file_bot = db.get_setting("file_store_bot_username", "Not Configured")
    
    text = (
        "⚙️ **Bot Configurations & Automation** ⚙️\n\n"
        f"**System Log Channel**: `{log_chan}`\n"
        f"**Subscription Log Channel**: `{sub_log_chan}`\n"
        f"**File Store Bot**: `@{file_bot}`\n"
        f"**Testing Mode**: {test_mode_str}\n"
        f"**Test User IDs**: `{test_users}`\n\n"
        "Select an action:"
    )
    buttons = [
        InlineKeyboardButton("💬 Customize Welcome Screen (/start)", callback_data="welcome_config_menu"),
        InlineKeyboardButton("📋 Config System Log Channel", callback_data="admin_log_channel"),
        InlineKeyboardButton("📋 Config Subscription Log Channel", callback_data="admin_sub_log_channel"),
        InlineKeyboardButton("🤖 Configure File Store Bot", callback_data="admin_config_file_bot"),
        InlineKeyboardButton("⏰ Expiry Notification Settings", callback_data="admin_expiry_notify"),
        InlineKeyboardButton("🔗 Get Link Delivery Settings", callback_data="get_link_config_menu"),
        InlineKeyboardButton("📺 Premium Channels", callback_data="chan_menu"),
        InlineKeyboardButton("👮 Channel Protection (Raid)", callback_data="raid_menu"),
        InlineKeyboardButton(f"🧪 Toggle Test Mode ({'ON' if test_mode == '1' else 'OFF'})", callback_data="toggle_test_mode"),
        InlineKeyboardButton("👥 Set Test User IDs", callback_data="set_test_users")
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

async def start_sub_log_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    
    current_log = db.get_setting("sub_log_channel_id", "Not Set")
    text = (
        "📋 **Configure Subscription Log Channel** 📋\n\n"
        f"**Current Channel ID:** `{current_log}`\n\n"
        "Please send the Channel ID (e.g., `-1001234567890`) where subscription updates (approvals, payments, revokes) should be sent.\n\n"
        "⚠️ *Make sure the bot is an Admin in the channel first!*\n\n"
        "Type /cancel to abort."
    )
    back_btn = InlineKeyboardButton("❌ Cancel / Back", callback_data="menu_config")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await edit_message_safely(query, text, reply_markup)
    
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return SUB_LOG_CHAN_ID

async def receive_sub_log_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    chan = update.message.text.strip()
    
    try:
        await update.message.delete()
    except:
        pass
        
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except:
            pass

    back_btn = InlineKeyboardButton("🔙 Back to Configurations", callback_data="menu_config")
    reply_markup = build_grid_keyboard([], back_button=back_btn)

    if not (chan.startswith('-100') and chan[4:].isdigit()):
        await context.bot.send_message(chat_id=update.message.chat_id, text="❌ Invalid format. Must start with '-100' followed by numbers.", reply_markup=reply_markup)
        context.user_data.clear()
        return ConversationHandler.END

    db.set_setting("sub_log_channel_id", chan)
    try:
        await context.bot.send_message(
            chat_id=chan,
            text="✅ **Subscription Log Channel Verification**\n\nThe Subscription Bot has been successfully linked to this channel. Future subscription logs will be posted here.",
            parse_mode="Markdown"
        )
        await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ Subscription Log Channel successfully set to `{chan}` and verified!", reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error receiving subscription log channel: {e}")
        await context.bot.send_message(chat_id=update.message.chat_id, text=f"❌ An error occurred: {e}", reply_markup=reply_markup)
    
    context.user_data.clear()
    return ConversationHandler.END

async def start_config_file_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    current_bot = db.get_setting("file_store_bot_username", "Not Set")
    reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("❌ Cancel", callback_data="menu_config"))
    await edit_message_safely(
        query, 
        f"🤖 **File Store Bot Configuration**\n\nCurrent Bot: `{current_bot}`\n\nPlease send the File Store Bot username (e.g. `@MyFileStoreBot` or `MyFileStoreBot`):\n\nType /cancel to abort.", 
        reply_markup
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    from handlers.admin_modules import FILE_STORE_BOT_USERNAME
    return FILE_STORE_BOT_USERNAME

async def receive_config_file_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    bot_input = update.message.text.strip()
    try: await update.message.delete()
    except Exception: pass
    if "prompt_msg_id" in context.user_data:
        try: await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception: pass

    bot_username = bot_input.replace("@", "").strip()
    db.set_setting("file_store_bot_username", bot_username)
    
    reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("🔙 Back to Configurations", callback_data="menu_config"))
    await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ File Store Bot successfully updated to: `@{bot_username}`", reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END

async def start_ep_extbtn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query: await query.answer()
    context.user_data.clear()
    if query:
        await show_backup_menu(query)
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

async def show_link_delivery_config_menu(query, alert=""):
    from utils.keyboard_helper import build_grid_keyboard
    delivery_type = db.get_setting("link_delivery_type", "folder")
    protect = db.get_setting("restrict_link_sharing", "1")
    auto_delete = db.get_setting("link_auto_delete", "1")
    expiry_mins = db.get_setting("link_expiry_minutes", "3")
    
    deliv_label = "📺 Individual Links" if delivery_type == "individual" else "📂 Folder/Plan Link"
    protect_label = "🔒 Restricted (Protected)" if protect == "1" else "🔓 Allowed (Copy/Forward)"
    auto_del_label = "🗑️ Enabled (Auto-Delete)" if auto_delete == "1" else "❌ Disabled (Keep Links)"
    
    text = f"{alert}\n\n" if alert else ""
    text += (
        "⚙️ **Get Link Options & Delivery Settings** ⚙️\n\n"
        "Configure how Premium Invite Links are delivered to users upon activation:\n\n"
        f"• **Delivery Type**: `{deliv_label}`\n"
        "   - _Folder/Plan Link_: Sends a single folder/main link where they join all channels.\n"
        "   - _Individual Links_: Sends a clean set of buttons for each mapped channel.\n\n"
        f"• **Security (Copy/Forward Restriction)**: `{protect_label}`\n"
        "   - _Restricted_: Restricts copying, forwarding, and saving media of the link message.\n"
        "   - _Allowed_: Standard message layout allowing sharing.\n\n"
        f"• **Auto-Delete Link**: `{auto_del_label}`\n"
        f"• **Link Expiry Timer**: `{expiry_mins} Minutes`\n"
    )
    
    buttons = [
        InlineKeyboardButton(f"🔄 Toggle Delivery (Current: {delivery_type.capitalize()})", callback_data="toggle_link_delivery_type"),
        InlineKeyboardButton(f"🛡️ Toggle Protection (Current: {'Protected' if protect == '1' else 'Allowed'})", callback_data="toggle_restrict_link_sharing"),
        InlineKeyboardButton(f"🗑️ Toggle Auto-Delete (Current: {'ON' if auto_delete == '1' else 'OFF'})", callback_data="toggle_link_auto_delete")
    ]
    if auto_delete == "1":
        buttons.append(InlineKeyboardButton("⏱ Configure Expiry Timer", callback_data="link_timer_config_menu"))
        
    back_btn = InlineKeyboardButton("🔙 Back to Configurations", callback_data="menu_config")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    
    await edit_message_safely(query, text, reply_markup)

async def show_link_timer_config_menu(query, alert=""):
    from utils.keyboard_helper import build_grid_keyboard
    expiry_mins = db.get_setting("link_expiry_minutes", "3")
    
    text = f"{alert}\n\n" if alert else ""
    text += (
        "⏱ **Link Expiry Timer Settings** ⏱\n\n"
        "Configure how long the Join Links stay active before being automatically deleted.\n\n"
        f"**Current Setting**: `{expiry_mins} Minutes`\n\n"
        "Select an option below to update:"
    )
    
    buttons = [
        InlineKeyboardButton("⏱ 1 Min", callback_data="set_link_exp_1"),
        InlineKeyboardButton("⏱ 3 Mins", callback_data="set_link_exp_3"),
        InlineKeyboardButton("⏱ 5 Mins", callback_data="set_link_exp_5"),
        InlineKeyboardButton("⏱ 10 Mins", callback_data="set_link_exp_10"),
    ]
    back_btn = InlineKeyboardButton("🔙 Back to Link Options", callback_data="get_link_config_menu")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    
    await edit_message_safely(query, text, reply_markup)

async def toggle_test_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    current = db.get_setting("testing_mode_enabled", "0")
    db.set_setting("testing_mode_enabled", "1" if current == "0" else "0")
    await show_config_menu(query)

async def start_test_mode_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("❌ Cancel", callback_data="menu_config"))
    await edit_message_safely(query, "👥 **Set Test User IDs**\n\nSend a comma-separated list of User IDs that are allowed to test the bot (e.g., `123456,78910`).\n\nType /cancel to abort.", reply_markup)
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    from handlers.admin_modules import TEST_MODE_USERS
    return TEST_MODE_USERS

async def receive_test_mode_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    ids = update.message.text.strip()
    try: await update.message.delete()
    except Exception: pass
    if "prompt_msg_id" in context.user_data:
        try: await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception: pass

    db.set_setting("testing_mode_users", ids)
    reply_markup = build_grid_keyboard([], back_button=InlineKeyboardButton("🔙 Back to Configurations", callback_data="menu_config"))
    await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ Test User IDs successfully updated to: `{ids}`", reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import db
from jobs.raid_scanner import scan_channels_job

logger = logging.getLogger(__name__)

# States for editing Conversations
EDIT_TIMEOUT_INPUT = 120
EDIT_RAID_CHANNEL_INPUT = 121

async def show_raid_menu(query) -> None:
    """
    Displays the Channel Protection / Raid system configuration panel.
    """
    raid_enabled = db.get_setting("raid_enabled", "0")
    auto_remove = db.get_setting("auto_remove_enabled", "0")
    timeout = db.get_setting("auto_remove_timeout_mins", "10")
    raid_chan = db.get_setting("raid_channel_id", "")
    if not raid_chan or raid_chan in ["Not Configured", "Not Set", "None", ""]:
        from config import RAID_CHANNEL
        raid_chan = RAID_CHANNEL
    
    status_prot = "🟢 **ENABLED**" if raid_enabled == "1" else "🔴 **DISABLED**"
    status_rem = "🟢 **ENABLED**" if auto_remove == "1" else "🔴 **DISABLED**"
    
    text = (
        "👮 **Channel Access Protection (Raid System)** 👮\n\n"
        "This system scans monitored premium channels in real-time (and periodically in the background) "
        "to detect and remove members who do not have an active subscription.\n\n"
        f"🛡️ **Raid Protection Status**: {status_prot}\n"
        f"🤖 **Auto-Remove Unauthorized**: {status_rem}\n"
        f"⏱️ **Auto-Remove Timeout**: `{timeout} minutes`\n"
        f"📢 **Alert Channel ID**: `{raid_chan or 'Log Channel (Default)'}`\n\n"
        "Configure options below or run an on-demand verification scan:"
    )

    keyboard = [
        [
            InlineKeyboardButton("🛡️ Toggle Protection", callback_data="raid_toggle_prot"),
            InlineKeyboardButton("🤖 Toggle Auto-Remove", callback_data="raid_toggle_rem")
        ],
        [
            InlineKeyboardButton("⏱️ Edit Timeout", callback_data="raid_edit_time_start"),
            InlineKeyboardButton("📢 Edit Raid Channel", callback_data="raid_edit_chan_start")
        ],
        [
            InlineKeyboardButton("🔍 Trigger Manual Scan Now", callback_data="raid_run_scan"),
            InlineKeyboardButton("📋 Verify Channels Status", callback_data="chan_verify_all")
        ],
        [
            InlineKeyboardButton("🔙 Back to Configurations", callback_data="menu_config")
        ]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def toggle_raid_protection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    current = db.get_setting("raid_enabled", "0")
    new_val = "1" if current == "0" else "0"
    db.set_setting("raid_enabled", new_val)
    
    await show_raid_menu(query)

async def toggle_auto_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    current = db.get_setting("auto_remove_enabled", "0")
    new_val = "1" if current == "0" else "0"
    db.set_setting("auto_remove_enabled", new_val)
    
    await show_raid_menu(query)

async def start_edit_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="raid_cancel")]]
    await query.edit_message_text(
        "⏱️ **Edit Auto-Remove Timeout**\n\n"
        "Please send the timeout in minutes (e.g. `10` or `30`) before unauthorized users are automatically banned.\n\n"
        "Type /cancel to abort.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return EDIT_TIMEOUT_INPUT

async def receive_timeout_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    try:
        minutes = int(text)
        if minutes <= 0:
            raise ValueError()
        
        db.set_setting("auto_remove_timeout_mins", str(minutes))
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")]]
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f"✅ **Auto-Remove Timeout Updated!**\n\n⏱️ New timeout is set to `{minutes} minutes`.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception:
        keyboard = [[InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")]]
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ **Invalid Number.** Please send a valid positive number of minutes.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    context.user_data.clear()
    return ConversationHandler.END

async def start_edit_raid_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="raid_cancel")]]
    await query.edit_message_text(
        "📢 **Configure Raid Alert Channel**\n\n"
        "Please send the Telegram Channel ID where the bot should post unauthorized access alerts (e.g. `-1003564494376`).\n\n"
        "Type /cancel to abort.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return EDIT_RAID_CHANNEL_INPUT

async def receive_raid_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    try:
        channel_id = int(text)
        db.set_setting("raid_channel_id", str(channel_id))
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")]]
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f"✅ **Raid Alert Channel Updated!**\n\n📢 New Alert Channel ID: `{channel_id}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    except Exception:
        keyboard = [[InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")]]
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ **Invalid Channel ID.** Please send a valid Telegram Channel ID (e.g. starting with -100).",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_raid_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await show_raid_menu(query)
    context.user_data.clear()
    return ConversationHandler.END

async def run_manual_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Verification scan started!")
    
    # Run the scanning job directly as an async task, passing the admin query for real-time monitoring
    asyncio.create_task(scan_channels_job(context, admin_query=query))

async def handle_raid_remove_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split("_")
    channel_id = int(parts[2])
    user_id = int(parts[3])

    try:
        await context.bot.ban_chat_member(chat_id=channel_id, user_id=user_id)
        await context.bot.unban_chat_member(chat_id=channel_id, user_id=user_id)
        
        await query.edit_message_text(
            text=query.message.text + "\n\n🚫 **User Removed by Admin**",
            reply_markup=None,
            parse_mode="Markdown"
        )
    except Exception as e:
        await query.edit_message_text(
            text=query.message.text + f"\n\n❌ **Failed to remove user**: {e}",
            reply_markup=None,
            parse_mode="Markdown"
        )

async def handle_raid_ignore_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text=query.message.text + "\n\n✅ **Ignored by Admin**",
        reply_markup=None,
        parse_mode="Markdown"
    )

# Timeout Configuration Handler
raid_timeout_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit_timeout, pattern="^raid_edit_time_start$")],
    states={
        EDIT_TIMEOUT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_timeout_input)]
    },
    fallbacks=[
        CallbackQueryHandler(cancel_raid_config, pattern="^raid_cancel$"),
        CommandHandler("cancel", cancel_raid_config)
    ],
    per_message=False
)

# Raid Channel Configuration Handler
raid_chan_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit_raid_channel, pattern="^raid_edit_chan_start$")],
    states={
        EDIT_RAID_CHANNEL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_raid_channel_input)]
    },
    fallbacks=[
        CallbackQueryHandler(cancel_raid_config, pattern="^raid_cancel$"),
        CommandHandler("cancel", cancel_raid_config)
    ],
    per_message=False
)

raid_action_handlers = [
    CallbackQueryHandler(toggle_raid_protection, pattern="^raid_toggle_prot$"),
    CallbackQueryHandler(toggle_auto_remove, pattern="^raid_toggle_rem$"),
    CallbackQueryHandler(run_manual_scan, pattern="^raid_run_scan$"),
    CallbackQueryHandler(handle_raid_remove_action, pattern="^raid_remove_"),
    CallbackQueryHandler(handle_raid_ignore_action, pattern="^raid_ignore_"),
    CallbackQueryHandler(cancel_raid_config, pattern="^raid_menu$")
]

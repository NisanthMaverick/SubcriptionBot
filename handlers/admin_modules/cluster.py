import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from handlers.admin_modules import ADMIN_BROADCAST, ADMIN_ADD_DB

logger = logging.getLogger(__name__)

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    back_btn = InlineKeyboardButton("❌ Cancel / Back", callback_data="menu_main")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    msg = await query.edit_message_text(
        "📢 **Cluster Broadcast System** 📢\n\n"
        "Please send the message (text, photo, video, or document with caption) you want to broadcast to all registered users across the database cluster.\n\n"
        "Type /cancel to abort.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    context.user_data["prompt_chat_id"] = msg.chat_id
    context.user_data["prompt_msg_id"] = msg.message_id
    return ADMIN_BROADCAST

async def receive_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    user_ids = db.get_all_unique_user_ids()
    if not user_ids:
        back_btn = InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="⚠️ No registered users found in the database cluster to broadcast to.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    status_msg = await context.bot.send_message(
        chat_id=update.message.chat_id,
        text=f"⏳ **Starting Cluster Broadcast**...\nTargeting **{len(user_ids)}** unique users.\nPlease wait...",
        parse_mode="Markdown"
    )

    success = 0
    failed = 0
    for uid in user_ids:
        try:
            await update.message.copy(chat_id=uid)
            success += 1
        except Exception:
            failed += 1

    back_btn = InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await context.bot.edit_message_text(
        chat_id=status_msg.chat_id,
        message_id=status_msg.message_id,
        text=f"📢 **Broadcast Complete!** 📢\n\n"
             f"✅ Successfully delivered: **{success}** users\n"
             f"❌ Failed / Blocked bot: **{failed}** users\n\n"
             f"Total Target Audience: **{len(user_ids)}**",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def start_add_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    back_btn = InlineKeyboardButton("❌ Cancel / Back", callback_data="menu_db_mgr")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    msg = await query.edit_message_text(
        "➕ **Add New PostgreSQL Database Shard** ➕\n\n"
        "Please send the complete database connection string (starting with `postgres://` or `postgresql://`).\n"
        "The bot will validate the connection instantly before adding it to the cluster.\n\n"
        "Type /cancel to abort.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    context.user_data["prompt_chat_id"] = msg.chat_id
    context.user_data["prompt_msg_id"] = msg.message_id
    return ADMIN_ADD_DB

async def receive_add_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    url = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    back_btn = InlineKeyboardButton("🔙 Back to Multi-Database Manager", callback_data="menu_db_mgr")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    if not url.startswith("postgres://") and not url.startswith("postgresql://"):
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Invalid URL. Must start with `postgres://` or `postgresql://`.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    status_msg = await context.bot.send_message(
        chat_id=update.message.chat_id,
        text="⏳ Testing database connection and initializing shard pool...",
        parse_mode="Markdown"
    )

    try:
        success = db.add_database(url)
        if success:
            await context.bot.edit_message_text(
                chat_id=status_msg.chat_id,
                message_id=status_msg.message_id,
                text="✅ **Database Shard Successfully Added & Initialized!**\n\n"
                     "The database has been attached to the cluster pool for auto-failover and load balancing.",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await context.bot.edit_message_text(
                chat_id=status_msg.chat_id,
                message_id=status_msg.message_id,
                text="⚠️ This database URL is already present in the cluster configuration.",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=status_msg.chat_id,
            message_id=status_msg.message_id,
            text=f"❌ **Database Connection Failed!**\n\nError: `{e}`\n\nPlease ensure the database is online and accessible.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    return ConversationHandler.END

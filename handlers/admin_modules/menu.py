import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import ADMIN_ID
from database import db
from handlers.admin_modules import ADMIN_MENTION_LINK

logger = logging.getLogger(__name__)

def is_admin(user_id: int) -> bool:
    return str(user_id) == str(ADMIN_ID)

async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if is_admin(user.id):
        await update.message.reply_text(
            f"👑 Welcome back, Admin {user.first_name}! 👑\n\n"
            "Use /settings to open the master control panel."
        )
        return True
    return False

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ Access denied.")
        return
    await show_main_menu(update)

async def show_main_menu(update: Update):
    text = (
        "🛠️ **Master Admin Control Panel** 🛠️\n\n"
        "Select a category below to configure and manage the bot:"
    )
    keyboard = [
        [InlineKeyboardButton("📦 Manage Plans", callback_data="menu_plans"),
         InlineKeyboardButton("💳 Payment Settings", callback_data="menu_payment")],
        [InlineKeyboardButton("👥 Subscriber Management", callback_data="menu_subs"),
         InlineKeyboardButton("⚙️ Bot Configurations", callback_data="menu_config")],
        [InlineKeyboardButton("📊 System Status & Analytics", callback_data="menu_status"),
         InlineKeyboardButton("📢 Broadcast Message", callback_data="menu_broadcast")],
        [InlineKeyboardButton("📤📥 Backup & Restore Settings", callback_data="menu_backup_restore")],
        [InlineKeyboardButton("🗄️ Multi-Database Manager", callback_data="menu_db_mgr")],
        [InlineKeyboardButton("🧹 Database Reset & Cleanup", callback_data="menu_db_clean")],
        [InlineKeyboardButton("❌ Close Panel", callback_data="close_panel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def cancel_admin_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    text = "❌ Action cancelled. Returning to Master Control Panel."
    if update.message:
        await update.message.reply_text(text)
        await show_main_menu(update)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text)
        await show_main_menu(update)
    return ConversationHandler.END

async def cancel_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await show_main_menu(update)
    return ConversationHandler.END

async def handle_menu_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu_main":
        await show_main_menu(update)
    elif data == "close_panel":
        await query.edit_message_text("✅ Control panel closed. Type /settings to open again.")
    elif data == "menu_plans":
        text = "📦 **Subscription Plans Management** 📦\n\nChoose an action below:"
        kb = [
            [InlineKeyboardButton("➕ Add New Plan", callback_data="admin_add_plan")],
            [InlineKeyboardButton("✏️ Edit Existing Plan", callback_data="list_edit_plans"),
             InlineKeyboardButton("🗑️ Delete Plan", callback_data="list_delete_plans")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    elif data == "list_edit_plans":
        from handlers.admin_modules.plans_edit import list_edit_plans
        await list_edit_plans(query)
    elif data == "list_delete_plans":
        from handlers.admin_modules.plans_edit import list_delete_plans
        await list_delete_plans(query)
    elif data.startswith("del_plan_"):
        pid = int(data.split("_")[-1])
        db.delete_plan(pid)
        kb = [[InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="menu_plans")]]
        await query.edit_message_text(f"✅ Plan #{pid} successfully deleted.", reply_markup=InlineKeyboardMarkup(kb))
    elif data == "menu_payment":
        from handlers.admin_modules.payment import show_payment_menu
        await show_payment_menu(query)
    elif data == "reset_upi_ids":
        db.save_upi_ids(["nisanthlatha2001-3@okaxis"])
        from handlers.admin_modules.payment import show_payment_menu
        await show_payment_menu(query, alert_msg="✅ All UPI IDs reset to default.")
    elif data == "menu_subs":
        from handlers.admin_modules.subs_manage import show_subs_menu
        await show_subs_menu(query)
    elif data == "menu_config":
        from handlers.admin_modules.config import show_config_menu
        await show_config_menu(query)
    elif data == "chan_menu":
        from handlers.admin_modules.channel_mapping import show_channels_menu
        await show_channels_menu(query)
    elif data == "raid_menu":
        from handlers.admin_modules.raid import show_raid_menu
        await show_raid_menu(query)
    elif data == "menu_backup_restore":
        from handlers.admin_modules.config import show_backup_menu
        await show_backup_menu(query)

    elif data == "welcome_config_menu":
        from handlers.admin_modules.config import show_welcome_config_menu
        await show_welcome_config_menu(query)
    elif data == "welcome_reset_btns":
        db.set_setting("welcome_custom_buttons", "")
        from handlers.admin_modules.config import show_welcome_config_menu
        await show_welcome_config_menu(query, alert="✅ Welcome custom buttons successfully reset.")
    elif data.startswith("ep_resext_"):
        pid = int(data.split("_")[-1])
        db.set_setting(f"link_custom_buttons_{pid}", "")
        query.data = f"edit_plan_{pid}"
        from handlers.admin_modules.plans_edit import handle_edit_plan_selection
        await handle_edit_plan_selection(update, context)
    else:
        from handlers.admin_modules.menu_db import handle_db_menu_navigation
        await handle_db_menu_navigation(update, context, data)

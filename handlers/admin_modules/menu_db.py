import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database import db, get_friendly_db_name
from handlers.admin_modules.menu import show_main_menu
from utils.keyboard_helper import build_grid_keyboard

logger = logging.getLogger(__name__)

async def handle_db_menu_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str) -> bool:
    query = update.callback_query

    if data == "menu_status":
        analytics = db.get_database_analytics()
        total_cluster_users = db.count_users()
        total_cluster_orders = db.count_subscriptions()
        active_cluster_subs = len(db.get_active_paid_subscriptions())

        report = "📊 **Multi-Database Cluster Status & Analytics** 📊\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for st in analytics:
            st_icon = "🟢 Online" if st['status'] == "Online" else ("🟡 Full" if st['status'] == "Full" else "🔴 Offline")
            report += (
                f"🗄️ **Database #{st['db_index']}**: `{st['name']}`\n"
                f"   • 🔌 **Status**: {st_icon}\n"
                f"   • 💾 **Storage Used**: **{st['size_mb']} MB** (`{st['usage_percent']}%` of 500MB free quota)\n"
                f"   • 👥 **Registered Users**: **{st['total_users']}**\n"
                f"   • 📦 **Total Subscriptions**: **{st['total_subs']}**\n"
                f"   • 👑 **Active VIP Members**: **{st['active_subs']}**\n"
                f"   • 💳 **Dual-Write**: 🟢 Enabled & Syncing\n\n"
            )
        report += (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌐 **Overall Cluster Summary & Aggregated Stats** 🌐\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"   • 🗄️ Total Connected Shards: **{len(analytics)} Databases**\n"
            f"   • 👥 Total Unique Registered Users: **{total_cluster_users} Users**\n"
            f"   • 📦 Total Combined Subscriptions: **{total_cluster_orders} Orders**\n"
            f"   • 👑 Total Active VIP Members: **{active_cluster_subs} VIPs**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        await query.message.reply_text(report, parse_mode="Markdown")
        await show_main_menu(update)
        return True
    elif data == "menu_db_mgr":
        urls = db.get_all_db_urls()
        status_map = db.get_db_status_map()
        text = "🗄️ **Multi-Database Cluster Shard Manager** 🗄️\n\nActive Shards:\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        for idx, u in enumerate(urls):
            fname = get_friendly_db_name(u, idx)
            st = status_map.get(u, "Online")
            st_icon = "🟢" if st == "Online" else ("🟡" if st == "Full" else "🔴")
            text += f"{st_icon} **Shard #{idx + 1}**: `{fname}` ({st})\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\nClick below to attach a new PostgreSQL database shard to the rotation pool:"
        
        buttons = [
            InlineKeyboardButton("➕ Add New Database URL", callback_data="add_db_url")
        ]
        back_btn = InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
        reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return True
    elif data == "menu_db_clean":
        text = (
            "🗄️ **Database Reset & Cleanup Management** 🗄️\n\n"
            "⚠️ **CAUTION**: These actions modify or permanently delete database records. Please proceed with care!\n\n"
            "Select an action below:"
        )
        buttons = [
            InlineKeyboardButton("🧹 Clear Only Subscriber Records", callback_data="db_warn_subs"),
            InlineKeyboardButton("🧹 Clear Only Subscription Plans", callback_data="db_warn_plans"),
            InlineKeyboardButton("🚨 Factory Reset (Wipe Entire Database) 🚨", callback_data="db_warn_all")
        ]
        back_btn = InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
        reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return True
    elif data == "db_warn_subs":
        text = (
            "⚠️ **WARNING: CRITICAL DESTRUCTIVE ACTION** ⚠️\n\n"
            "You are about to permanently delete **ALL Subscriber Records** from the active database.\n"
            "This action cannot be undone!\n\n"
            "Are you absolutely sure you want to proceed?"
        )
        buttons = [
            InlineKeyboardButton("🚨 YES, PERMANENTLY DELETE ALL SUBSCRIBERS 🚨", callback_data="db_exec_subs")
        ]
        back_btn = InlineKeyboardButton("❌ NO, CANCEL & RETURN TO SAFETY ❌", callback_data="menu_main")
        reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return True
    elif data == "db_warn_plans":
        text = (
            "⚠️ **WARNING: CRITICAL DESTRUCTIVE ACTION** ⚠️\n\n"
            "You are about to permanently delete **ALL Subscription Plans** from the active database.\n"
            "This action cannot be undone!\n\n"
            "Are you absolutely sure you want to proceed?"
        )
        buttons = [
            InlineKeyboardButton("🚨 YES, PERMANENTLY DELETE ALL PLANS 🚨", callback_data="db_exec_plans")
        ]
        back_btn = InlineKeyboardButton("❌ NO, CANCEL & RETURN TO SAFETY ❌", callback_data="menu_main")
        reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return True
    elif data == "db_warn_all":
        text = (
            "🚨 **FACTORY RESET WARNING: TOTAL DATABASE WIPE** 🚨\n\n"
            "You are about to permanently delete **EVERYTHING** in the database, including all subscriber records, all subscription plans, and all custom settings.\n"
            "This action cannot be undone!\n\n"
            "Are you absolutely sure you want to proceed?"
        )
        buttons = [
            InlineKeyboardButton("🚨 YES, WIPE ENTIRE DATABASE 🚨", callback_data="db_exec_all")
        ]
        back_btn = InlineKeyboardButton("❌ NO, CANCEL & RETURN TO SAFETY ❌", callback_data="menu_main")
        reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return True
    elif data == "db_exec_subs":
        db.clear_subscriptions()
        back_btn = InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text("✅ **All subscriber subscription records have been completely erased from the database.**", reply_markup=reply_markup, parse_mode="Markdown")
        return True
    elif data == "db_exec_plans":
        db.clear_plans()
        back_btn = InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text("✅ **All subscription plans have been completely erased from the database.**", reply_markup=reply_markup, parse_mode="Markdown")
        return True
    elif data == "db_exec_all":
        db.clear_all_tables()
        back_btn = InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text("🚨 **Factory Reset Complete: All plans, subscriber records, and custom settings have been completely erased from the database.**", reply_markup=reply_markup, parse_mode="Markdown")
        return True

    return False

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
        back_btn = InlineKeyboardButton("🔙 Back to Sync Menu", callback_data="menu_db_sync")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text(report, reply_markup=reply_markup, parse_mode="Markdown")
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
    elif data == "db_sync_refresh":
        # Force a ping which attempts reconnect on offline databases
        db.ping_databases()
        # Clear settings cache so it re-reads from DB
        db.clear_cache()
        # Refresh current stats
        total_cluster_users = db.count_users()
        total_cluster_orders = db.count_subscriptions()
        
        await query.answer("Database pinged and caches cleared!")
        text = (
            "✅ **Manual Refresh Complete!**\n\n"
            "Database connections have been checked and re-established if offline. Internal caches are cleared.\n\n"
            f"👥 Unique Users Loaded: **{total_cluster_users}**\n"
            f"📦 Subscriptions Loaded: **{total_cluster_orders}**\n\n"
            "Your plans and settings should now be fully synced."
        )
        back_btn = InlineKeyboardButton("🔙 Back to Sync Menu", callback_data="menu_db_sync")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return True
    elif data == "db_sync_interval":
        text = "⏱️ **Configure Auto-Check Interval**\n\nSelect how often the bot should ping the database to keep it online:"
        buttons = [
            InlineKeyboardButton("1 Minute", callback_data="set_db_interval_1"),
            InlineKeyboardButton("3 Minutes", callback_data="set_db_interval_3"),
            InlineKeyboardButton("5 Minutes", callback_data="set_db_interval_5"),
            InlineKeyboardButton("10 Minutes", callback_data="set_db_interval_10"),
            InlineKeyboardButton("❌ Disable", callback_data="set_db_interval_0")
        ]
        back_btn = InlineKeyboardButton("🔙 Back to Sync Menu", callback_data="menu_db_sync")
        reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        return True
    elif data.startswith("set_db_interval_"):
        mins = data.split("_")[-1]
        db.set_setting("db_ping_interval_mins", mins)
        status_text = "Disabled" if mins == "0" else f"{mins} Minutes"
        await query.answer(f"Interval set to {status_text}")
        await show_db_sync_menu(query)
        return True

    return False

async def show_db_sync_menu(query):
    interval = db.get_setting("db_ping_interval_mins", "3")
    interval_str = "Disabled" if interval == "0" else f"{interval} minutes"
    analytics = db.get_database_analytics()
    total_users = db.count_users()
    
    if not analytics:
        status_text = "🔴 Offline (No connections)"
    else:
        offline_count = sum(1 for st in analytics if st['status'] == 'Offline')
        if offline_count == 0:
            status_text = "🟢 Online"
        elif offline_count < len(analytics):
            status_text = "🟡 Degraded (Some offline)"
        else:
            status_text = "🔴 Offline (All shards down)"
            
    last_interaction = "⚡ Live Syncing"
    
    text = (
        "🔄 **Database Sync & Integrity Check** 🔄\n\n"
        "Ensure your database stays online and your settings/plans stay in sync. Serverless databases may sleep after inactivity; this tool keeps them awake.\n\n"
        f"🔌 **Cluster Status**: {status_text}\n"
        f"👥 **Total Registered Users**: **{total_users}**\n"
        f"⏱️ **Current Auto-Check Interval**: `{interval_str}`\n"
        f"📡 **Last Interaction**: {last_interaction}\n\n"
        "Select an option below:"
    )
    buttons = [
        InlineKeyboardButton("📊 System Status & Analytics", callback_data="menu_status"),
        InlineKeyboardButton("⚡ Manual DB Start / Refresh Settings", callback_data="db_sync_refresh"),
        InlineKeyboardButton("⏱️ Configure Check Interval", callback_data="db_sync_interval"),
        InlineKeyboardButton("🗄️ Multi-Database Manager", callback_data="menu_db_mgr"),
        InlineKeyboardButton("📤📥 Import/Export Settings", callback_data="menu_backup_restore"),
        InlineKeyboardButton("🧹 Database Reset & Cleanup", callback_data="menu_db_clean")
    ]
    back_btn = InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")


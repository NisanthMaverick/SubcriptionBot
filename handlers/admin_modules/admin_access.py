import logging
import json
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from config import ADMIN_ID
from utils.keyboard_helper import build_grid_keyboard

logger = logging.getLogger(__name__)

# State for Conversation
ADD_ADMIN_ID = 26

def is_owner(user_id: int) -> bool:
    return str(user_id) == str(ADMIN_ID)

async def show_admin_access_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
    else:
        user_id = update.effective_user.id

    if not is_owner(user_id):
        if query:
            await query.answer("⛔ Access denied. Only the Owner can manage admins.", show_alert=True)
        else:
            await update.message.reply_text("⛔ Access denied. Only the Owner can manage admins.")
        return

    admins_str = db.get_setting("additional_admins", "[]")
    try:
        admins = json.loads(admins_str)
    except Exception:
        admins = []

    text = "🔑 **Admin Access Control** 🔑\n\n"
    text += "Manage additional administrators who have full management rights and access to all channels.\n\n"
    text += "👥 **Active Sub-Admins**:\n"
    
    if not admins:
        text += "_None registered yet._\n"
    else:
        for idx, admin in enumerate(admins, 1):
            name = admin.get("first_name") or admin.get("username") or "Admin"
            uid = admin.get("user_id")
            exp_type = admin.get("expiry_type", "lifetime")
            
            if exp_type == "lifetime":
                exp_text = "♾️ Lifetime"
            else:
                exp_ts = admin.get("expiry_timestamp", 0)
                exp_dt = datetime.fromtimestamp(exp_ts).strftime("%d/%m/%Y")
                if time.time() > exp_ts:
                    exp_text = f"❌ Expired ({exp_dt})"
                else:
                    exp_text = f"⏳ Expiring: {exp_dt}"
                    
            text += f"{idx}. **{name}** (ID: `{uid}`) - {exp_text}\n"

    text += "\nChoose an action below:"
    
    buttons = [
        InlineKeyboardButton("➕ Add New Admin", callback_data="admin_add_admin_start"),
        InlineKeyboardButton("🗑️ Remove Admin", callback_data="admin_remove_admin_list")
    ]
    back_btn = InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def start_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    cancel_btn = InlineKeyboardButton("❌ Cancel", callback_data="admin_access_cancel")
    reply_markup = build_grid_keyboard([], back_button=cancel_btn)
    
    await query.edit_message_text(
        "📝 **Add New Admin**\n\n"
        "Please send the Telegram **User ID** of the user you want to grant admin access to.\n\n"
        "Type /cancel to abort.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return ADD_ADMIN_ID

async def receive_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass

    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=context.user_data["prompt_chat_id"],
                message_id=context.user_data["prompt_msg_id"]
            )
        except Exception:
            pass

    try:
        new_admin_id = int(text)
    except ValueError:
        await update.message.reply_text("❌ Invalid User ID. Must be a number. Process canceled.")
        return ConversationHandler.END

    # Fetch user info
    first_name = "Sub Admin"
    username = ""
    try:
        chat = await context.bot.get_chat(new_admin_id)
        first_name = chat.first_name or "Sub Admin"
        username = chat.username or ""
    except Exception:
        pass

    context.user_data["new_admin_id"] = new_admin_id
    context.user_data["new_admin_name"] = first_name
    context.user_data["new_admin_username"] = username

    # Show duration selection
    text = (
        f"👤 **User selected**: {first_name} (ID: `{new_admin_id}`)\n\n"
        f"Select the admin access duration/type for this user:"
    )
    
    buttons = [
        [InlineKeyboardButton("♾️ Lifetime (Unlimited Access)", callback_data=f"addadmin_dur_lifetime")],
        [InlineKeyboardButton("🗓️ 1 Month (30 Days)", callback_data=f"addadmin_dur_month")],
        [InlineKeyboardButton("❌ Cancel", callback_data="menu_admin_access")]
    ]
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def confirm_add_admin_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    new_admin_id = context.user_data.get("new_admin_id")
    if not new_admin_id:
        await query.edit_message_text("❌ Session expired. Please try again.")
        return
        
    first_name = context.user_data.get("new_admin_name", "Sub Admin")
    username = context.user_data.get("new_admin_username", "")
    
    dur_type = query.data.split("_")[-1]  # "lifetime" or "month"
    
    admins_str = db.get_setting("additional_admins", "[]")
    try:
        admins = json.loads(admins_str)
    except Exception:
        admins = []
        
    # Remove if already exists
    admins = [a for a in admins if int(a.get("user_id", 0)) != int(new_admin_id)]
    
    entry = {
        "user_id": new_admin_id,
        "first_name": first_name,
        "username": username,
        "expiry_type": dur_type,
        "expiry_timestamp": time.time() + 30 * 24 * 3600 if dur_type == "month" else 0
    }
    admins.append(entry)
    db.set_setting("additional_admins", json.dumps(admins))
    
    dur_desc = "Lifetime" if dur_type == "lifetime" else "1 Month (30 Days)"
    
    text = (
        f"✅ **Sub-Admin Added Successfully!**\n\n"
        f"👤 **Name**: {first_name}\n"
        f"🆔 **ID**: `{new_admin_id}`\n"
        f"🕒 **Duration**: {dur_desc}\n\n"
        f"This user now has full administrative rights and access to all channels."
    )
    
    back_btn = InlineKeyboardButton("🔙 Back to Admin Access", callback_data="menu_admin_access")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    context.user_data.clear()

async def show_remove_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    admins_str = db.get_setting("additional_admins", "[]")
    try:
        admins = json.loads(admins_str)
    except Exception:
        admins = []
        
    if not admins:
        await query.edit_message_text(
            "⚠️ No additional admins found to remove.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="menu_admin_access")]]),
            parse_mode="Markdown"
        )
        return
        
    text = "🗑️ **Remove Sub-Admin**\n\nSelect an admin to revoke their administrative rights immediately:"
    
    buttons = []
    for admin in admins:
        name = admin.get("first_name") or admin.get("username") or "Admin"
        uid = admin.get("user_id")
        buttons.append(InlineKeyboardButton(f"👤 {name} (ID: {uid})", callback_data=f"admin_deladmin_{uid}"))
        
    back_btn = InlineKeyboardButton("🔙 Back", callback_data="menu_admin_access")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def remove_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    target_id = int(query.data.split("_")[-1])
    
    admins_str = db.get_setting("additional_admins", "[]")
    try:
        admins = json.loads(admins_str)
    except Exception:
        admins = []
        
    updated_admins = [a for a in admins if int(a.get("user_id", 0)) != target_id]
    db.set_setting("additional_admins", json.dumps(updated_admins))
    
    await query.edit_message_text(
        f"✅ Administrative rights for User ID `{target_id}` have been revoked.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Access", callback_data="menu_admin_access")]]),
        parse_mode="Markdown"
    )

async def cancel_admin_access_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await show_admin_access_menu(update, context)
    return ConversationHandler.END

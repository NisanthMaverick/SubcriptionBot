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
    back_btn = InlineKeyboardButton("🔙 Back to Admin Settings", callback_data="menu_admin_settings")
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

    # Show role selection
    text = (
        f"👤 **User selected**: {first_name} (ID: `{new_admin_id}`)\n\n"
        f"Select the role for this user:\n\n"
        f"👮 **Sub Admin**: Only has access to Raid Channel Protection\n"
        f"🦸‍♂️ **Super Admin**: Has access to all settings except Database Reset and Payments"
    )
    
    buttons = [
        [InlineKeyboardButton("👮 Sub Admin", callback_data=f"addadmin_role_sub_admin")],
        [InlineKeyboardButton("🦸‍♂️ Super Admin", callback_data=f"addadmin_role_super_admin")],
        [InlineKeyboardButton("❌ Cancel", callback_data="menu_admin_access")]
    ]
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def confirm_add_admin_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    new_admin_id = context.user_data.get("new_admin_id")
    if not new_admin_id:
        await query.edit_message_text("❌ Session expired. Please try again.")
        return
        
    role = query.data.split("_role_")[-1]  # "sub_admin" or "super_admin"
    context.user_data["new_admin_role"] = role
    
    first_name = context.user_data.get("new_admin_name", "Sub Admin")
    
    role_name = "Super Admin" if role == "super_admin" else "Sub Admin"
    text = (
        f"👤 **User**: {first_name} (ID: `{new_admin_id}`)\n"
        f"🛡️ **Role**: {role_name}\n\n"
        f"Select the admin access duration:"
    )
    
    buttons = [
        [InlineKeyboardButton("♾️ Lifetime (Unlimited Access)", callback_data=f"addadmin_dur_lifetime")],
        [InlineKeyboardButton("🗓️ 1 Month (30 Days)", callback_data=f"addadmin_dur_month")],
        [InlineKeyboardButton("❌ Cancel", callback_data="menu_admin_access")]
    ]
    
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

async def confirm_add_admin_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    new_admin_id = context.user_data.get("new_admin_id")
    if not new_admin_id:
        await query.edit_message_text("❌ Session expired. Please try again.")
        return
        
    first_name = context.user_data.get("new_admin_name", "Sub Admin")
    username = context.user_data.get("new_admin_username", "")
    role = context.user_data.get("new_admin_role", "super_admin")
    
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
        "role": role,
        "expiry_type": dur_type,
        "expiry_timestamp": time.time() + 30 * 24 * 3600 if dur_type == "month" else 0
    }
    admins.append(entry)
    db.set_setting("additional_admins", json.dumps(admins))
    
    dur_desc = "Lifetime" if dur_type == "lifetime" else "1 Month (30 Days)"
    role_name = "Super Admin" if role == "super_admin" else "Sub Admin"
    
    text = (
        f"✅ **{role_name} Added Successfully!**\n\n"
        f"👤 **Name**: {first_name}\n"
        f"🆔 **ID**: `{new_admin_id}`\n"
        f"🛡️ **Role**: {role_name}\n"
        f"🕒 **Duration**: {dur_desc}\n\n"
    )
    
    if role == "super_admin":
        text += "This user now has access to all settings except Database Reset and Payments."
    else:
        text += "This user now only has access to Raid Channel Protection."
    
    back_btn = InlineKeyboardButton("🔙 Back to Admin Access", callback_data="menu_admin_access")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    
    # Notify the promoted user
    try:
        if role == "super_admin":
            user_notify = (
                f"🎉 **You have been promoted to {role_name}!** 🎉\n\n"
                f"🕒 **Access Duration**: {dur_desc}\n\n"
                "You now have management rights including:\n"
                "• 👥 User & subscriber management\n"
                "• 🛡️ Raid protection controls\n"
                "• 📺 Access to premium channels\n\n"
                "⚡ Use /settings to access the admin panel."
            )
        else:
            user_notify = (
                f"🎉 **You have been promoted to {role_name}!** 🎉\n\n"
                f"🕒 **Access Duration**: {dur_desc}\n\n"
                "You now have access to:\n"
                "• 🛡️ Raid protection controls\n\n"
                "⚡ Use /settings to access the admin panel."
            )
        await context.bot.send_message(chat_id=new_admin_id, text=user_notify, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Could not notify new admin {new_admin_id}: {e}")
    
    # Log to log channel
    log_chan = db.get_setting("log_channel_id", "")
    if log_chan and log_chan not in ["Not Configured", "Not Set", "None", ""]:
        try:
            log_text = (
                "🔑 **Admin Access Update** 🔑\n\n"
                f"✅ **Action**: Promoted to {role_name}\n"
                f"👤 **User**: {first_name} (@{username})\n"
                f"🆔 **User ID**: `{new_admin_id}`\n"
                f"🕒 **Duration**: {dur_desc}\n"
                f"📅 **Date**: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            )
            await context.bot.send_message(chat_id=log_chan, text=log_text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Failed to log admin promotion to log channel: {e}")
    
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
    
    # Find the admin info before removing
    removed_admin = None
    for a in admins:
        if int(a.get("user_id", 0)) == target_id:
            removed_admin = a
            break
    
    updated_admins = [a for a in admins if int(a.get("user_id", 0)) != target_id]
    db.set_setting("additional_admins", json.dumps(updated_admins))
    
    removed_name = removed_admin.get("first_name", "Admin") if removed_admin else "Admin"
    removed_username = removed_admin.get("username", "") if removed_admin else ""
    
    await query.edit_message_text(
        f"✅ Administrative rights for **{removed_name}** (ID: `{target_id}`) have been revoked.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin Access", callback_data="menu_admin_access")]]),
        parse_mode="Markdown"
    )
    
    # Notify the removed user
    try:
        user_notify = (
            "⚠️ **Your Admin Access has been Revoked** ⚠️\n\n"
            "Your sub-admin privileges have been removed by the Owner.\n\n"
            "You no longer have access to:\n"
            "• 👥 User & subscriber management\n"
            "• 🛡️ Raid protection controls\n\n"
            "If you believe this is a mistake, please contact the Owner."
        )
        await context.bot.send_message(chat_id=target_id, text=user_notify, parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Could not notify removed admin {target_id}: {e}")
    
    # Log to log channel
    log_chan = db.get_setting("log_channel_id", "")
    if log_chan and log_chan not in ["Not Configured", "Not Set", "None", ""]:
        try:
            log_text = (
                "🔑 **Admin Access Update** 🔑\n\n"
                f"❌ **Action**: Removed from Sub-Admin\n"
                f"👤 **User**: {removed_name} (@{removed_username})\n"
                f"🆔 **User ID**: `{target_id}`\n"
                f"📅 **Date**: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            )
            await context.bot.send_message(chat_id=log_chan, text=log_text, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Failed to log admin removal to log channel: {e}")

async def cancel_admin_access_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await show_admin_access_menu(update, context)
    return ConversationHandler.END

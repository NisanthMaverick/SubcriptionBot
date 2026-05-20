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
EDIT_SCAN_INTERVAL_INPUT = 122

async def show_raid_menu(query) -> None:
    """
    Displays the Channel Protection system configuration panel.
    """
    from utils.keyboard_helper import build_grid_keyboard
    raid_enabled = db.get_setting("raid_enabled", "0")
    auto_remove = db.get_setting("auto_remove_enabled", "0")
    timeout = db.get_setting("auto_remove_timeout_mins", "10")
    scan_interval = db.get_setting("scan_interval_hours", "0.5")
    raid_chan = db.get_setting("raid_channel_id", "")
    if not raid_chan or raid_chan in ["Not Configured", "Not Set", "None", ""]:
        from config import RAID_CHANNEL
        raid_chan = RAID_CHANNEL
    
    status_prot = "🟢 **ENABLED**" if raid_enabled == "1" else "🔴 **DISABLED**"
    status_rem = "🟢 **ENABLED**" if auto_remove == "1" else "🔴 **DISABLED**"
    
    text = (
        "🛡️ **Premium Channels Protection System** 🛡️\n\n"
        "This system protects your premium channels by scanning for unauthorized members and monitoring new joins.\n\n"
        f"🛡️ **Auto Scan Protection Status**: {status_prot}\n"
        f"🤖 **Auto Kick Non-Subscribers**: {status_rem}\n"
        f"⏱️ **Auto Kick Delay**: `{timeout} minutes`\n"
        f"⏰ **Background Scan Interval**: `{scan_interval} hours`\n"
        f"📢 **Alert Channel ID**: `{raid_chan or 'Log Channel (Default)'}`\n\n"
        "Configure options below or run an on-demand verification scan:"
    )

    buttons = [
        InlineKeyboardButton("🛡️ Auto Scan Protection", callback_data="raid_toggle_prot"),
        InlineKeyboardButton("🤖 Auto-Kick Non-Subscribers", callback_data="raid_toggle_rem"),
        InlineKeyboardButton("⏱️ Set Auto-Kick Delay", callback_data="raid_edit_time_start"),
        InlineKeyboardButton("⏰ Set Background Scan Interval", callback_data="raid_edit_interval_start"),
        InlineKeyboardButton("📢 Edit Alert Channel", callback_data="raid_edit_chan_start"),
        InlineKeyboardButton("🔍 Trigger Manual Scan Now", callback_data="raid_run_scan")
    ]
    back_btn = InlineKeyboardButton("🔙 Back to Configurations", callback_data="menu_config")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

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
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    
    back_btn = InlineKeyboardButton("❌ Cancel", callback_data="raid_cancel")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await query.edit_message_text(
        "⏱️ **Set Auto-Kick Delay Time** ⏱️\n\n"
        "Please send the number of minutes the bot should wait before automatically kicking an unauthorized user after they join or are detected.\n\n"
        "Example: Enter `10` for 10 minutes.\n\n"
        "Type /cancel to keep current settings.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return EDIT_TIMEOUT_INPUT

async def receive_timeout_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
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

    back_btn = InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    try:
        minutes = int(text)
        if minutes <= 0:
            raise ValueError()
        
        db.set_setting("auto_remove_timeout_mins", str(minutes))
        
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f"✅ **Auto-Kick Delay Updated!**\n\n⏱️ New auto-kick delay is set to `{minutes} minutes`.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ **Invalid Number.** Please send a valid positive number of minutes.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    context.user_data.clear()
    return ConversationHandler.END

async def start_edit_raid_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    
    back_btn = InlineKeyboardButton("❌ Cancel", callback_data="raid_cancel")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await query.edit_message_text(
        "📢 **Configure Raid Alert Channel**\n\n"
        "Please send the Telegram Channel ID where the bot should post unauthorized access alerts (e.g. `-1003564494376`).\n\n"
        "Type /cancel to abort.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return EDIT_RAID_CHANNEL_INPUT

async def receive_raid_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
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

    back_btn = InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    try:
        channel_id = int(text)
        db.set_setting("raid_channel_id", str(channel_id))
        
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f"✅ **Raid Alert Channel Updated!**\n\n📢 New Alert Channel ID: `{channel_id}`",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ **Invalid Channel ID.** Please send a valid Telegram Channel ID (e.g. starting with -100).",
            reply_markup=reply_markup,
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

    is_scan_result = "Raid Scan Finished" in (query.message.text or "") or "Remaining Unauthorized Users" in (query.message.text or "")

    try:
        await context.bot.ban_chat_member(chat_id=channel_id, user_id=user_id)
        await context.bot.unban_chat_member(chat_id=channel_id, user_id=user_id)
        
        if is_scan_result and "unauthorized_users" in context.user_data:
            # Remove this specific user/channel combination from the list
            context.user_data["unauthorized_users"] = [
                u for u in context.user_data["unauthorized_users"]
                if not (u["user_id"] == user_id and u["channel_id"] == channel_id)
            ]
            
            remaining = context.user_data["unauthorized_users"]
            if remaining:
                text = (
                    f"✅ **Raid Scan Completed!**\n\n"
                    f"🚨 **Remaining Unauthorized Users**: `{len(remaining)}`\n\n"
                    f"👇 **Manage Remaining Unauthorized Users:**"
                )
                
                # Rebuild inline keyboard buttons
                buttons = []
                buttons.append([InlineKeyboardButton("🚨 Remove All Remaining Users", callback_data="raid_remove_all")])
                
                for u in remaining:
                    display_name = u["first_name"] if len(u["first_name"]) <= 12 else u["first_name"][:10] + ".."
                    chan_name = u["channel_title"] if len(u["channel_title"]) <= 15 else u["channel_title"][:12] + ".."
                    btn_text = f"👤 {display_name} in {chan_name} (❌ Remove)"
                    buttons.append([InlineKeyboardButton(btn_text, callback_data=f"raid_remove_{u['channel_id']}_{u['user_id']}")])
                
                buttons.append([InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")])
                
                await query.edit_message_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    text="✅ **Raid Scan Finished!**\n\n🎉 All unauthorized users have been successfully removed!",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")]]),
                    parse_mode="Markdown"
                )
        else:
            await query.edit_message_text(
                text=query.message.text + "\n\n🚫 **User Removed by Admin**",
                reply_markup=None,
                parse_mode="Markdown"
            )
    except Exception as e:
        if is_scan_result:
            await query.message.reply_text(f"❌ Failed to remove user: {e}", disable_web_page_preview=True)
        else:
            await query.edit_message_text(
                text=query.message.text + f"\n\n❌ **Failed to remove user**: {e}",
                reply_markup=None,
                parse_mode="Markdown"
            )

async def handle_raid_remove_all_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("Removing all unauthorized users... Please wait.")
    
    import json
    data_str = db.get_setting("temp_unauthorized_users", "[]")
    try:
        unauthorized = json.loads(data_str)
    except Exception:
        unauthorized = []
        
    if not unauthorized:
        await query.answer("No unauthorized users to remove.")
        return

    success_count = 0
    fail_count = 0
    
    for u in unauthorized:
        if u.get("removed"):
            continue
        try:
            await context.bot.ban_chat_member(chat_id=u["channel_id"], user_id=u["user_id"])
            await context.bot.unban_chat_member(chat_id=u["channel_id"], user_id=u["user_id"])
            u["removed"] = True
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to bulk-remove {u['user_id']} from {u['channel_id']}: {e}")
            fail_count += 1
            
    db.set_setting("temp_unauthorized_users", json.dumps(unauthorized))
    
    await query.answer(f"✅ Removed: {success_count} entries. Failed: {fail_count} entries.")
    
    await handle_raid_user_list(update, context)

async def handle_raid_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, override_user_id: int = None) -> None:
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    
    if override_user_id is not None:
        user_id = override_user_id
    else:
        user_id = int(query.data.split("_")[-1])
    
    import json
    data_str = db.get_setting("temp_unauthorized_users", "[]")
    try:
        unauthorized = json.loads(data_str)
    except Exception:
        unauthorized = []
        
    user_entries = [u for u in unauthorized if u["user_id"] == user_id]
    if not user_entries:
        await query.edit_message_text(
            text="❌ **User details not found or already removed.**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to User List", callback_data="raid_user_list")]]),
            parse_mode="Markdown"
        )
        return
        
    from utils.formatters import clean_username
    first_name = clean_username(user_entries[0]["first_name"])
    username = clean_username(user_entries[0]["username"])
    
    details = (
        f"👤 **User**: {first_name} (ID: `{user_id}`)\n"
        f"🔗 **Profile**: @{username}\n\n"
        f"📺 **Found in Unauthorized Channels**:\n"
    )
    for u in user_entries:
        status_symbol = "✅ Removed" if u.get("removed") else "❌ Unauthorized"
        details += f"• `{u['channel_title']}` (ID: `{u['channel_id']}`) - {status_symbol}\n"
        
    buttons = []
    
    # 1. Remove user from all channels button at the top (only if at least one is not removed)
    has_any_unremoved = any(not u.get("removed") for u in user_entries)
    if has_any_unremoved:
        buttons.append([InlineKeyboardButton("🚨 Remove this user from all channels", callback_data=f"raid_remuser_all_{user_id}")])
    
    # 2. Individual channel buttons — show status for each channel
    for u in user_entries:
        if u.get("removed"):
            btn_text = f"✅ Removed from {u['channel_title']}"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"raid_already_removed_{user_id}_{u['channel_id']}")])
        else:
            btn_text = f"❌ Remove from {u['channel_title']}"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"raid_remuser_chan_{user_id}_{u['channel_id']}")])
        
    # 3. Back button
    buttons.append([InlineKeyboardButton("🔙 Back to User List", callback_data="raid_user_list")])
    
    await query.edit_message_text(
        text=details,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )

async def handle_raid_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    
    import json
    data_str = db.get_setting("temp_unauthorized_users", "[]")
    try:
        unauthorized = json.loads(data_str)
    except Exception:
        unauthorized = []
        
    is_channel_post = (query.message.chat.type != "private")
    
    if unauthorized:
        text = (
            f"✅ **Raid Scan Results**\n\n"
            f"🚨 **Unauthorized Users Detected**: `{len(unauthorized)}`\n\n"
            f"👇 **Manage Unauthorized Users Below:**"
        )
        
        # Group by user_id
        grouped = {}
        for u in unauthorized:
            uid = u["user_id"]
            if uid not in grouped:
                grouped[uid] = []
            grouped[uid].append(u)
            
        buttons = []
        
        # Remove all users button (only if at least one is not removed)
        has_any_unremoved = any(not u.get("removed") for u in unauthorized)
        if has_any_unremoved:
            buttons.append([InlineKeyboardButton("🚨 Remove all users from unauthorized channels", callback_data="raid_remove_all")])
        
        for uid, entries in grouped.items():
            first_entry = entries[0]
            display_name = first_entry["first_name"]
            if len(display_name) > 15:
                display_name = display_name[:12] + ".."
                
            total_chans = len(entries)
            removed_chans = len([e for e in entries if e.get("removed")])
            
            if removed_chans == total_chans:
                btn_text = f"👤 {display_name} (✅ All Removed)"
            else:
                btn_text = f"👤 {display_name} (ID: {uid}) (❌ {total_chans - removed_chans} left)"
                
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"raid_user_{uid}")])
            
        if is_channel_post:
            buttons.append([InlineKeyboardButton("❌ Close Menu", callback_data="raid_close_post")])
        else:
            buttons.append([InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")])
            
        reply_markup = InlineKeyboardMarkup(buttons)
    else:
        text = "✅ **Raid Scan Finished!**\n\n🎉 All unauthorized users have been successfully removed!"
        if is_channel_post:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close Menu", callback_data="raid_close_post")]])
        else:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")]])
            
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_raid_remuser_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    
    user_id = int(query.data.split("_")[-1])
    
    import json
    data_str = db.get_setting("temp_unauthorized_users", "[]")
    try:
        unauthorized = json.loads(data_str)
    except Exception:
        unauthorized = []
        
    success_count = 0
    fail_count = 0
    errors = []
    
    for u in unauthorized:
        if u["user_id"] == user_id and not u.get("removed"):
            try:
                await context.bot.ban_chat_member(chat_id=u["channel_id"], user_id=user_id)
                await context.bot.unban_chat_member(chat_id=u["channel_id"], user_id=user_id)
                u["removed"] = True
                success_count += 1
            except Exception as e:
                err_str = str(e).lower()
                if "not found" in err_str or "not in the chat" in err_str or "member" in err_str or "left" in err_str:
                    u["removed"] = True
                    success_count += 1
                else:
                    logger.error(f"Failed to remove user {user_id} from {u['channel_id']}: {e}")
                    fail_count += 1
                    errors.append(f"{u['channel_title']}: {e}")
                
    db.set_setting("temp_unauthorized_users", json.dumps(unauthorized))
    
    if fail_count > 0:
        err_details = "\n".join(errors[:3])
        await query.answer(f"⚠️ Removed: {success_count}. Failed: {fail_count}.\nErrors:\n{err_details}", show_alert=True)
    else:
        await query.answer(f"✅ Successfully removed from {success_count} channels!")
        
    await handle_raid_user_menu(update, context, override_user_id=user_id)

async def handle_raid_remuser_chan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    
    parts = query.data.split("_")
    user_id = int(parts[3])
    channel_id = int(parts[4])
    
    import json
    data_str = db.get_setting("temp_unauthorized_users", "[]")
    try:
        unauthorized = json.loads(data_str)
    except Exception:
        unauthorized = []
    
    removed_ok = False
    error_msg = None
    try:
        await context.bot.ban_chat_member(chat_id=channel_id, user_id=user_id)
        await context.bot.unban_chat_member(chat_id=channel_id, user_id=user_id)
        removed_ok = True
    except Exception as e:
        err_str = str(e).lower()
        if "not found" in err_str or "not in the chat" in err_str or "member" in err_str or "left" in err_str:
            removed_ok = True
        else:
            logger.error(f"Failed to remove user {user_id} from {channel_id}: {e}")
            error_msg = str(e)
    
    # Set removed flag outside the try block so it always runs on success
    if removed_ok:
        for u in unauthorized:
            if str(u.get("user_id", "")) == str(user_id) and str(u.get("channel_id", "")) == str(channel_id):
                u["removed"] = True
        await query.answer("✅ User removed successfully!")
    else:
        await query.answer(f"❌ Failed: {error_msg}", show_alert=True)
        
    db.set_setting("temp_unauthorized_users", json.dumps(unauthorized))
    
    await handle_raid_user_menu(update, context, override_user_id=user_id)

async def handle_raid_manage_in_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await handle_raid_user_list(update, context)

async def handle_raid_manage_in_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    import json
    data_str = db.get_setting("temp_unauthorized_users", "[]")
    try:
        unauthorized = json.loads(data_str)
    except Exception:
        unauthorized = []
        
    raid_chan = db.get_setting("raid_channel_id", "")
    if not raid_chan or raid_chan in ["Not Configured", "Not Set", "None", ""]:
        from config import RAID_CHANNEL
        raid_chan = RAID_CHANNEL
        
    if not raid_chan or raid_chan in ["Not Configured", "Not Set", "None", ""]:
        await query.answer("Raid channel not configured!", show_alert=True)
        return
        
    from jobs.raid_scanner import build_raid_results_keyboard, get_raid_channel_link
    
    text = (
        f"✅ **Raid Scan Results**\n\n"
        f"🚨 **Unauthorized Users Detected**: `{len(unauthorized)}`\n\n"
        f"👇 **Manage Unauthorized Users Below:**"
    )
    
    try:
        await context.bot.send_message(
            chat_id=raid_chan,
            text=text,
            reply_markup=build_raid_results_keyboard(unauthorized, show_back=False),
            parse_mode="Markdown"
        )
        await query.answer("Results posted to Raid Channel!")
    except Exception as e:
        logger.error(f"Failed to post results to Raid Channel: {e}")
        await query.answer(f"Failed to post results: {e}", show_alert=True)
        return
        
    admin_text = (
        f"📣 **Scan Results posted to Raid Channel!**\n\n"
        f"You can perform all user removals directly inside the channel.\n"
        f"Click the link below to access the channel."
    )
    
    admin_buttons = []
    invite_link = await get_raid_channel_link(context.bot, raid_chan)
    if invite_link:
        admin_buttons.append([InlineKeyboardButton("📣 Go to Raid Channel", url=invite_link)])
    admin_buttons.append([InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")])
    
    await query.edit_message_text(
        text=admin_text,
        reply_markup=InlineKeyboardMarkup(admin_buttons),
        parse_mode="Markdown"
    )

async def handle_raid_already_removed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer("This user has already been removed from this channel.", show_alert=True)


async def handle_raid_close_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass


async def handle_raid_ignore_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text=query.message.text + "\n\n✅ **Ignored by Admin**",
        reply_markup=None,
        parse_mode="Markdown"
    )

async def start_edit_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    
    back_btn = InlineKeyboardButton("❌ Cancel", callback_data="raid_cancel")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await query.edit_message_text(
        "⏰ **Set Background Scan Interval** ⏰\n\n"
        "Please send the background scan interval in hours (e.g. `0.5` for 30 minutes, `1` for 1 hour, `6` for 6 hours).\n\n"
        "Type /cancel to keep current settings.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return EDIT_SCAN_INTERVAL_INPUT

async def receive_interval_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
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

    back_btn = InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    try:
        hours = float(text)
        if hours <= 0:
            raise ValueError()
        
        db.set_setting("scan_interval_hours", str(hours))
        
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f"✅ **Background Scan Interval Updated!**\n\n⏱️ Background scans will run every `{hours} hours`.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception:
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ **Invalid Number.** Please send a valid positive number of hours (e.g. `0.5` or `2`).",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    context.user_data.clear()
    return ConversationHandler.END

# Scan Interval Configuration Handler
raid_interval_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_edit_interval, pattern="^raid_edit_interval_start$")],
    states={
        EDIT_SCAN_INTERVAL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_interval_input)]
    },
    fallbacks=[
        CallbackQueryHandler(cancel_raid_config, pattern="^raid_cancel$"),
        CommandHandler("cancel", cancel_raid_config)
    ],
    per_message=False
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
    CallbackQueryHandler(handle_raid_remove_all_action, pattern="^raid_remove_all$"),
    CallbackQueryHandler(handle_raid_remove_action, pattern=r"^raid_remove_-?\d+_\d+$"),
    CallbackQueryHandler(handle_raid_ignore_action, pattern="^raid_ignore_"),
    CallbackQueryHandler(handle_raid_user_menu, pattern=r"^raid_user_\d+$"),
    CallbackQueryHandler(handle_raid_user_list, pattern="^raid_user_list$"),
    CallbackQueryHandler(handle_raid_remuser_all, pattern=r"^raid_remuser_all_\d+$"),
    CallbackQueryHandler(handle_raid_remuser_chan, pattern=r"^raid_remuser_chan_\d+_-?\d+$"),
    CallbackQueryHandler(handle_raid_manage_in_bot, pattern="^raid_manage_in_bot$"),
    CallbackQueryHandler(handle_raid_manage_in_channel, pattern="^raid_manage_in_channel$"),
    CallbackQueryHandler(handle_raid_already_removed, pattern=r"^raid_already_removed_\d+_-?\d+$"),
    CallbackQueryHandler(handle_raid_close_post, pattern="^raid_close_post$"),
    CallbackQueryHandler(cancel_raid_config, pattern="^raid_menu$")
]


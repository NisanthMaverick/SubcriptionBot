import logging
import asyncio
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from database import db
from utils.formatters import clean_username

logger = logging.getLogger(__name__)

async def run_member_check(user_id: int, username: str, first_name: str, channel_id: int, channel_title: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    enabled = db.get_setting("raid_enabled", "0")
    if enabled != "1":
        return

    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        from telegram import ChatMember
        if member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            return
    except Exception:
        pass

    has_access = db.check_user_access_to_channel(user_id, channel_id)
    if has_access:
        return

    raid_chan = db.get_setting("raid_channel_id", "")
    if not raid_chan or raid_chan in ["Not Configured", "Not Set", "None", ""]:
        from config import RAID_CHANNEL
        raid_chan = RAID_CHANNEL
    if not raid_chan or raid_chan in ["Not Configured", "Not Set", "None", ""]:
        raid_chan = db.get_setting("log_channel_id", "")
    if not raid_chan or raid_chan in ["Not Configured", "Not Set", "None", ""]:
        from config import ADMIN_ID
        raid_chan = ADMIN_ID

    alert_text = (
        "🚨 **RAID / UNAUTHORIZED JOIN DETECTED** 🚨\n\n"
        f"👤 **User**: [{clean_username(first_name)}](https://t.me/{username}) (`{user_id}`)\n"
        f"📺 **Channel**: {channel_title} (`{channel_id}`)\n"
        "⚠️ **Reason**: No active premium subscription maps to this channel.\n"
    )
    keyboard = [[
        InlineKeyboardButton("❌ Remove User", callback_data=f"raid_remove_{channel_id}_{user_id}"),
        InlineKeyboardButton("✅ Ignore / Keep", callback_data=f"raid_ignore_{channel_id}_{user_id}")
    ]]

    try:
        sent_alert = await context.bot.send_message(
            chat_id=raid_chan,
            text=alert_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        auto_remove = db.get_setting("auto_remove_enabled", "0")
        if auto_remove == "1":
            try: timeout = int(db.get_setting("auto_remove_timeout_mins", "10"))
            except ValueError: timeout = 10
            if context.job_queue:
                context.job_queue.run_once(
                    auto_remove_user_job,
                    when=timeout * 60,
                    data={
                        "chat_id": raid_chan,
                        "message_id": sent_alert.message_id,
                        "channel_id": channel_id,
                        "user_id": user_id,
                        "first_name": first_name,
                        "username": username
                    }
                )
            else:
                logger.warning("JobQueue is not active. Auto-remove user job skipped.")
    except Exception as e:
        logger.error(f"Failed to process raid alert: {e}")

async def auto_remove_user_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    message_id = job_data["message_id"]
    channel_id = job_data["channel_id"]
    user_id = job_data["user_id"]
    first_name = job_data["first_name"]

    has_access = db.check_user_access_to_channel(user_id, channel_id)
    if has_access:
        return

    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        from telegram import ChatMember
        if member.status not in [ChatMember.MEMBER, ChatMember.RESTRICTED]:
            return
    except Exception:
        return

    try:
        await context.bot.ban_chat_member(chat_id=channel_id, user_id=user_id)
        await context.bot.unban_chat_member(chat_id=channel_id, user_id=user_id)
        updated_text = (
            "🚨 **AUTO-REMOVE ACTIVATED** 🚨\n\n"
            f"👤 **User**: {first_name} (`{user_id}`) was **automatically removed**.\n"
            f"📺 **Channel**: Channel ID `{channel_id}`\n"
            "⏱ **Reason**: Auto-remove timeout reached."
        )
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=updated_text, reply_markup=None, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Failed to auto-remove user: {e}")

async def get_raid_channel_link(bot, chat_id):
    try:
        chat = await bot.get_chat(chat_id)
        if chat.username:
            return f"https://t.me/{chat.username}"
        if chat.invite_link:
            return chat.invite_link
        try:
            link = await bot.export_chat_invite_link(chat_id)
            if link:
                return link
        except Exception:
            pass
        cid_str = str(chat_id)
        if cid_str.startswith("-100"):
            return f"https://t.me/c/{cid_str[4:]}/999999999"
    except Exception:
        pass
    return None

def build_raid_results_keyboard(unauthorized_users, show_back=True):
    buttons = []
    if unauthorized_users:
        # Check if there are any active (non-removed) users remaining
        active_entries = [u for u in unauthorized_users if not u.get("removed")]
        if active_entries:
            buttons.append([InlineKeyboardButton("🚨 Remove all users from unauthorized channels", callback_data="raid_remove_all")])
        
        # Group by user_id
        grouped = {}
        for u in unauthorized_users:
            uid = u["user_id"]
            if uid not in grouped:
                grouped[uid] = []
            grouped[uid].append(u)
        
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
            
    if show_back:
        buttons.append([InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")])
    else:
        buttons.append([InlineKeyboardButton("❌ Close Menu", callback_data="raid_close_post")])
    return InlineKeyboardMarkup(buttons)


async def scan_channels_job(context: ContextTypes.DEFAULT_TYPE, admin_query=None) -> None:
    enabled = db.get_setting("raid_enabled", "0")
    unauthorized_users = []
    if enabled != "1" and not admin_query:
        return

    # Check background run interval
    if not admin_query:
        import time
        try:
            last_scan = float(db.get_setting("last_scan_timestamp", "0"))
        except ValueError:
            last_scan = 0.0
        now = time.time()
        try:
            interval_hours = float(db.get_setting("scan_interval_hours", "0.5"))
        except ValueError:
            interval_hours = 0.5
            
        if now - last_scan < (interval_hours * 3600 - 30):
            # Not time yet
            return
        
        # Save timestamp
        db.set_setting("last_scan_timestamp", str(now))

    channels = db.get_all_premium_channels()
    if not channels:
        if admin_query:
            try: await admin_query.edit_message_text("⚠️ No premium channels registered to scan.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="raid_menu")]]))
            except Exception: pass
        return

    user_ids = db.get_all_unique_user_ids()
    if not user_ids:
        if admin_query:
            try: await admin_query.edit_message_text("⚠️ No registered users found in the database to scan.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="raid_menu")]]))
            except Exception: pass
        return

    total_chans = len(channels)
    total_users = len(user_ids)
    unauthorized_count = 0
    checked_users_count = 0

    # Start manual progress tracking if query exists
    tracking_msg = None
    chan_tracking_msg = None
    
    # Check if raid channel is configured
    raid_chan = db.get_setting("raid_channel_id", "")
    if not raid_chan or raid_chan in ["Not Configured", "Not Set", "None", ""]:
        from config import RAID_CHANNEL
        raid_chan = RAID_CHANNEL
        
    is_raid_chan_configured = False
    if raid_chan and raid_chan not in ["Not Configured", "Not Set", "None", ""]:
        is_raid_chan_configured = True

    if admin_query:
        try:
            tracking_msg = await context.bot.send_message(
                chat_id=admin_query.message.chat_id,
                text="🔄 Starting manual verification scan of premium channels..."
            )
        except Exception:
            pass

        if is_raid_chan_configured:
            try:
                chan_tracking_msg = await context.bot.send_message(
                    chat_id=raid_chan,
                    text="🛡️ **Starting Manual Raid Scan...**\nInitializing verification parameters..."
                )
            except Exception:
                pass

    for c_idx, chan in enumerate(channels, 1):
        channel_id = chan["channel_id"]
        channel_title = chan["title"]

        for u_idx, user_id in enumerate(user_ids, 1):
            checked_users_count += 1
            # Retrieve user display name if possible
            first_name = "Premium User"
            username = "NoUsername"
            try:
                sub_rec = db.get_active_paid_subscriptions()
                user_sub = next((s for s in sub_rec if s["user_id"] == user_id), None)
                if user_sub:
                    first_name = user_sub["username"]
            except Exception:
                pass

            try:
                member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                from telegram import ChatMember
                if member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
                    continue
                
                # Check status
                if member.status in [ChatMember.MEMBER, ChatMember.RESTRICTED]:
                    username = member.user.username or "NoUsername"
                    first_name = member.user.first_name or "User"
                    
                    has_access = db.check_user_access_to_channel(user_id, channel_id)
                    if not has_access:
                        unauthorized_count += 1
                        unauthorized_users.append({
                            "user_id": user_id,
                            "username": username,
                            "first_name": first_name,
                            "channel_id": channel_id,
                            "channel_title": channel_title
                        })
            except Exception:
                pass

            if checked_users_count % 3 == 0 or checked_users_count == total_chans * total_users:
                status_text = (
                    "⚡ **Live Raid Scan Tracking** ⚡\n\n"
                    f"📺 **Checking Channel**: `{channel_title}` ({c_idx}/{total_chans})\n"
                    f"👤 **Checking User**: `@{username}` (`{user_id}`) ({u_idx}/{total_users})\n"
                    f"🚨 **Unauthorized Found**: `{unauthorized_count}`\n\n"
                    "⌛ _Scan running..._"
                )
                if tracking_msg:
                    try: await tracking_msg.edit_text(status_text, parse_mode="Markdown")
                    except Exception: pass
                if chan_tracking_msg:
                    try: await chan_tracking_msg.edit_text(status_text, parse_mode="Markdown")
                    except Exception: pass
            await asyncio.sleep(0.05)

    final_text = (
        "✅ **Raid Scan Completed!**\n\n"
        f"📺 **Channels Checked**: `{total_chans}`\n"
        f"👥 **Total User Checks**: `{checked_users_count}`\n"
        f"🚨 **Unauthorized Users Detected**: `{unauthorized_count}`"
    )
    if tracking_msg:
        try: await tracking_msg.edit_text(final_text, parse_mode="Markdown")
        except Exception: pass
    if chan_tracking_msg:
        try: await chan_tracking_msg.edit_text(final_text, parse_mode="Markdown")
        except Exception: pass

    if admin_query:
        import json
        try:
            if unauthorized_users:
                db.set_setting("temp_unauthorized_users", json.dumps(unauthorized_users))
                
                text = (
                    f"✅ **Raid Scan Completed!**\n\n"
                    f"📺 Channels Checked: `{total_chans}`\n"
                    f"👥 User Checks Run: `{checked_users_count}`\n"
                    f"🚨 **Unauthorized Users Detected**: `{len(unauthorized_users)}`\n\n"
                    f"Choose where you want to manage these users:"
                )
                buttons = []
                buttons.append([InlineKeyboardButton("🤖 Manage in Bot (Here)", callback_data="raid_manage_in_bot")])
                if is_raid_chan_configured:
                    buttons.append([InlineKeyboardButton("📣 Manage in Raid Channel", callback_data="raid_manage_in_channel")])
                buttons.append([InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")])
                
                await admin_query.edit_message_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode="Markdown"
                )
            else:
                text = (
                    f"✅ **Raid Scan Finished!**\n\n"
                    f"📺 Channels Checked: `{total_chans}`\n"
                    f"👥 User Checks Run: `{checked_users_count}`\n"
                    f"🎉 **Zero unauthorized users found!** All users have active subscriptions."
                )
                reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")]])
                await admin_query.edit_message_text(
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Error handling admin query after scan completion: {e}")

    if not admin_query:
        import json
        if unauthorized_users:
            db.set_setting("temp_unauthorized_users", json.dumps(unauthorized_users))
            if is_raid_chan_configured:
                text = (
                    f"🚨 **Auto-Scan Results** 🚨\n\n"
                    f"📺 Channels Checked: `{total_chans}`\n"
                    f"👥 User Checks Run: `{checked_users_count}`\n"
                    f"🚨 **Unauthorized Users Detected**: `{len(unauthorized_users)}`\n\n"
                    f"👇 **Manage Unauthorized Users Below:**"
                )
                try:
                    await context.bot.send_message(
                        chat_id=raid_chan,
                        text=text,
                        reply_markup=build_raid_results_keyboard(unauthorized_users, show_back=False),
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to auto-send results to Raid Channel {raid_chan}: {e}")
        import time
        db.set_setting("last_scan_timestamp", str(time.time()))

async def on_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_member = update.chat_member or update.my_chat_member
    if not chat_member:
        return
    from telegram import ChatMember
    if chat_member.new_chat_member.status not in [ChatMember.MEMBER, ChatMember.RESTRICTED]:
        return
    channel_id = chat_member.chat.id
    channels = db.get_all_premium_channels()
    if not any(c["channel_id"] == channel_id for c in channels):
        return
    user = chat_member.new_chat_member.user
    await run_member_check(
        user_id=user.id,
        username=user.username or "NoUsername",
        first_name=user.first_name or "User",
        channel_id=channel_id,
        channel_title=chat_member.chat.title or f"Channel {channel_id}",
        context=context
    )

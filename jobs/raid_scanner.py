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

async def scan_channels_job(context: ContextTypes.DEFAULT_TYPE, admin_query=None) -> None:
    enabled = db.get_setting("raid_enabled", "0")
    if enabled != "1" and not admin_query:
        return

    channels = db.get_all_premium_channels()
    if not channels:
        if admin_query:
            try: await admin_query.edit_message_text("⚠️ No premium channels registered to scan.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="raid_menu")]]))
            except Exception: pass
        return

    user_ids = db.get_all_unique_user_ids()
    if not user_ids:
        if admin_query:
            try: await admin_query.edit_message_text("⚠️ No unique subscribers in the database to scan.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="raid_menu")]]))
            except Exception: pass
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

    tracking_msg = None
    try:
        tracking_msg = await context.bot.send_message(
            chat_id=raid_chan,
            text="🛡️ **Starting Live Raid Scan...**\nInitializing parameters..."
        )
    except Exception as e:
        logger.warning(f"Raid tracking message could not be sent: {e}")

    unauthorized_count = 0
    checked_users_count = 0
    total_chans = len(channels)
    total_users = len(user_ids)

    for c_idx, channel in enumerate(channels, 1):
        channel_id = channel["channel_id"]
        channel_title = channel["title"]

        for u_idx, user_id in enumerate(user_ids, 1):
            checked_users_count += 1
            username = f"User {user_id}"
            first_name = "User"
            try:
                member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                from telegram import ChatMember
                if member.status in [ChatMember.MEMBER, ChatMember.RESTRICTED]:
                    username = member.user.username or "NoUsername"
                    first_name = member.user.first_name or "User"
                    
                    has_access = db.check_user_access_to_channel(user_id, channel_id)
                    is_admin = member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
                    if not has_access and not is_admin:
                        unauthorized_count += 1
                        await run_member_check(
                            user_id=user_id,
                            username=username,
                            first_name=first_name,
                            channel_id=channel_id,
                            channel_title=channel_title,
                            context=context
                        )
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
                if admin_query:
                    try:
                        await admin_query.edit_message_text(
                            f"🔄 **Raid Scan in Progress...**\n\n"
                            f"📺 **Channel**: `{channel_title}` ({c_idx}/{total_chans})\n"
                            f"👤 **User**: `@{username}` ({u_idx}/{total_users})\n"
                            f"🚨 **Unauthorized Found**: `{unauthorized_count}`\n\n"
                            "⌛ Please wait...",
                            parse_mode="Markdown"
                        )
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

    if admin_query:
        try:
            keyboard = [[InlineKeyboardButton("🔙 Back to Protection Menu", callback_data="raid_menu")]]
            await admin_query.edit_message_text(
                f"✅ **Raid Scan Finished!**\n\n"
                f"📺 Channels Checked: `{total_chans}`\n"
                f"👥 User Checks Run: `{checked_users_count}`\n"
                f"🚨 Unauthorized Found: `{unauthorized_count}`\n\n"
                "Alert cards have been sent to the Raid Alert Channel.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception: pass

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

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import db

logger = logging.getLogger(__name__)

ADD_CHANNEL_INPUT = 100

async def edit_message_safely(query, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.warning(f"Error editing message safely: {e}")

async def show_channels_menu(query) -> None:
    channels = db.get_all_premium_channels()
    text = (
        "📺 **Premium Channels Management** 📺\n\n"
        "Manage monitored premium channels and plan associations.\n\n"
        "**Monitored Channels List:**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    if not channels:
        text += "⚠️ _No channels added yet._\n"
    else:
        for idx, c in enumerate(channels, 1):
            mapped_plans = []
            plans = db.get_all_plans()
            for p in plans:
                chans = db.get_channels_for_plan(p["plan_id"])
                if any(ch["channel_id"] == c["channel_id"] for ch in chans):
                    mapped_plans.append(p["name"].split("\n")[0].strip())
            plan_str = ", ".join(mapped_plans) if mapped_plans else "_None_"
            text += f"{idx}️⃣ **{c['title']}**\n   ├ 🆔 `{c['channel_id']}`\n   └ 📦 Plans: `{plan_str}`\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━"

    keyboard = [
        [InlineKeyboardButton("➕ Add Premium Channel", callback_data="chan_add"),
         InlineKeyboardButton("🔗 Map Channel to Plan", callback_data="chan_map_start")],
        [InlineKeyboardButton("🔍 Verify Channels & Links", callback_data="chan_verify_all")],
        [InlineKeyboardButton("❌ Remove Channel", callback_data="chan_del_list"),
         InlineKeyboardButton("🔙 Back to Configurations", callback_data="menu_config")]
    ]
    await edit_message_safely(query, text, InlineKeyboardMarkup(keyboard))

async def start_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="chan_cancel")]]
    await edit_message_safely(
        query,
        "➕ **Add Premium Channel**\n\n"
        "1. Add this bot as an **Administrator** with invite link creation rights.\n"
        "2. Then:\n"
        "   • **Forward a message** from that channel here.\n"
        "   • Or send the **Channel ID** (e.g. `-1003564494376`).\n\n"
        "Type /cancel to abort.",
        InlineKeyboardMarkup(keyboard)
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return ADD_CHANNEL_INPUT

async def receive_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try: await update.message.delete()
    except Exception: pass
    if "prompt_msg_id" in context.user_data:
        try: await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception: pass

    channel_id = None
    if update.message.forward_origin:
        from telegram import MessageOriginChannel, MessageOriginChat
        if isinstance(update.message.forward_origin, MessageOriginChannel):
            channel_id = update.message.forward_origin.chat.id
        elif isinstance(update.message.forward_origin, MessageOriginChat):
            channel_id = update.message.forward_origin.sender_chat.id
            
    if not channel_id:
        try: channel_id = int(update.message.text.strip())
        except (ValueError, AttributeError): pass

    keyboard = [[InlineKeyboardButton("🔙 Back to Channels Menu", callback_data="chan_menu")]]
    if not channel_id:
        await context.bot.send_message(chat_id=update.message.chat_id, text="❌ **Invalid Input.** Forward a message or send a channel ID.", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    try:
        chat = await context.bot.get_chat(channel_id)
        from telegram import ChatMember
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=context.bot.id)
        if member.status != ChatMember.ADMINISTRATOR:
            raise Exception("Bot is not an administrator in this channel.")

        invite_link = chat.invite_link or (await context.bot.create_chat_invite_link(chat_id=channel_id, name="Subscription VIP Link")).invite_link
        title = chat.title or f"Channel {channel_id}"
        db.add_premium_channel(channel_id, title, invite_link)
        
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text=f"✅ **Channel Added!**\n\n📺 **Title**: {title}\n🆔 **ID**: `{channel_id}`\n🔗 **Link**: {invite_link}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        await context.bot.send_message(chat_id=update.message.chat_id, text=f"❌ **Failed to verify/add channel:**\n\n`{e}`", reply_markup=InlineKeyboardMarkup(keyboard))

    context.user_data.clear()
    return ConversationHandler.END

async def start_map_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    channels = db.get_all_premium_channels()
    if not channels:
        await edit_message_safely(query, "⚠️ No channels available.", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="chan_menu")]]))
        return
    keyboard = [[InlineKeyboardButton(f"📺 {c['title']}", callback_data=f"chan_map_select_{c['channel_id']}")] for c in channels]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="chan_menu")])
    await edit_message_safely(query, "🔗 **Map Channel to Plans**\n\nSelect the channel:", InlineKeyboardMarkup(keyboard))

async def select_channel_for_mapping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    channel_id = int(query.data.split("_")[-1])
    await show_channel_mapping_toggles(query, channel_id)

async def show_channel_mapping_toggles(query, channel_id: int) -> None:
    plans = db.get_all_plans()
    channel = db.get_premium_channel(channel_id)
    if not channel:
        await edit_message_safely(query, "❌ Channel not found.", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="chan_menu")]]))
        return

    mapped_plan_ids = []
    for p in plans:
        chans = db.get_channels_for_plan(p["plan_id"])
        if any(ch["channel_id"] == channel_id for ch in chans):
            mapped_plan_ids.append(p["plan_id"])

    keyboard = []
    for p in plans:
        is_mapped = p["plan_id"] in mapped_plan_ids
        status_icon = "✅" if is_mapped else "🔳"
        clean_name = p['name'].split('\n')[0][:40]
        keyboard.append([InlineKeyboardButton(f"{status_icon} {clean_name}", callback_data=f"chan_toggle_{channel_id}_{p['plan_id']}")])

    keyboard.append([InlineKeyboardButton("🔙 Done / Back", callback_data="chan_menu")])
    text = (
        f"📺 **Channel**: {channel['title']}\n🆔 **ID**: `{channel_id}`\n\n"
        "Click subscription plans to toggle access:\n- ✅ : Has access\n- 🔳 : No access"
    )
    await edit_message_safely(query, text, InlineKeyboardMarkup(keyboard))

async def toggle_channel_plan_mapping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    channel_id, plan_id = int(parts[2]), int(parts[3])

    plans = db.get_all_plans()
    is_currently_mapped = False
    for p in plans:
        if p["plan_id"] == plan_id:
            chans = db.get_channels_for_plan(plan_id)
            if any(ch["channel_id"] == channel_id for ch in chans):
                is_currently_mapped = True
                break

    if is_currently_mapped:
        db.remove_channel_mapping(channel_id, plan_id)
    else:
        db.add_channel_mapping(channel_id, plan_id)
    await show_channel_mapping_toggles(query, channel_id)

async def list_channels_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    channels = db.get_all_premium_channels()
    if not channels:
        await edit_message_safely(query, "⚠️ No channels to delete.", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="chan_menu")]]))
        return
    keyboard = [[InlineKeyboardButton(f"🗑️ Delete: {c['title']}", callback_data=f"chan_del_confirm_{c['channel_id']}")] for c in channels]
    keyboard.append([InlineKeyboardButton("🔙 Back to Channels Menu", callback_data="chan_menu")])
    await edit_message_safely(query, "❌ **Remove Premium Channel**\n\nWarning: Removing a channel will delete its plan mappings.", InlineKeyboardMarkup(keyboard))

async def confirm_delete_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    channel_id = int(query.data.split("_")[-1])
    channel = db.get_premium_channel(channel_id)
    msg = f"✅ Channel **{channel['title']}** removed." if channel else "❌ Channel not found."
    if channel:
        db.delete_premium_channel(channel_id)
    keyboard = [[InlineKeyboardButton("🔙 Back to Channels Menu", callback_data="chan_menu")]]
    await edit_message_safely(query, msg, InlineKeyboardMarkup(keyboard))

async def verify_all_channels_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    channels = db.get_all_premium_channels()
    if not channels:
        await edit_message_safely(query, "⚠️ No premium channels registered.", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="chan_menu")]]))
        return

    total = len(channels)
    status_msg = await query.edit_message_text(f"🔄 **Initializing Channel Verification (0/{total})...**\n\nPlease wait.", parse_mode="Markdown")
    report_lines = []
    from telegram import ChatMember

    for idx, c in enumerate(channels, 1):
        try: await status_msg.edit_text(f"🔄 **Checking Channel {idx}/{total}:**\n`{c['title']}`...", parse_mode="Markdown")
        except Exception: pass

        chan_id, title = c["channel_id"], c["title"]
        status_icon, status_text, permissions_text, link_status = "❌", "No Access", "N/A", "❌ None"

        try:
            chat = await context.bot.get_chat(chan_id)
            member = await context.bot.get_chat_member(chat_id=chan_id, user_id=context.bot.id)
            if member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
                status_icon, status_text = "🟢", "Accessible (Admin)"
                can_invite = getattr(member, "can_invite_users", False) or member.status == ChatMember.OWNER
                permissions_text = "Invite Users: " + ("✅ Yes" if can_invite else "❌ No")
                invite_link = chat.invite_link
                if not invite_link:
                    try:
                        invite_link = (await context.bot.create_chat_invite_link(chat_id=chan_id, name="Subscription VIP Link")).invite_link
                        db.add_premium_channel(chan_id, chat.title or title, invite_link)
                    except Exception: invite_link = None
                link_status = f"[Join Link]({invite_link})" if invite_link else "❌ Link Gen Failed"
            else:
                status_icon, status_text, permissions_text, link_status = "🟡", "Accessible (Not Admin)", "Invite Users: ❌ No", "❌ Cannot export link"
        except Exception as e:
            status_text = f"Error: {e}"

        report_lines.append(f"{idx}️⃣ {status_icon} **{title}**\n   ├ 🆔 `{chan_id}`\n   ├ Status: `{status_text}`\n   ├ Perms: `{permissions_text}`\n   └ Link: {link_status}")

    report_text = "📋 **Channel Status & Permissions Report** 📋\n\n━━━━━━━━━━━━━━━━━━━━\n" + "\n\n".join(report_lines) + "\n━━━━━━━━━━━━━━━━━━━━"
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Channels Menu", callback_data="chan_menu"),
         InlineKeyboardButton("🔙 Back to Raid Menu", callback_data="raid_menu")]
    ]
    await status_msg.edit_text(report_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown", disable_web_page_preview=True)

async def cancel_channel_mapping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        await show_channels_menu(query)
    context.user_data.clear()
    return ConversationHandler.END

channel_add_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_channel, pattern="^chan_add$")],
    states={ADD_CHANNEL_INPUT: [MessageHandler(filters.ALL & ~filters.COMMAND, receive_channel_input)]},
    fallbacks=[CallbackQueryHandler(cancel_channel_mapping, pattern="^chan_cancel$"), CommandHandler("cancel", cancel_channel_mapping)],
    per_message=False
)

channel_nav_handlers = [
    CallbackQueryHandler(list_channels_to_delete, pattern="^chan_del_list$"),
    CallbackQueryHandler(confirm_delete_channel, pattern="^chan_del_confirm_"),
    CallbackQueryHandler(start_map_channel, pattern="^chan_map_start$"),
    CallbackQueryHandler(select_channel_for_mapping, pattern="^chan_map_select_"),
    CallbackQueryHandler(toggle_channel_plan_mapping, pattern="^chan_toggle_"),
    CallbackQueryHandler(verify_all_channels_status, pattern="^chan_verify_all$"),
    CallbackQueryHandler(cancel_channel_mapping, pattern="^chan_menu$")
]

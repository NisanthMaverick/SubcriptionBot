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
        "Monitored premium channels and plan associations.\n\n"
        "**Monitored Channels List:**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    if not channels:
        text += "⚠️ _No channels added yet._\n"
    else:
        # Optimize queries: fetch plans and mappings once
        plans = db.get_all_plans()
        plan_titles = {p["plan_id"]: p["name"].split("\n")[0].strip() for p in plans}
        mappings = db.get_all_channel_mappings()
        
        channel_plans_map = {}
        for m in mappings:
            c_id = m["channel_id"]
            p_id = m["plan_id"]
            if p_id in plan_titles:
                if c_id not in channel_plans_map:
                    channel_plans_map[c_id] = []
                channel_plans_map[c_id].append(plan_titles[p_id])

        for idx, c in enumerate(channels, 1):
            mapped_plans = channel_plans_map.get(c["channel_id"], [])
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
    plans = db.get_all_plans()
    if not plans:
        await edit_message_safely(query, "⚠️ No plans available.", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="chan_menu")]]))
        return
    keyboard = [[InlineKeyboardButton(f"📦 {p['name'].split('\n')[0][:40]}", callback_data=f"chan_map_select_{p['plan_id']}")] for p in plans]
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="chan_menu")])
    await edit_message_safely(query, "🔗 **Map Channels to Plan**\n\nSelect a Subscription Plan to manage its channel access:", InlineKeyboardMarkup(keyboard))

async def select_channel_for_mapping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.split("_")[-1])
    await show_plan_channel_toggles(query, plan_id)

async def show_plan_channel_toggles(query, plan_id: int) -> None:
    plan = db.get_plan(plan_id)
    if not plan:
        await edit_message_safely(query, "❌ Plan not found.", InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="chan_menu")]]))
        return

    channels = db.get_all_premium_channels()
    mapped_channels = db.get_channels_for_plan(plan_id)
    mapped_channel_ids = {c["channel_id"] for c in mapped_channels}

    keyboard = []
    for c in channels:
        is_mapped = c["channel_id"] in mapped_channel_ids
        status_icon = "✅" if is_mapped else "🔳"
        clean_name = c["title"][:40]
        keyboard.append([InlineKeyboardButton(f"{status_icon} {clean_name}", callback_data=f"chan_toggle_{plan_id}_{c['channel_id']}")])

    # Select All / Deselect All Row
    keyboard.append([
        InlineKeyboardButton("✅ Select All", callback_data=f"chan_mapall_{plan_id}"),
        InlineKeyboardButton("🔳 Deselect All", callback_data=f"chan_unmapall_{plan_id}")
    ])
    keyboard.append([InlineKeyboardButton("🔙 Done / Back", callback_data="chan_map_start")])

    total_chans = len(channels)
    selected_chans = len(mapped_channel_ids)
    text = (
        f"📦 **Plan**: {plan['name']}\n"
        f"💵 **Price**: {plan['amount']}\n"
        f"📊 **Mapped Channels**: `{selected_chans} / {total_chans}` selected\n\n"
        "Click premium channels to toggle access for this plan:\n- ✅ : Included in plan\n- 🔳 : Not in plan"
    )
    await edit_message_safely(query, text, InlineKeyboardMarkup(keyboard))

async def toggle_channel_plan_mapping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    plan_id, channel_id = int(parts[2]), int(parts[3])

    mapped_channels = db.get_channels_for_plan(plan_id)
    is_currently_mapped = any(c["channel_id"] == channel_id for c in mapped_channels)

    if is_currently_mapped:
        db.remove_channel_mapping(channel_id, plan_id)
    else:
        db.add_channel_mapping(channel_id, plan_id)
    await show_plan_channel_toggles(query, plan_id)

async def map_all_channels_to_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.split("_")[-1])
    channels = db.get_all_premium_channels()
    for c in channels:
        db.add_channel_mapping(c["channel_id"], plan_id)
    await show_plan_channel_toggles(query, plan_id)

async def unmap_all_channels_from_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.split("_")[-1])
    channels = db.get_all_premium_channels()
    for c in channels:
        db.remove_channel_mapping(c["channel_id"], plan_id)
    await show_plan_channel_toggles(query, plan_id)

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
        [InlineKeyboardButton("🔙 Back to Channels Menu", callback_data="chan_menu")]
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
    CallbackQueryHandler(map_all_channels_to_plan, pattern="^chan_mapall_"),
    CallbackQueryHandler(unmap_all_channels_from_plan, pattern="^chan_unmapall_"),
    CallbackQueryHandler(verify_all_channels_status, pattern="^chan_verify_all$"),
    CallbackQueryHandler(cancel_channel_mapping, pattern="^chan_menu$")
]

import logging
import time
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler
from database import db
from handlers.admin_modules import ADMIN_BROADCAST, ADMIN_ADD_DB

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
#  STEP 1 — Audience selector  (All Users / Premium Users)
# ─────────────────────────────────────────────────────────
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()

    buttons = [
        InlineKeyboardButton("👥 All Users",      callback_data="bc_type_all"),
        InlineKeyboardButton("👑 Premium Users",  callback_data="bc_type_premium"),
    ]
    back_btn = InlineKeyboardButton("❌ Cancel", callback_data="menu_admin_settings")
    await query.edit_message_text(
        "📢 **Broadcast System** 📢\n\n"
        "Select the target audience for your broadcast:",
        reply_markup=build_grid_keyboard(buttons, back_button=back_btn),
        parse_mode="Markdown"
    )
    return ADMIN_BROADCAST


# ─────────────────────────────────────────────────────────
#  STEP 2a — All Users → content-type chooser
# ─────────────────────────────────────────────────────────
async def bc_type_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    context.user_data["bc_target"] = "all"
    context.user_data.pop("bc_selected_plans",    None)
    context.user_data.pop("bc_selected_channels", None)
    context.user_data.pop("bc_content_type",      None)
    context.user_data.pop("bc_opt_msg_chat_id",   None)
    context.user_data.pop("bc_opt_msg_id",        None)

    buttons = [
        InlineKeyboardButton("💬 Send Message / Media", callback_data="bc_content_message"),
        InlineKeyboardButton("🔗 Send Channel Link",    callback_data="bc_content_channel"),
    ]
    await query.edit_message_text(
        "👥 **Broadcast → All Users**\n\nWhat would you like to send?",
        reply_markup=build_grid_keyboard(buttons,
                                         back_button=InlineKeyboardButton("🔙 Back", callback_data="bc_back_to_start")),
        parse_mode="Markdown"
    )
    return ADMIN_BROADCAST


# ─────────────────────────────────────────────────────────
#  STEP 2b — Premium Users → plan multi-select
# ─────────────────────────────────────────────────────────
async def bc_type_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    context.user_data["bc_target"] = "premium"
    context.user_data.pop("bc_selected_channels", None)
    context.user_data.pop("bc_content_type",      None)
    context.user_data.pop("bc_opt_msg_chat_id",   None)
    context.user_data.pop("bc_opt_msg_id",        None)
    if "bc_selected_plans" not in context.user_data:
        context.user_data["bc_selected_plans"] = []
    await _show_plan_selection(query, context)
    return ADMIN_BROADCAST


async def _show_plan_selection(query, context: ContextTypes.DEFAULT_TYPE):
    from utils.keyboard_helper import build_grid_keyboard
    plans    = db.get_all_plans()
    selected = context.user_data.get("bc_selected_plans", [])

    buttons = []
    for p in plans:
        tick = "✅ " if p["plan_id"] in selected else "☑️ "
        name = p["name"].split("\n")[0][:35]
        buttons.append(InlineKeyboardButton(f"{tick}{name}", callback_data=f"bc_plan_{p['plan_id']}"))

    if selected:
        buttons.append(InlineKeyboardButton("▶️ Continue", callback_data="bc_plans_done"))

    selected_names = [p["name"].split("\n")[0][:30] for p in plans if p["plan_id"] in selected]
    status = f"✅ Selected: {', '.join(selected_names)}" if selected_names else "⚠️ No plans selected yet."

    await query.edit_message_text(
        "👑 **Broadcast → Premium Users**\n\n"
        "Tick one or more plans. Only those subscribers will receive the broadcast.\n\n"
        f"{status}",
        reply_markup=build_grid_keyboard(buttons,
                                         back_button=InlineKeyboardButton("🔙 Back", callback_data="bc_back_to_start")),
        parse_mode="Markdown"
    )


async def bc_toggle_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    plan_id  = int(query.data.split("_")[-1])
    selected = context.user_data.get("bc_selected_plans", [])
    if plan_id in selected:
        selected.remove(plan_id)
    else:
        selected.append(plan_id)
    context.user_data["bc_selected_plans"] = selected
    await _show_plan_selection(query, context)
    return ADMIN_BROADCAST


async def bc_plans_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    buttons = [
        InlineKeyboardButton("💬 Send Message / Media", callback_data="bc_content_message"),
        InlineKeyboardButton("🔗 Send Channel Link",    callback_data="bc_content_channel"),
    ]
    await query.edit_message_text(
        "👑 **Broadcast → Premium Users**\n\nWhat would you like to send?",
        reply_markup=build_grid_keyboard(buttons,
                                         back_button=InlineKeyboardButton("🔙 Back", callback_data="bc_type_premium")),
        parse_mode="Markdown"
    )
    return ADMIN_BROADCAST


# ─────────────────────────────────────────────────────────
#  STEP 3a — "Send Message" path
# ─────────────────────────────────────────────────────────
async def bc_content_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    context.user_data["bc_content_type"] = "message"

    msg = await query.edit_message_text(
        "💬 **Broadcast — Send Message / Media**\n\n"
        "Send the message (text, photo, video, document) to broadcast to all target users.\n\n"
        "Type /cancel to abort.",
        reply_markup=build_grid_keyboard([], back_button=InlineKeyboardButton("❌ Cancel", callback_data="menu_admin_settings")),
        parse_mode="Markdown"
    )
    context.user_data["prompt_chat_id"] = msg.chat_id
    context.user_data["prompt_msg_id"]  = msg.message_id
    return ADMIN_BROADCAST


# ─────────────────────────────────────────────────────────
#  STEP 3b — "Send Channel Link" path → multi-channel select
# ─────────────────────────────────────────────────────────
async def bc_content_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()

    context.user_data["bc_content_type"]      = "channel_only"
    context.user_data["bc_selected_channels"] = context.user_data.get("bc_selected_channels", [])

    channels = db.get_all_premium_channels()
    if not channels:
        await query.edit_message_text(
            "⚠️ No premium channels configured yet.\n\n"
            "Go to Bot Configurations → Premium Channels to add channels first.",
            reply_markup=build_grid_keyboard([], back_button=InlineKeyboardButton("🔙 Back", callback_data="bc_back_to_start")),
            parse_mode="Markdown"
        )
        return ADMIN_BROADCAST

    await _show_channel_selection(query, context)
    return ADMIN_BROADCAST


async def _show_channel_selection(query, context: ContextTypes.DEFAULT_TYPE):
    """Render multi-channel checkbox UI."""
    from utils.keyboard_helper import build_grid_keyboard
    channels = db.get_all_premium_channels()
    selected = context.user_data.get("bc_selected_channels", [])

    buttons = []
    for c in channels:
        cid   = c["channel_id"]
        tick  = "✅ " if cid in selected else "☑️ "
        title = c["title"][:38]
        buttons.append(InlineKeyboardButton(f"{tick}{title}", callback_data=f"bc_chsel_{cid}"))

    if selected:
        buttons.append(InlineKeyboardButton("▶️ Continue", callback_data="bc_chans_done"))

    selected_titles = [c["title"][:25] for c in channels if c["channel_id"] in selected]
    status = f"✅ Selected: {', '.join(selected_titles)}" if selected_titles else "⚠️ No channels selected yet."

    await query.edit_message_text(
        "🔗 **Broadcast — Select Channel Link(s)**\n\n"
        "Tick one or more channels. Their invite links will be sent to all target users.\n\n"
        f"{status}",
        reply_markup=build_grid_keyboard(buttons,
                                         back_button=InlineKeyboardButton("🔙 Back", callback_data="bc_back_to_start")),
        parse_mode="Markdown"
    )


async def bc_toggle_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Toggle a channel in the multi-select list."""
    query = update.callback_query
    await query.answer()
    # data looks like "bc_chsel_-1001234567890"
    raw     = query.data[len("bc_chsel_"):]
    cid     = int(raw)
    selected = context.user_data.get("bc_selected_channels", [])
    if cid in selected:
        selected.remove(cid)
    else:
        selected.append(cid)
    context.user_data["bc_selected_channels"] = selected
    await _show_channel_selection(query, context)
    return ADMIN_BROADCAST


# ─────────────────────────────────────────────────────────
#  STEP 4 — Channels confirmed → optional message step
# ─────────────────────────────────────────────────────────
async def bc_chans_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Channels confirmed — offer optional message or skip to send."""
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()

    channels  = db.get_all_premium_channels()
    sel_ids   = context.user_data.get("bc_selected_channels", [])
    sel_names = [c["title"][:30] for c in channels if c["channel_id"] in sel_ids]

    buttons = [
        InlineKeyboardButton("📝 Add Message (Optional)", callback_data="bc_opt_add_msg"),
        InlineKeyboardButton("⏭️ Skip & Show Send Button",  callback_data="bc_opt_skip"),
    ]
    await query.edit_message_text(
        "🔗 **Broadcast — Optional Message**\n\n"
        f"📺 Channels selected: **{', '.join(sel_names)}**\n\n"
        "Would you like to add a **custom message** along with the channel link(s)?\n"
        "_(Text, photo, video or document — shown above the channel buttons)_\n\n"
        "• **Add Message** → type/send your message next\n"
        "• **Skip** → go straight to the Send button",
        reply_markup=build_grid_keyboard(buttons,
                                         back_button=InlineKeyboardButton("🔙 Back", callback_data="bc_content_channel")),
        parse_mode="Markdown"
    )
    return ADMIN_BROADCAST


# ─────────────────────────────────────────────────────────
#  STEP 5a — Admin wants to add a message
# ─────────────────────────────────────────────────────────
async def bc_opt_add_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    context.user_data["bc_content_type"] = "channel_with_msg"

    msg = await query.edit_message_text(
        "📝 **Add Optional Message**\n\n"
        "Send your message now (text, photo, video or document).\n"
        "It will be sent to each user **before** the channel invite button(s).\n\n"
        "Type /cancel to abort.",
        reply_markup=build_grid_keyboard([], back_button=InlineKeyboardButton("❌ Cancel", callback_data="menu_admin_settings")),
        parse_mode="Markdown"
    )
    context.user_data["prompt_chat_id"] = msg.chat_id
    context.user_data["prompt_msg_id"]  = msg.message_id
    return ADMIN_BROADCAST


# ─────────────────────────────────────────────────────────
#  STEP 5b — Admin skips message → show Send button
# ─────────────────────────────────────────────────────────
async def bc_opt_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    context.user_data["bc_content_type"] = "channel_only"
    await _show_send_confirm(query, context)
    return ADMIN_BROADCAST


async def _show_send_confirm(query, context: ContextTypes.DEFAULT_TYPE):
    """Show summary + Send Broadcast button."""
    from utils.keyboard_helper import build_grid_keyboard

    user_ids  = _resolve_user_ids(context)
    channels  = db.get_all_premium_channels()
    sel_ids   = context.user_data.get("bc_selected_channels", [])
    sel_names = [c["title"][:28] for c in channels if c["channel_id"] in sel_ids]
    target    = _resolve_label(context)
    has_msg   = context.user_data.get("bc_content_type") == "channel_with_msg"

    try:
        expiry_mins = int(db.get_setting("link_expiry_minutes", "3"))
    except Exception:
        expiry_mins = 3

    summary = (
        "📤 **Ready to Send — Broadcast Summary**\n\n"
        f"👥 **Target**: {target} (`{len(user_ids)}` users)\n"
        f"📺 **Channels**: {', '.join(sel_names)}\n"
        f"📝 **Custom Message**: {'✅ Yes' if has_msg else '⛔ None (links only)'}\n"
        f"⏱️ **Link expires in**: {expiry_mins} min (forward-restricted)\n\n"
        "Press **📤 Send Broadcast** to start."
    )
    buttons = [InlineKeyboardButton("📤 Send Broadcast", callback_data="bc_send_now")]
    await query.edit_message_text(
        summary,
        reply_markup=build_grid_keyboard(buttons,
                                         back_button=InlineKeyboardButton("🔙 Back", callback_data="bc_chans_done")),
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────────────────
#  STEP 6 — Execute channel broadcast with live tracking
# ─────────────────────────────────────────────────────────
async def bc_send_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Execute the broadcast with live progress tracking."""
    query = update.callback_query
    await query.answer()
    await _do_channel_broadcast(query, context)
    return ConversationHandler.END


async def _do_channel_broadcast(query, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast a 'Get Link' teaser. Replaces the confirm message in-place with
    live progress — no new messages created."""
    from utils.keyboard_helper import build_grid_keyboard

    user_ids  = _resolve_user_ids(context)
    sel_ids   = context.user_data.get("bc_selected_channels", [])
    all_chans = db.get_all_premium_channels()
    channels  = [c for c in all_chans if c["channel_id"] in sel_ids]

    if not user_ids or not channels:
        back_btn = InlineKeyboardButton("🔙 Back to Admin Settings", callback_data="menu_admin_settings")
        await query.edit_message_text(
            "⚠️ No users or channels found for this broadcast.",
            reply_markup=build_grid_keyboard([], back_button=back_btn),
            parse_mode="Markdown"
        )
        return

    total     = len(user_ids)
    stat_chat = query.message.chat_id
    stat_mid  = query.message.message_id

    # ── Replace confirm screen with "Starting" in-place ────
    await query.edit_message_text(
        f"📡 **Broadcast Started**\n\n"
        f"👥 Target   : **{total}** users\n"
        f"📺 Channels : **{len(channels)}**\n\n"
        f"⏳ Progress : **0 / {total}** sent...",
        parse_mode="Markdown"
    )

    try:
        expiry_mins = int(db.get_setting("link_expiry_minutes", "3"))
    except Exception:
        expiry_mins = 3

    has_opt_msg  = context.user_data.get("bc_content_type") == "channel_with_msg"
    opt_msg_chat = context.user_data.get("bc_opt_msg_chat_id")
    opt_msg_id   = context.user_data.get("bc_opt_msg_id")

    # ── Create session for Get Link button ─────────────────
    session_id = uuid.uuid4().hex[:12]
    if "bc_link_sessions" not in context.application.bot_data:
        context.application.bot_data["bc_link_sessions"] = {}
    context.application.bot_data["bc_link_sessions"][session_id] = {
        "channel_ids":  sel_ids,
        "expiry_mins":  expiry_mins,
        "created_at":   time.time(),
    }

    chan_names = " | ".join(c["title"][:25] for c in channels)

    teaser_text = (
        "🎁 **Exclusive VIP Channel Access Reserved For You!**\n\n"
        f"An administrator has sent you access to:\n📺 **{chan_names}**\n\n"
        "⚠️ **Important:** Once you click **Get Link**, your invite link(s) will be"
        f" delivered and will auto-delete in **{expiry_mins} minutes** for security.\n"
        "_Make sure you are ready to join before clicking!_"
    )
    teaser_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Get My Channel Link(s)", callback_data=f"bc_gl_{session_id}")]
    ])

    success = 0
    failed  = 0

    for i, uid in enumerate(user_ids):
        try:
            if has_opt_msg and opt_msg_chat and opt_msg_id:
                try:
                    await context.bot.copy_message(
                        chat_id=uid,
                        from_chat_id=opt_msg_chat,
                        message_id=opt_msg_id
                    )
                except Exception as e:
                    logger.warning(f"Could not copy optional message to {uid}: {e}")

            await context.bot.send_message(
                chat_id=uid,
                text=teaser_text,
                reply_markup=teaser_markup,
                parse_mode="Markdown"
            )
            success += 1
        except Exception:
            failed += 1

        # ── Live progress — edit the SAME message in-place ───
        if (i + 1) % 5 == 0 or (i + 1) == total:
            pct = int(((i + 1) / total) * 100)
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            try:
                await context.bot.edit_message_text(
                    chat_id=stat_chat,
                    message_id=stat_mid,
                    text=(
                        f"📡 **Broadcasting... {pct}%**\n\n"
                        f"`[{bar}]`\n\n"
                        f"⏳ Progress : **{i + 1} / {total}**\n"
                        f"✅ Sent     : **{success}**\n"
                        f"❌ Failed   : **{failed}**"
                    ),
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    # ── Final result — same message, replaced in-place ───
    back_btn = InlineKeyboardButton("🔙 Back to Admin Settings", callback_data="menu_admin_settings")
    await context.bot.edit_message_text(
        chat_id=stat_chat,
        message_id=stat_mid,
        text=(
            f"📢 **Broadcast Complete!** 📢\n\n"
            f"✅ Teasers sent : **{success}** users\n"
            f"❌ Failed        : **{failed}** users\n"
            f"👥 Total         : **{total}**\n\n"
            f"📺 Channels : {chan_names}\n"
            f"🔗 Users receive links when they click **Get Link**\n"
            f"⏱️ Each link auto-deletes **{expiry_mins} min** after clicking"
        ),
        reply_markup=build_grid_keyboard([], back_button=back_btn),
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────────────────
#  Get Link handler — fires when user clicks the teaser button
# ─────────────────────────────────────────────────────────
async def handle_bc_get_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User clicked 'Get My Channel Link(s)' — send actual links NOW with fresh timer."""
    from handlers.approval import live_timer_update_job
    from handlers.admin_modules import ADMIN_MENTION_LINK

    query = update.callback_query
    await query.answer("⏳ Generating your secure invite link(s)...", show_alert=False)

    session_id = query.data[len("bc_gl_"):]
    sessions   = context.application.bot_data.get("bc_link_sessions", {})
    session    = sessions.get(session_id)

    if not session:
        await query.edit_message_text(
            "❌ **This invite request has expired.**\n\n"
            "Please contact the admin to request a new link.",
            parse_mode="Markdown"
        )
        return

    channel_ids = session["channel_ids"]
    expiry_mins = session.get("expiry_mins", 3)
    all_chans   = db.get_all_premium_channels()
    channels    = [c for c in all_chans if c["channel_id"] in channel_ids]

    if not channels:
        await query.edit_message_text(
            "❌ **Channel(s) not found.** Please contact the admin.",
            parse_mode="Markdown"
        )
        return

    admin_contact = "https://t.me/aLooser"
    uid = query.from_user.id

    # Build the protected invite buttons
    link_buttons = [[InlineKeyboardButton(f"📺 Join {c['title']}", url=c["invite_link"])] for c in channels]
    link_buttons.append([InlineKeyboardButton("👤 Contact Admin 🦋 ༄Nìśẳntℎ༄ 🦋", url=admin_contact)])
    chan_markup = InlineKeyboardMarkup(link_buttons)

    invite_text = (
        "🚨 **SECURE VIP CHANNEL INVITE(S)** 🚨\n\n"
        "Use the buttons below to join your premium channel(s).\n\n"
        f"⏳ **CRITICAL**: Forward-restricted. **Auto-deletes in {expiry_mins} min**. Join immediately!\n\n"
        "{TIMER_PLACEHOLDER}\n\n"
        "💬 If you face any issues, contact Admin directly."
    )
    initial_text = invite_text.replace(
        "{TIMER_PLACEHOLDER}",
        f"⏳ **Auto-Deleting in: {expiry_mins:02d}:00** ⏳"
    )

    protect     = db.get_setting("restrict_link_sharing", "1") == "1"
    auto_delete = db.get_setting("link_auto_delete", "1") == "1"

    try:
        # Delete teaser message so user only has the main invite message
        await query.message.delete()
    except Exception as e:
        logger.warning(f"Failed to delete teaser message: {e}")

    try:
        sent = await context.bot.send_message(
            chat_id=uid,
            text=initial_text,
            reply_markup=chan_markup,
            parse_mode="Markdown",
            protect_content=protect,
            disable_web_page_preview=True
        )

        jq = context.application.job_queue if hasattr(context, 'application') else None
        if jq is None:
            try:
                jq = context.job_queue
            except Exception:
                jq = None

        if auto_delete and jq:
            jq.run_repeating(
                live_timer_update_job,
                interval=5,
                first=5,
                data={
                    "chat_id": uid,
                    "message_id": sent.message_id,
                    "admin_mention": ADMIN_MENTION_LINK,
                    "end_time": time.time() + (expiry_mins * 60),
                    "original_text": invite_text,
                    "reply_markup": chan_markup
                }
            )
        elif auto_delete and not jq:
            logger.error("Auto-delete is enabled but job_queue is unavailable.")
    except Exception as e:
        logger.error(f"Failed to send invite message or schedule timer: {e}")


# ─────────────────────────────────────────────────────────
#  STEP 4 (message path) — Receive broadcast message
# ─────────────────────────────────────────────────────────
async def receive_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles incoming admin message.
    - content_type == 'channel_with_msg' → save msg, edit prompt → show confirm in-place
    - content_type == 'message'          → edit prompt in-place with live progress
    - anything else                      → ignore (admin is in channel-select flow)
    """
    from utils.keyboard_helper import build_grid_keyboard
    ctype = context.user_data.get("bc_content_type")

    # ── Channel-with-message path ───────────────────────
    if ctype == "channel_with_msg":
        # Save message reference for later copy_message (do NOT delete the admin's msg)
        context.user_data["bc_opt_msg_chat_id"] = update.message.chat_id
        context.user_data["bc_opt_msg_id"]       = update.message.message_id

        # Edit the prompt message IN-PLACE to show the confirm/send screen
        prompt_chat = context.user_data.get("prompt_chat_id")
        prompt_mid  = context.user_data.get("prompt_msg_id")
        if prompt_chat and prompt_mid:
            user_ids  = _resolve_user_ids(context)
            channels  = db.get_all_premium_channels()
            sel_ids   = context.user_data.get("bc_selected_channels", [])
            sel_names = [c["title"][:28] for c in channels if c["channel_id"] in sel_ids]
            target    = _resolve_label(context)
            try:
                expiry_mins = int(db.get_setting("link_expiry_minutes", "3"))
            except Exception:
                expiry_mins = 3

            summary = (
                "📤 **Ready to Send — Broadcast Summary**\n\n"
                f"👥 **Target**: {target} (`{len(user_ids)}` users)\n"
                f"📺 **Channels**: {', '.join(sel_names)}\n"
                f"📝 **Custom Message**: ✅ Yes (preview above ↑)\n"
                f"⏱️ **Link expires**: {expiry_mins} min after user clicks (forward-restricted)\n\n"
                "Press **📤 Send Broadcast** to start."
            )
            buttons  = [InlineKeyboardButton("📤 Send Broadcast", callback_data="bc_send_now")]
            back_btn = InlineKeyboardButton("🔙 Cancel", callback_data="menu_admin_settings")
            try:
                await context.bot.edit_message_text(
                    chat_id=prompt_chat, message_id=prompt_mid,
                    text=summary,
                    reply_markup=build_grid_keyboard(buttons, back_button=back_btn),
                    parse_mode="Markdown"
                )
            except Exception:
                pass
        return ADMIN_BROADCAST

    # ── Plain message broadcast path ──────────────────
    if ctype == "message":
        try:
            await update.message.delete()
        except Exception:
            pass

        user_ids    = _resolve_user_ids(context)
        prompt_chat = context.user_data.get("prompt_chat_id")
        prompt_mid  = context.user_data.get("prompt_msg_id")

        if not user_ids:
            back_btn = InlineKeyboardButton("🔙 Back", callback_data="menu_admin_settings")
            if prompt_chat and prompt_mid:
                try:
                    await context.bot.edit_message_text(
                        chat_id=prompt_chat, message_id=prompt_mid,
                        text="⚠️ No matching users found in the database.",
                        reply_markup=build_grid_keyboard([], back_button=back_btn),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
            return ConversationHandler.END

        total = len(user_ids)

        # Replace the prompt message in-place with "Starting"
        if prompt_chat and prompt_mid:
            try:
                await context.bot.edit_message_text(
                    chat_id=prompt_chat, message_id=prompt_mid,
                    text=f"📡 **Broadcast Started**\n\n⏳ Progress: **0 / {total}** sent...",
                    parse_mode="Markdown"
                )
                stat_chat, stat_mid = prompt_chat, prompt_mid
            except Exception:
                fallback = await context.bot.send_message(
                    chat_id=update.message.chat_id,
                    text=f"📡 **Broadcast Started**\n\n⏳ Progress: **0 / {total}** sent...",
                    parse_mode="Markdown"
                )
                stat_chat, stat_mid = fallback.chat_id, fallback.message_id
        else:
            fallback = await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=f"📡 **Broadcast Started**\n\n⏳ Progress: **0 / {total}** sent...",
                parse_mode="Markdown"
            )
            stat_chat, stat_mid = fallback.chat_id, fallback.message_id

        success = 0
        failed  = 0
        for i, uid in enumerate(user_ids):
            try:
                await update.message.copy(chat_id=uid)
                success += 1
            except Exception:
                failed += 1

            if (i + 1) % 5 == 0 or (i + 1) == total:
                pct = int(((i + 1) / total) * 100)
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                try:
                    await context.bot.edit_message_text(
                        chat_id=stat_chat,
                        message_id=stat_mid,
                        text=(
                            f"📡 **Broadcasting... {pct}%**\n\n"
                            f"`[{bar}]`\n\n"
                            f"⏳ Progress : **{i + 1} / {total}**\n"
                            f"✅ Sent     : **{success}**\n"
                            f"❌ Failed   : **{failed}**"
                        ),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

        target_label = _resolve_label(context)
        back_btn = InlineKeyboardButton("🔙 Back to Admin Settings", callback_data="menu_admin_settings")
        await context.bot.edit_message_text(
            chat_id=stat_chat, message_id=stat_mid,
            text=(
                f"📢 **Broadcast Complete!** 📢\n\n"
                f"🎯 Target  : **{target_label}**\n"
                f"✅ Sent    : **{success}**\n"
                f"❌ Failed  : **{failed}**\n"
                f"👥 Total   : **{total}**"
            ),
            reply_markup=build_grid_keyboard([], back_button=back_btn),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # ── Ignore — admin is in channel-select or not yet chosen ──
    return ADMIN_BROADCAST


async def _show_send_confirm_from_msg(message, context: ContextTypes.DEFAULT_TYPE):
    """Show the send-confirm screen sent as a new message (not a callback edit)."""
    from utils.keyboard_helper import build_grid_keyboard

    user_ids  = _resolve_user_ids(context)
    channels  = db.get_all_premium_channels()
    sel_ids   = context.user_data.get("bc_selected_channels", [])
    sel_names = [c["title"][:28] for c in channels if c["channel_id"] in sel_ids]
    target    = _resolve_label(context)

    try:
        expiry_mins = int(db.get_setting("link_expiry_minutes", "3"))
    except Exception:
        expiry_mins = 3

    summary = (
        "📤 **Ready to Send — Broadcast Summary**\n\n"
        f"👥 **Target**: {target} (`{len(user_ids)}` users)\n"
        f"📺 **Channels**: {', '.join(sel_names)}\n"
        f"📝 **Custom Message**: ✅ Yes (preview above)\n"
        f"⏱️ **Link expires in**: {expiry_mins} min (forward-restricted)\n\n"
        "Press **📤 Send Broadcast** to start."
    )
    buttons = [InlineKeyboardButton("📤 Send Broadcast", callback_data="bc_send_now")]
    await message.reply_text(
        summary,
        reply_markup=build_grid_keyboard(buttons,
                                         back_button=InlineKeyboardButton("🔙 Cancel", callback_data="menu_admin_settings")),
        parse_mode="Markdown"
    )


# ─────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────
def _resolve_user_ids(context: ContextTypes.DEFAULT_TYPE) -> list:
    target = context.user_data.get("bc_target", "all")
    if target == "all":
        return db.get_all_unique_user_ids()
    selected_plans = context.user_data.get("bc_selected_plans", [])
    if not selected_plans:
        return db.get_all_unique_user_ids()
    uid_set = set()
    for plan_id in selected_plans:
        for s in db.get_subscriptions_by_plan(plan_id):
            uid_set.add(s["user_id"])
    return list(uid_set)


def _resolve_label(context: ContextTypes.DEFAULT_TYPE) -> str:
    target = context.user_data.get("bc_target", "all")
    if target == "all":
        return "All Users"
    plans = context.user_data.get("bc_selected_plans", [])
    if not plans:
        return "All Premium Users"
    all_plans = db.get_all_plans()
    name_map  = {p["plan_id"]: p["name"].split("\n")[0][:20] for p in all_plans}
    return f"Premium ({', '.join(name_map.get(pid, f'Plan #{pid}') for pid in plans)})"


# ─────────────────────────────────────────────────────────
#  Master callback router for all bc_ callbacks
# ─────────────────────────────────────────────────────────
async def broadcast_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data  = query.data

    if   data == "bc_back_to_start":         return await start_broadcast(update, context)
    elif data == "bc_type_all":              return await bc_type_all(update, context)
    elif data == "bc_type_premium":          return await bc_type_premium(update, context)
    elif data.startswith("bc_plan_"):        return await bc_toggle_plan(update, context)
    elif data == "bc_plans_done":            return await bc_plans_done(update, context)
    elif data == "bc_content_message":       return await bc_content_message(update, context)
    elif data == "bc_content_channel":       return await bc_content_channel(update, context)
    elif data.startswith("bc_chsel_"):       return await bc_toggle_channel(update, context)
    elif data == "bc_chans_done":            return await bc_chans_done(update, context)
    elif data == "bc_opt_add_msg":           return await bc_opt_add_msg(update, context)
    elif data == "bc_opt_skip":              return await bc_opt_skip(update, context)
    elif data == "bc_send_now":              return await bc_send_now(update, context)
    else:                                    return ADMIN_BROADCAST


# ─────────────────────────────────────────────────────────
#  Add-DB conversation (unchanged)
# ─────────────────────────────────────────────────────────
async def start_add_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    back_btn = InlineKeyboardButton("❌ Cancel / Back", callback_data="menu_db_mgr")
    msg = await query.edit_message_text(
        "➕ **Add New PostgreSQL Database Shard** ➕\n\n"
        "Please send the complete database connection string (starting with `postgres://` or `postgresql://`).\n"
        "The bot will validate the connection instantly before adding it to the cluster.\n\n"
        "Type /cancel to abort.",
        reply_markup=build_grid_keyboard([], back_button=back_btn),
        parse_mode="Markdown"
    )
    context.user_data["prompt_chat_id"] = msg.chat_id
    context.user_data["prompt_msg_id"]  = msg.message_id
    return ADMIN_ADD_DB


async def receive_add_db(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    url = update.message.text.strip()
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

    back_btn = InlineKeyboardButton("🔙 Back to Multi-Database Manager", callback_data="menu_db_mgr")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    if not url.startswith("postgres://") and not url.startswith("postgresql://"):
        await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="❌ Invalid URL. Must start with `postgres://` or `postgresql://`.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    status_msg = await context.bot.send_message(
        chat_id=update.message.chat_id,
        text="⏳ Testing database connection and initializing shard pool...",
        parse_mode="Markdown"
    )
    try:
        success = db.add_database(url)
        text = (
            "✅ **Database Shard Successfully Added & Initialized!**\n\n"
            "The database has been attached to the cluster pool for auto-failover and load balancing."
            if success else
            "⚠️ This database URL is already present in the cluster configuration."
        )
        await context.bot.edit_message_text(
            chat_id=status_msg.chat_id, message_id=status_msg.message_id,
            text=text, reply_markup=reply_markup, parse_mode="Markdown"
        )
    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=status_msg.chat_id, message_id=status_msg.message_id,
            text=f"❌ **Database Connection Failed!**\n\nError: `{e}`",
            reply_markup=reply_markup, parse_mode="Markdown"
        )
    return ConversationHandler.END


def get_broadcast_link_handlers() -> list:
    return [
        CallbackQueryHandler(handle_bc_get_link, pattern="^bc_gl_")
    ]

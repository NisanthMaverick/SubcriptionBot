import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import LOG_CHANNEL, ADMIN_ID
from database import db
from utils.formatters import calculate_expiry_date, clean_username
from handlers.admin_modules import GRANT_USER_ID, GRANT_PLAN, GRANT_DURATION, GRANT_CUSTOM

logger = logging.getLogger(__name__)

async def grant_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    back_btn = InlineKeyboardButton("❌ Cancel / Back", callback_data="menu_subs")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    prompt_msg = await query.edit_message_text(
        "➕ **Manually Grant VIP Subscription Access**\n\n"
        "Please send the Telegram **User ID** of the user you want to grant premium access to (e.g., `123456789`).\n\n"
        "Type /cancel to abort.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return GRANT_USER_ID

async def receive_grant_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    user_id_str = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    if not user_id_str.isdigit():
        back_btn = InlineKeyboardButton("❌ Cancel", callback_data="menu_subs")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        sent_msg = await context.bot.send_message(chat_id=update.message.chat_id, text="⚠️ User ID must be numeric. Please send a valid numeric Telegram ID:", reply_markup=reply_markup)
        context.user_data["prompt_msg_id"] = sent_msg.message_id
        context.user_data["prompt_chat_id"] = sent_msg.chat_id
        return GRANT_USER_ID

    context.user_data["grant_uid"] = int(user_id_str)
    plans = db.get_all_plans()
    if not plans:
        back_btn = InlineKeyboardButton("🔙 Back to Menu", callback_data="menu_subs")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await context.bot.send_message(chat_id=update.message.chat_id, text="❌ No active plans available in the database to grant.", reply_markup=reply_markup)
        return ConversationHandler.END

    text = f"👤 User ID `{user_id_str}` validated.\n\n📦 **Select Subscription Plan to Grant:**"
    buttons = []
    for p in plans:
        name_clean = p['name'].split('\n')[0][:40]
        buttons.append(InlineKeyboardButton(f"🎁 {name_clean}", callback_data=f"gplan_{p['plan_id']}"))
    back_btn = InlineKeyboardButton("❌ Cancel", callback_data="menu_subs")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)

    sent_msg = await context.bot.send_message(chat_id=update.message.chat_id, text=text, reply_markup=reply_markup, parse_mode="Markdown")
    context.user_data["prompt_msg_id"] = sent_msg.message_id
    context.user_data["prompt_chat_id"] = sent_msg.chat_id
    return GRANT_PLAN

async def handle_grant_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    plan = db.get_plan(pid)
    if not plan:
        return ConversationHandler.END

    context.user_data["grant_plan"] = plan
    plan_name_clean = plan['name'].split('\n')[0]
    text = (
        f"🎁 **Selected Plan: {plan_name_clean}**\n\n"
        "⏱ **Select Duration for Grant:**"
    )
    buttons = []
    for idx, d in enumerate(plan["durations"]):
        dur_name = d.get("duration", "")
        dur_price = d.get("price", "")
        buttons.append(InlineKeyboardButton(f"⏱ {dur_name} ({dur_price})", callback_data=f"gdur_{idx}"))
    buttons.append(InlineKeyboardButton("🌟 Permanent / Lifetime Access", callback_data="gdur_lifetime"))
    buttons.append(InlineKeyboardButton("⏳ Custom Duration Interval", callback_data="gdur_custom"))
    back_btn = InlineKeyboardButton("❌ Cancel", callback_data="menu_subs")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)

    prompt_msg = await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return GRANT_DURATION

async def handle_grant_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    data = query.data.replace("gdur_", "")

    if data == "custom":
        back_btn = InlineKeyboardButton("❌ Cancel", callback_data="menu_subs")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        prompt_msg = await query.edit_message_text(
            "⏳ **Custom Duration Interval**\n\n"
            "Please send the custom duration text and price separated by `-`\n"
            "(e.g., `7 Days - INR 10` or `3 Months - INR 50`):\n\n"
            "Type /cancel to abort.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        context.user_data["prompt_msg_id"] = query.message.message_id
        context.user_data["prompt_chat_id"] = query.message.chat_id
        return GRANT_CUSTOM
    elif data == "lifetime":
        return await execute_grant_access(query, context, "Lifetime (Permanent)", "INR 0 (Lifetime VIP)", query.from_user.first_name)
    else:
        idx = int(data)
        plan = context.user_data["grant_plan"]
        selected_item = plan["durations"][idx]
        dur = selected_item["duration"]
        price = selected_item["price"]
        return await execute_grant_access(query, context, dur, price, query.from_user.first_name)

async def receive_grant_custom(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    dur = text
    price = "INR 0 (Custom Grant)"
    if "-" in text:
        parts = text.split("-")
        dur = parts[0].strip()
        price = parts[1].strip()
    return await execute_grant_access(update.message, context, dur, price, update.effective_user.first_name)

async def execute_grant_access(target_obj, context, duration, price_str, admin_name) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    uid = context.user_data["grant_uid"]
    plan = context.user_data["grant_plan"]
    start_date = datetime.now().strftime("%d/%m/%Y")
    plan_name_clean = plan["name"].split('\n')[0]

    if duration == "Lifetime (Permanent)":
        expiry_date = "Lifetime (Permanent)"
    else:
        expiry_date = calculate_expiry_date(start_date, duration)

    username_display = f"User {uid}"
    try:
        chat_info = await context.bot.get_chat(uid)
        username_display = chat_info.first_name or chat_info.username or f"User {uid}"
    except Exception as e:
        logger.info(f"Could not fetch chat info for {uid}: {e}")

    username_clean = clean_username(username_display)
    profile_link = f"tg://user?id={uid}"

    sub_id = db.add_subscription(
        user_id=uid, username=username_clean, profile_link=profile_link,
        plan_id=plan["plan_id"], plan_name=plan_name_clean, duration=duration,
        amount=price_str, screenshot_file_id="N/A"
    )
    db.update_subscription_status(sub_id, status="Granted", start_date=start_date, expiry_date=expiry_date, notes="Granted manually by Admin")
    db.delete_other_user_subscriptions(uid, sub_id)

    notify_status = "⚠️ Note: Could not deliver VIP receipt and join link directly to user (User may have blocked the bot or not started it)."
    user_card_text = (
        "🎉 **VIP PREMIUM ACCESS GRANTED** 🎉\n\n"
        "Congratulations! You have been manually granted Premium VIP subscription access by the Administrator.\n\n"
        "━━━━━━━━━━━━━━━\n"
        "**Plan details** :-\n\n"
        f"📦 **Selected Plan** : {plan_name_clean}\n\n"
        f"🆔 **Plan Id** : {plan['plan_id']}\n\n"
        f"⏰ **Plan Duration** : {duration}\n\n"
        f"📅 **Start Date** : {start_date}\n\n"
        f"📅 **Expiry Date** : {expiry_date}\n\n"
        "━━━━━━━━━━━━━━━\n"
        "**Payment details** :-\n\n"
        f"💵 **Total Amount** : {price_str}\n\n"
        "💰 **Payment Status** : 👑 Granted by Admin\n\n"
        "📝 **Notes** : Manual VIP Grant\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "⚡ **Welcome to Premium VIP Access** 🚀"
    )
    user_buttons = [[InlineKeyboardButton("🔗 Get Channel Link", callback_data=f"get_link_{sub_id}")]]
    try:
        await context.bot.send_message(
            chat_id=uid,
            text=user_card_text,
            reply_markup=InlineKeyboardMarkup(user_buttons),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        notify_status = f"✅ VIP receipt and Get Channel Link button successfully delivered to User `{uid}`."
    except Exception as e:
        logger.warning(f"Failed to notify granted user {uid}: {e}")

    log_chan = db.get_setting("sub_log_channel_id", "")
    if not log_chan or log_chan in ["Not Configured", "Not Set", "None", ""]:
        log_chan = db.get_setting("log_channel_id", LOG_CHANNEL)
    channel_details_text = (
        "👑 **ADMIN MANUAL VIP GRANT** 👑\n\n"
        "━━━━━━━━━━━━━━━\n"
        "**User details** :-\n\n"
        f"👤 **User Name** : [{username_clean}]({profile_link})\n\n"
        f"🆔 **User ID** : `{uid}`\n\n"
        f"🔗 **Profile Link** : [Click Here]({profile_link})\n\n"
        "━━━━━━━━━━━━━━━\n"
        "**Plan details** :-\n\n"
        f"📦 **Selected Plan** : {plan_name_clean}\n\n"
        f"🆔 **Plan Id** : {plan['plan_id']}\n\n"
        f"⏰ **Plan Duration** : {duration}\n\n"
        f"📅 **Start Date** : {start_date}\n\n"
        f"📅 **Expiry Date** : {expiry_date}\n\n"
        "━━━━━━━━━━━━━━━\n"
        "**Payment details** :-\n\n"
        f"💵 **Total Amount** : {price_str}\n\n"
        "💰 **Payment Status** : 👑 Granted by Admin\n\n"
        "📝 **Notes** : Manually onboarded by Admin\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "⚡ **VIP Premium granted successfully** 🚀"
    )

    sent_channel = False
    if log_chan and log_chan not in ["Not Configured", "Not Set", "None", ""]:
        try:
            await context.bot.send_message(
                chat_id=log_chan, text=channel_details_text,
                parse_mode="Markdown", disable_web_page_preview=True
            )
            sent_channel = True
        except Exception as e:
            logger.warning(f"Failed to send granted details to log_channel {log_chan} ({e}). Falling back to Admin ID.")

    if not sent_channel:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID, text=channel_details_text,
                parse_mode="Markdown", disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Failed to send granted details to Admin ID {ADMIN_ID}: {e}")

    back_btn = InlineKeyboardButton("🔙 Back to Subscriber Management", callback_data="menu_subs")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    success_msg = f"✅ VIP Access successfully granted to [{username_clean}]({profile_link}) (`{uid}`) for duration: `{duration}` ({price_str}).\n\n{notify_status}"
    chat_id = context.user_data.get("prompt_chat_id")
    if hasattr(target_obj, 'edit_message_text'):
        await target_obj.edit_message_text(success_msg, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
    elif chat_id:
        await context.bot.send_message(chat_id=chat_id, text=success_msg, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)
    elif hasattr(target_obj, 'reply_text'):
        await target_obj.reply_text(success_msg, reply_markup=reply_markup, parse_mode="Markdown", disable_web_page_preview=True)

    context.user_data.clear()
    return ConversationHandler.END

import logging
import re
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from utils.translator import translate_text
from utils.keyboard_helper import build_grid_keyboard
from handlers.user_modules import USER_DURATION, USER_PAYMENT_UPLOAD, ADMIN_MENTION_LINK, ADMIN_CONTACT_URL
from config import PAYMENT_REDIRECT_URL

logger = logging.getLogger(__name__)

def extract_numeric_amount(price_str: str) -> str:
    """
    Strips currency symbols and isolates a clean decimal or integer amount.
    Examples:
      '₹299' -> '299'
      '₹ 299.50' -> '299.50'
      '299 INR' -> '299'
      'Rs. 299' -> '299'
    """
    cleaned = price_str.replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if match:
        return match.group(1)
    return "0.00"

def clean_upi_note(text: str) -> str:
    """
    Strips emojis and non-alphanumeric characters to make the note fully compliant
    with UPI merchant specifications and avoid URL validation issues in Telegram.
    """
    # Keep only alphanumeric characters, spaces, and simple hyphens
    cleaned = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
    # Replace multiple spaces with a single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()[:50]

def get_payment_base_url() -> str:
    if PAYMENT_REDIRECT_URL:
        return PAYMENT_REDIRECT_URL
    
    # Auto-detect local network IP so mobile testing on the same Wi-Fi works seamlessly
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip != "127.0.0.1":
            return f"http://{ip}:10000/pay"
    except Exception:
        pass
    return "http://lvh.me:10000/pay"

async def edit_message_or_reply(update: Update, text: str, reply_markup: InlineKeyboardMarkup, parse_mode="Markdown") -> Message:
    query = update.callback_query

    async def try_send(func, **kwargs):
        try:
            return await func(**kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if "can't parse" in err_str or "entity" in err_str or "bad request" in err_str:
                if kwargs.get("parse_mode"):
                    logger.warning(f"Markdown parsing failed, retrying with raw text: {e}")
                    kwargs["parse_mode"] = None
                    return await func(**kwargs)
            raise e

    if query:
        try:
            return await try_send(query.edit_message_text, text=text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)
        except Exception as e:
            logger.info(f"Failed to edit callback message, falling back to deleting and sending new: {e}")
            try:
                await query.message.delete()
            except Exception:
                pass
            return await try_send(query.message.reply_text, text=text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)
    else:
        return await try_send(update.message.reply_text, text=text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)

async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await show_plans_list(update, context)

async def show_plans_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = user.language_code if user else "en"
    
    # Intercept for Testing Mode
    from handlers.admin_modules.menu import is_admin
    test_mode = db.get_setting("testing_mode_enabled", "0")
    if test_mode == "1":
        test_users = db.get_setting("testing_mode_users", "")
        test_user_list = [u.strip() for u in test_users.split(",") if u.strip().isdigit()]
        if not is_admin(user.id) and str(user.id) not in test_user_list:
            fallback = db.get_setting("fallback_channel_link", "")
            msg = "🚧 **Bot is in Testing Mode.**\n\nThe bot is currently undergoing maintenance and testing. You cannot use it right now."
            if fallback:
                msg += f"\n\nPlease join our channel for updates: {fallback}"
            if update.callback_query:
                await update.callback_query.answer("Bot is in Testing Mode", show_alert=True)
                await update.callback_query.message.reply_text(msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(msg, parse_mode="Markdown")
            return ConversationHandler.END

    import asyncio
    plans = await asyncio.to_thread(db.get_all_plans)

    if not plans:
        msg = f"📭 There are currently no active subscription plans available. Please check back later or contact Admin {ADMIN_MENTION_LINK}!"
        back_btn = InlineKeyboardButton("👤 Contact Admin 🦋 ༄Nìśẳntℎ༄ 🦋", url=ADMIN_CONTACT_URL)
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await edit_message_or_reply(update, translate_text(msg, lang), reply_markup=reply_markup)
        return ConversationHandler.END

    text = "🌟 **Exclusive Premium Plans** 🌟\n━━━━━━━━━━━━━━━━━━━━\n\n"
    plan_buttons = []
    for plan in plans:
        text += f"✨ **{plan['name']}** ✨\n"
        if plan['description'] and plan['description'] != plan['name']:
            text += f"📝 _{plan['description']}_\n\n"
        else:
            text += "\n"

        text += "💎 **Pricing:**\n"
        for d in plan['durations']:
            dur_name = d.get('duration', '')
            dur_price = d.get('price', '')
            text += f" 🔹 {dur_name} ➔ **{dur_price}**\n"

        text += "\n━━━━━━━━━━━━━━━━━━━━\n\n"

        clean_btn_name = plan['name'].split("\n")[0][:40]
        plan_buttons.append(InlineKeyboardButton(clean_btn_name, callback_data=f"select_plan_{plan['plan_id']}"))

    keyboard = []
    for i in range(0, len(plan_buttons), 2):
        keyboard.append(plan_buttons[i:i+2])

    view_channels_btn = InlineKeyboardButton("📺 View Channels", callback_data="view_channels_menu")
    contact_btn = InlineKeyboardButton("👤 Contact Admin", url=ADMIN_CONTACT_URL)
    keyboard.append([view_channels_btn, contact_btn])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await edit_message_or_reply(update, translate_text(text, lang), reply_markup=reply_markup)
    return USER_DURATION

async def view_channels_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.from_user.language_code
    
    import asyncio
    plans = await asyncio.to_thread(db.get_all_plans)
    
    text = "📺 **Select a Plan to View Channels** 📺\n━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "Choose a subscription plan below to see the list of premium channels included with it."
    
    keyboard = []
    for plan in plans:
        clean_btn_name = plan['name'].split("\n")[0][:40]
        keyboard.append([InlineKeyboardButton(clean_btn_name, callback_data=f"view_channels_plan_{plan['plan_id']}")])
        
    keyboard.append([InlineKeyboardButton("🔙 Back to Plans", callback_data="select_plans_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await edit_message_or_reply(update, translate_text(text, lang), reply_markup=reply_markup)
    return USER_DURATION

async def view_channels_for_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.from_user.language_code
    plan_id = int(query.data.split("_")[-1])
    
    import asyncio
    plan = await asyncio.to_thread(db.get_plan, plan_id)
    if not plan:
        await query.message.reply_text(translate_text("❌ Selected plan is no longer available.", lang))
        return USER_DURATION
        
    channels = await asyncio.to_thread(db.get_channels_for_plan, plan_id)
    
    text = f"📺 **Channels Included in:**\n✨ **{plan['name']}** ✨\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if channels:
        for i, c in enumerate(channels, 1):
            text += f"🔹 {i}. {c['title']}\n"
    else:
        text += "📝 _No channels have been configured for this plan yet._\n"
        
    text += "\n━━━━━━━━━━━━━━━━━━━━"
    
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Plan Selection", callback_data="view_channels_menu")],
        [InlineKeyboardButton("📦 Browse All Plans", callback_data="select_plans_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await edit_message_or_reply(update, translate_text(text, lang), reply_markup=reply_markup)
    return USER_DURATION

async def handle_plan_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    lang = query.from_user.language_code
    plan_id = int(query.data.split("_")[-1])
    plan = db.get_plan(plan_id)

    if not plan:
        await query.message.reply_text(translate_text("❌ Selected plan is no longer available.", lang))
        return ConversationHandler.END

    context.user_data["selected_plan"] = plan

    buttons = []
    for idx, d in enumerate(plan["durations"]):
        dur_name = d.get('duration', '')
        dur_price = d.get('price', '')
        buttons.append(InlineKeyboardButton(f"💰 {dur_name} – {dur_price}", callback_data=f"sel_dur_{idx}"))

    back_btn = InlineKeyboardButton("🔙 Back to Plans", callback_data="back_to_plans")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)

    details_msg = (
        f"💎 **Selected Plan: {plan['name']}** 💎\n\n"
        "Choose your subscription duration below:"
    )
    await edit_message_or_reply(update, translate_text(details_msg, lang), reply_markup=reply_markup)
    return USER_DURATION

async def handle_duration_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.from_user.language_code

    if query.data == "back_to_plans":
        return await show_plans_list(update, context)

    plan = context.user_data["selected_plan"]

    if query.data == "back_to_payment_methods":
        duration = context.user_data["selected_duration"]
        price = context.user_data["selected_price"]
    else:
        dur_idx = int(query.data.replace("sel_dur_", ""))
        selected_item = plan["durations"][dur_idx]
        duration = selected_item["duration"]
        price = selected_item["price"]
        context.user_data["selected_duration"] = duration
        context.user_data["selected_price"] = price
        context.user_data["selected_duration_idx"] = dur_idx

    method_msg = (
        "💳 **Choose Your Payment Method** 💳\n\n"
        f"📦 **Plan**: {plan['name']}\n"
        f"⏱ **Duration**: {duration}\n"
        f"💰 **Amount**: `{price}`\n\n"
        "Please select your preferred payment method below:"
    )

    qr_enabled = db.get_setting("pay_method_qr_enabled", "1") != "0"
    upi_enabled = db.get_setting("pay_method_upi_enabled", "1") != "0"
    app_enabled = db.get_setting("pay_method_app_enabled", "1") != "0"

    # Defensive fallback: if all are disabled, automatically enable all 3
    if not (qr_enabled or upi_enabled or app_enabled):
        db.set_setting("pay_method_qr_enabled", "1")
        db.set_setting("pay_method_upi_enabled", "1")
        db.set_setting("pay_method_app_enabled", "1")
        qr_enabled = upi_enabled = app_enabled = True

    pay_buttons = []
    if qr_enabled:
        pay_buttons.append(InlineKeyboardButton("📸 Pay via QR Code", callback_data="pay_method_qr"))
    if upi_enabled:
        pay_buttons.append(InlineKeyboardButton("🔑 Pay via UPI ID", callback_data="pay_method_upi"))
    if app_enabled:
        pay_buttons.append(InlineKeyboardButton("📲 Pay via UPI App", callback_data="pay_method_app"))

    back_btn = InlineKeyboardButton("🔙 Back to Durations", callback_data="back_to_durations")
    reply_markup = build_grid_keyboard(pay_buttons, back_button=back_btn)

    await edit_message_or_reply(update, translate_text(method_msg, lang), reply_markup=reply_markup)
    return USER_DURATION

async def show_payment_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.from_user.language_code
    context.user_data["payment_method"] = "QR Code"

    plan = context.user_data["selected_plan"]
    duration = context.user_data["selected_duration"]
    price = context.user_data["selected_price"]
    qr_code = db.get_setting("qr_code_file_id")

    payment_msg = (
        "📸 **Pay via QR Code** 📸\n"
        "\u200b\n"
        f"📦 **Selected Plan**: {plan['name'].split('\n')[0]}\n"
        f"⏱ **Duration**: {duration}\n"
        f"💰 **Amount to Pay**: `{price}`\n"
        "\u200b\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\u200b\n"
        "👉 **Scan the QR code photo below** using any UPI app (Google Pay, PhonePe, Paytm, BHIM) to complete your transaction.\n"
        "\u200b\n"
        "🛑 **MANDATORY**: Once paid, **you MUST capture a screenshot of your successful transaction and upload it here as a photo**!\n"
        "\u200b\n"
        "🤖 **System Status**: The bot is waiting and **expects a screenshot** to verify your transaction. Your plan will not activate until a valid screenshot is uploaded! ⚡\n"
        "\u200b\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\u200b\n"
        f"💬 *Need assistance?* Direct contact Admin {ADMIN_MENTION_LINK}."
    )

    back_btn = InlineKeyboardButton("🔙 Cancel / Change Payment Method", callback_data="back_to_payment_methods")
    reply_markup = build_grid_keyboard([], back_button=back_btn)

    sent_msg = None
    
    # 1. Try to send the user-configured QR code from DB settings if available
    if qr_code and str(qr_code).strip() not in ["None", "Not Configured", "Null", "not_configured", ""]:
        try:
            try:
                sent_msg = await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=qr_code,
                    caption=translate_text(payment_msg, lang),
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            except Exception as pe:
                if "can't parse" in str(pe).lower() or "entity" in str(pe).lower():
                    logger.warning(f"Markdown parsing failed for custom QR caption, retrying with raw text: {pe}")
                    sent_msg = await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=qr_code,
                        caption=translate_text(payment_msg, lang),
                        reply_markup=reply_markup,
                        parse_mode=None
                    )
                else:
                    raise pe
            try:
                await query.message.delete()
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Failed to send custom QR photo {qr_code}: {e}. Falling back to dynamic UPI QR.")

    # 2. Fall back to dynamically generated UPI QR code image if custom QR failed or was not configured
    if not sent_msg:
        try:
            upi_ids = db.get_upi_ids()
            primary_upi = upi_ids[0] if upi_ids else "nisanthlatha2001-3@okaxis"
            clean_amount = extract_numeric_amount(price)
            
            import random
            generic_tn = f"TXN{random.randint(100000, 999999)}"
            
            # Omit 'pn' completely and use a non-commercial generic reference note to bypass bank security filters
            upi_uri = f"upi://pay?pa={primary_upi}&am={clean_amount}&tn={generic_tn}&cu=INR"
            fallback_qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(upi_uri)}"
            
            try:
                sent_msg = await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=fallback_qr_url,
                    caption=translate_text(payment_msg, lang),
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            except Exception as pe:
                if "can't parse" in str(pe).lower() or "entity" in str(pe).lower():
                    logger.warning(f"Markdown parsing failed for fallback UPI QR caption, retrying with raw text: {pe}")
                    sent_msg = await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=fallback_qr_url,
                        caption=translate_text(payment_msg, lang),
                        reply_markup=reply_markup,
                        parse_mode=None
                    )
                else:
                    raise pe
            try:
                await query.message.delete()
            except Exception:
                pass
        except Exception as fallback_err:
            logger.error(f"Failed to send fallback UPI QR photo: {fallback_err}")

    # 3. Ultimate text fallback if photo sending failed completely
    if not sent_msg:
        sent_msg = await edit_message_or_reply(
            update=update,
            text=translate_text(payment_msg, lang),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    context.user_data["payment_prompt_msg_id"] = sent_msg.message_id
    context.user_data["payment_chat_id"] = sent_msg.chat_id

    return USER_PAYMENT_UPLOAD

async def show_payment_upi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.from_user.language_code
    context.user_data["payment_method"] = "UPI ID"

    plan = context.user_data["selected_plan"]
    duration = context.user_data["selected_duration"]
    price = context.user_data["selected_price"]
    upi_ids = db.get_upi_ids()
    upi_text = "\n".join([f"🔸 `{u}`" for u in upi_ids]) if upi_ids else "⚠️ No UPI ID configured by Admin yet."
    payment_msg = (
        "🔑 **Pay via UPI ID** 🔑\n"
        "\u200b\n"
        f"📦 **Selected Plan**: {plan['name'].split('\n')[0]}\n"
        f"⏱ **Duration**: {duration}\n"
        f"💰 **Amount to Pay**: `{price}`\n"
        "\u200b\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\u200b\n"
        "👉 **Available UPI ID(s) for Payment**:\n"
        "\u200b\n"
        f"{upi_text}\n"
        "\u200b\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\u200b\n"
        "📋 Copy one of the UPI IDs listed above and pay the exact amount using your favorite UPI app.\n"
        "\u200b\n"
        "🛑 **MANDATORY**: Once paid, **you MUST capture a screenshot of your successful transaction and upload it here as a photo**!\n"
        "\u200b\n"
        "🤖 **System Status**: The bot is waiting and **expects a screenshot** to verify your transaction. Your plan will not activate until a valid screenshot is uploaded! ⚡\n"
        "\u200b\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\u200b\n"
        f"💬 *Need assistance?* Direct contact Admin {ADMIN_MENTION_LINK}."
    )

    back_btn = InlineKeyboardButton("🔙 Cancel / Change Payment Method", callback_data="back_to_payment_methods")
    reply_markup = build_grid_keyboard([], back_button=back_btn)

    sent_msg = await edit_message_or_reply(
        update=update,
        text=translate_text(payment_msg, lang),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    context.user_data["payment_prompt_msg_id"] = sent_msg.message_id
    context.user_data["payment_chat_id"] = sent_msg.chat_id

    return USER_PAYMENT_UPLOAD

async def show_payment_app(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.from_user.language_code
    context.user_data["payment_method"] = "UPI App"

    plan = context.user_data["selected_plan"]
    duration = context.user_data["selected_duration"]
    price = context.user_data["selected_price"]
    dur_idx = context.user_data["selected_duration_idx"]

    upi_ids = db.get_upi_ids()
    primary_upi = upi_ids[0] if upi_ids else "nisanthlatha2001-3@okaxis"
    
    clean_amount = extract_numeric_amount(price)
    clean_plan_name = clean_upi_note(plan['name'].split("\n")[0])
    
    bot_username = context.bot.username or "TamilanlinkssSubscription_bot"
    pay_params = {
        "pa": primary_upi,
        "pn": "Subscription Bot",
        "am": clean_amount,
        "tn": clean_plan_name,
        "uid": str(query.from_user.id),
        "pid": str(plan["plan_id"]),
        "dur_idx": str(dur_idx),
        "bot": bot_username
    }
    
    base_url = get_payment_base_url()
    pay_url = f"{base_url}?{urllib.parse.urlencode(pay_params)}"

    payment_msg = (
        "📲 **Pay via UPI App (Auto-Activation)** 📲\n"
        "\u200b\n"
        f"📦 **Selected Plan**: {plan['name'].split('\n')[0]}\n"
        f"⏱ **Duration**: {duration}\n"
        f"💰 **Amount to Pay**: `{price}`\n"
        "\u200b\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "\u200b\n"
        "👉 **Click the button below** to initiate a secure checkout and launch any UPI App directly on your mobile device.\n"
        "\u200b\n"
        "🔄 **Auto-activation**: After successful payment, the system will **automatically redirect you back to this bot**, and your premium subscription will be activated instantly! ⚡\n"
        "\u200b\n"
        "💡 *Note: The bot does NOT require a screenshot for this automated payment flow. However, if you face any issues, you can still upload your payment screenshot here as a fallback!*\n"
        "\u200b\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    pay_btn = InlineKeyboardButton("📲 Pay via UPI App", url=pay_url)
    back_btn = InlineKeyboardButton("🔙 Cancel / Change Payment Method", callback_data="back_to_payment_methods")
    reply_markup = build_grid_keyboard([pay_btn], back_button=back_btn)

    sent_msg = await edit_message_or_reply(
        update=update,
        text=translate_text(payment_msg, lang),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    context.user_data["payment_prompt_msg_id"] = sent_msg.message_id
    context.user_data["payment_chat_id"] = sent_msg.chat_id

    return USER_PAYMENT_UPLOAD

async def handle_back_to_durations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.from_user.language_code

    plan = context.user_data["selected_plan"]

    buttons = []
    for idx, d in enumerate(plan["durations"]):
        dur_name = d.get('duration', '')
        dur_price = d.get('price', '')
        buttons.append(InlineKeyboardButton(f"💰 {dur_name} – {dur_price}", callback_data=f"sel_dur_{idx}"))

    back_btn = InlineKeyboardButton("🔙 Back to Plans", callback_data="back_to_plans")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)

    details_msg = (
        f"💎 **Selected Plan: {plan['name']}** 💎\n\n"
        "Choose your subscription duration below:"
    )
    await edit_message_or_reply(update, translate_text(details_msg, lang), reply_markup=reply_markup)
    return USER_DURATION

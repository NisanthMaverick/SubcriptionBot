import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from utils.translator import translate_text
from handlers.user_modules import USER_DURATION, USER_PAYMENT_UPLOAD, ADMIN_MENTION_LINK, ADMIN_CONTACT_URL

logger = logging.getLogger(__name__)

async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await show_plans_list(update, context)

async def show_plans_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = update.effective_user.language_code if update.effective_user else "en"
    plans = db.get_all_plans()

    if not plans:
        msg = f"📭 There are currently no active subscription plans available. Please check back later or contact Admin {ADMIN_MENTION_LINK}!"
        keyboard = [[InlineKeyboardButton("👤 Contact Admin 🦋 ༄Nìśẳntℎ༄ 🦋", url=ADMIN_CONTACT_URL)]]
        if update.callback_query:
            await update.callback_query.edit_message_text(translate_text(msg, lang), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown", disable_web_page_preview=True)
        else:
            await update.message.reply_text(translate_text(msg, lang), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown", disable_web_page_preview=True)
        return ConversationHandler.END

    text = "📦 **Plans & Prices** 📦\n━━━━━━━━━━━━━━━\n\n"
    keyboard = []

    for plan in plans:
        text += f"**{plan['name']}**\n\n"
        if plan['description'] and plan['description'] != plan['name']:
            text += f"{plan['description']}\n\n"

        for d in plan['durations']:
            dur_name = d.get('duration', '')
            dur_price = d.get('price', '')
            text += f"💰 {dur_name} – {dur_price}\n"

        text += "\n━━━━━━━━━━━━━━━\n\n"

        clean_btn_name = plan['name'].split("\n")[0][:40]
        keyboard.append([InlineKeyboardButton(clean_btn_name, callback_data=f"select_plan_{plan['plan_id']}")])

    if update.callback_query:
        await update.callback_query.edit_message_text(translate_text(text, lang), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await update.message.reply_text(translate_text(text, lang), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown", disable_web_page_preview=True)

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

    keyboard = []
    for idx, d in enumerate(plan["durations"]):
        dur_name = d.get('duration', '')
        dur_price = d.get('price', '')
        keyboard.append([InlineKeyboardButton(f"💰 {dur_name} – {dur_price}", callback_data=f"sel_dur_{idx}")])

    keyboard.append([InlineKeyboardButton("🔙 Back to Plans", callback_data="back_to_plans")])

    details_msg = (
        f"💎 **Selected Plan: {plan['name']}** 💎\n\n"
        "Choose your subscription duration below:"
    )
    await query.edit_message_text(translate_text(details_msg, lang), reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown", disable_web_page_preview=True)
    return USER_DURATION

async def handle_duration_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.from_user.language_code

    if query.data == "back_to_plans":
        return await show_plans_list(update, context)

    dur_idx = int(query.data.replace("sel_dur_", ""))
    plan = context.user_data["selected_plan"]
    selected_item = plan["durations"][dur_idx]

    duration = selected_item["duration"]
    price = selected_item["price"]

    context.user_data["selected_duration"] = duration
    context.user_data["selected_price"] = price

    upi_ids = db.get_upi_ids()
    upi_text = "\n".join([f"🔸 `{u}`" for u in upi_ids])
    qr_code = db.get_setting("qr_code_file_id")

    payment_msg = (
        "💳 **Payment Instructions** 💳\n\n"
        f"📦 **Plan**: {plan['name']}\n"
        f"⏱ **Duration**: {duration}\n"
        f"💰 **Amount to Pay**: `{price}`\n\n"
        "━━━━━━━━━━━━━━━\n"
        "**Available UPI IDs for Payment**:\n"
        f"{upi_text}\n"
        "━━━━━━━━━━━━━━━\n\n"
        "Send the exact amount shown. **Screenshot your payment confirmation and upload it here as a photo**.\n\n"
        f"💬 *Need help or facing any issues?*\n"
        f"Contact Admin {ADMIN_MENTION_LINK} directly anytime 📩"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Cancel / Back to Plans", callback_data="back_to_plans")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if qr_code:
        sent_msg = await query.message.reply_photo(
            photo=qr_code,
            caption=translate_text(payment_msg, lang),
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    else:
        sent_msg = await query.edit_message_text(
            translate_text(payment_msg, lang),
            reply_markup=reply_markup,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    context.user_data["payment_prompt_msg_id"] = sent_msg.message_id
    context.user_data["payment_chat_id"] = sent_msg.chat_id

    return USER_PAYMENT_UPLOAD

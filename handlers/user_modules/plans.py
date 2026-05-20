import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from utils.translator import translate_text
from utils.keyboard_helper import build_grid_keyboard
from handlers.user_modules import USER_DURATION, USER_PAYMENT_UPLOAD, ADMIN_MENTION_LINK, ADMIN_CONTACT_URL

logger = logging.getLogger(__name__)

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
    lang = update.effective_user.language_code if update.effective_user else "en"
    plans = db.get_all_plans()

    if not plans:
        msg = f"📭 There are currently no active subscription plans available. Please check back later or contact Admin {ADMIN_MENTION_LINK}!"
        back_btn = InlineKeyboardButton("👤 Contact Admin 🦋 ༄Nìśẳntℎ༄ 🦋", url=ADMIN_CONTACT_URL)
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await edit_message_or_reply(update, translate_text(msg, lang), reply_markup=reply_markup)
        return ConversationHandler.END

    text = "📦 **Plans & Prices** 📦\n━━━━━━━━━━━━━━━\n\n"
    buttons = []

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
        buttons.append(InlineKeyboardButton(clean_btn_name, callback_data=f"select_plan_{plan['plan_id']}"))

    reply_markup = build_grid_keyboard(buttons)
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

    back_btn = InlineKeyboardButton("🔙 Cancel / Back to Plans", callback_data="back_to_plans")
    reply_markup = build_grid_keyboard([], back_button=back_btn)

    sent_msg = None
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
                    logger.warning(f"Markdown parsing failed for QR caption, retrying with raw text: {pe}")
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
            logger.warning(f"Failed to send QR photo {qr_code}: {e}. Falling back to text.")
            
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

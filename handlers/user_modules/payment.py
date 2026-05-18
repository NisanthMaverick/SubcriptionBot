import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from config import LOG_CHANNEL, ADMIN_ID
from utils.formatters import clean_username
from utils.translator import translate_text
from handlers.user_modules import USER_PAYMENT_UPLOAD, ADMIN_CONTACT_URL
from handlers.user_modules.plans import show_plans_list

logger = logging.getLogger(__name__)

async def handle_payment_upload_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await show_plans_list(update, context)

async def receive_payment_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    lang = user.language_code

    if not update.message.photo:
        await update.message.reply_text(translate_text("⚠️ Please send your payment confirmation screenshot as an image photo.", lang))
        return USER_PAYMENT_UPLOAD

    try:
        await update.message.delete()
    except Exception:
        pass
    if "payment_prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["payment_chat_id"], message_id=context.user_data["payment_prompt_msg_id"])
        except Exception:
            pass

    photo_id = update.message.photo[-1].file_id
    plan = context.user_data["selected_plan"]
    duration = context.user_data["selected_duration"]
    price = context.user_data["selected_price"]

    user_clean_name = clean_username(user.first_name or user.username or "User")
    profile_link = f"https://t.me/{user.username}" if user.username else f"tg://user?id={user.id}"

    sub_id = db.add_subscription(
        user_id=user.id,
        username=user_clean_name,
        profile_link=profile_link,
        plan_id=plan["plan_id"],
        plan_name=plan["name"].split('\n')[0],
        duration=duration,
        amount=price,
        screenshot_file_id=photo_id
    )

    log_chan = db.get_setting("log_channel_id", LOG_CHANNEL)
    review_caption = (
        f"🔔 **New Subscription Verification Request (#{sub_id})** 🔔\n\n"
        f"👤 **User**: [{user_clean_name}]({profile_link}) (`{user.id}`)\n"
        f"📦 **Plan**: {plan['name'].split('\n')[0]} (ID: {plan['plan_id']})\n"
        f"⏱ **Duration**: {duration}\n"
        f"💰 **Amount**: {price}"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{sub_id}"),
         InlineKeyboardButton("❌ Decline", callback_data=f"decline_{sub_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    sent = False
    if log_chan and log_chan not in ["Not Configured", "Not Set", "None", ""]:
        try:
            await context.bot.send_photo(chat_id=log_chan, photo=photo_id, caption=review_caption, reply_markup=reply_markup, parse_mode="Markdown")
            sent = True
        except Exception as e:
            logger.warning(f"Failed to send verification to log_chan {log_chan} ({e}). Falling back to Admin ID {ADMIN_ID}.")

    if not sent:
        try:
            await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=review_caption, reply_markup=reply_markup, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send verification request to Admin ID {ADMIN_ID}: {e}")

    success_msg = (
        "⏳ **Thank you! Your payment screenshot has been submitted.**\n\n"
        "Please wait for Admin approval. Once approved, you will receive your Premium Channel link directly here.\n\n"
        "If your subscription is not verified within 24 hours, please contact Admin via the button below."
    )
    user_keyboard = [[InlineKeyboardButton("👤 Contact Admin 🦋 ༄Nìśẳntℎ༄ 🦋", url=ADMIN_CONTACT_URL)]]
    await context.bot.send_message(
        chat_id=update.message.chat_id,
        text=translate_text(success_msg, lang),
        reply_markup=InlineKeyboardMarkup(user_keyboard),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

    context.user_data.clear()
    return ConversationHandler.END

async def cancel_user_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await update.message.reply_text(translate_text("❌ Action cancelled. Type /plan to subscribe.", user.language_code))
    context.user_data.clear()
    return ConversationHandler.END

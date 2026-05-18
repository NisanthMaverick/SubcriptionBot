import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from handlers.admin_modules import PAY_UPI, PAY_QR, PAY_VALIDITY

logger = logging.getLogger(__name__)

async def show_payment_menu(query, alert_msg: str = ""):
    upi_ids = db.get_upi_ids()
    upi_str = "\n".join([f"{i+1}. `{u}`" for i, u in enumerate(upi_ids)])
    val = db.get_setting("payment_validity", "Pay within 30 minutes")
    qr = "Configured ✅" if db.get_setting("qr_code_file_id") else "Not Configured ❌"
    text = (
        "💳 **Payment Gateway Settings** 💳\n\n"
        f"**Configured UPI IDs (Max 3)**:\n{upi_str}\n\n"
        f"**Validity Window**: {val}\n"
        f"**QR Code Image**: {qr}\n\n"
    )
    if alert_msg:
        text += f"{alert_msg}\n\n"
    text += "Select an action below:"

    keyboard = [
        [InlineKeyboardButton("➕ Add UPI ID (Max 3)", callback_data="add_upi_id"),
         InlineKeyboardButton("🗑️ Reset UPIs", callback_data="reset_upi_ids")],
        [InlineKeyboardButton("🖼️ Add / Update QR Code", callback_data="setup_qr_code"),
         InlineKeyboardButton("⏳ Set Validity Window", callback_data="setup_validity")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="menu_main")]
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def start_add_upi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    upi_ids = db.get_upi_ids()
    if len(upi_ids) >= 3 and upi_ids != ["nisanthlatha2001-3@okaxis"]:
        await query.edit_message_text(
            "⚠️ You have already configured the maximum of 3 UPI IDs. Reset or clear existing ones before adding new IDs.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Payment Settings", callback_data="menu_payment")]])
        )
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton("❌ Cancel / Back", callback_data="menu_payment")]]
    prompt_msg = await query.edit_message_text(
        "➕ **Add New UPI ID (Max 3)**\n\n"
        "Please send the new **UPI ID** (e.g., `nisanthlatha@okbank`).\n\n"
        "Type /cancel to abort.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return PAY_UPI

async def receive_upi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_upi = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    upi_ids = db.get_upi_ids()

    if upi_ids == ["nisanthlatha2001-3@okaxis"]:
        upi_ids = [new_upi]
    elif len(upi_ids) < 3:
        upi_ids.append(new_upi)

    db.save_upi_ids(upi_ids)
    keyboard = [[InlineKeyboardButton("🔙 Back to Payment Settings", callback_data="menu_payment")]]
    await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ UPI ID `{new_upi}` successfully added! ({len(upi_ids)}/3 configured)", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

async def start_setup_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ Cancel / Back", callback_data="menu_payment")]]
    prompt_msg = await query.edit_message_text(
        "🖼️ **Add / Update Payment QR Code**\n\n"
        "Please upload your **Payment QR Code Image** as a photo.\n\n"
        "Type /cancel to abort.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return PAY_QR

async def receive_qr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="menu_payment")]]
        sent_msg = await update.message.reply_text("⚠️ Please send your QR code as a photo image.", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data["prompt_msg_id"] = sent_msg.message_id
        context.user_data["prompt_chat_id"] = sent_msg.chat_id
        return PAY_QR

    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    photo_id = update.message.photo[-1].file_id
    db.set_setting("qr_code_file_id", photo_id)
    keyboard = [[InlineKeyboardButton("🔙 Back to Payment Settings", callback_data="menu_payment")]]
    await context.bot.send_message(chat_id=update.message.chat_id, text="✅ Payment QR Code photo successfully updated!", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data.clear()
    return ConversationHandler.END

async def start_setup_validity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ Cancel / Back", callback_data="menu_payment")]]
    prompt_msg = await query.edit_message_text(
        "⏳ **Set Payment Validity Window**\n\n"
        "Please send the payment validity window text (e.g., `Pay within 30 minutes`).\n\n"
        "Type /cancel to abort.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return PAY_VALIDITY

async def receive_validity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_val = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    db.set_setting("payment_validity", new_val)
    keyboard = [[InlineKeyboardButton("🔙 Back to Payment Settings", callback_data="menu_payment")]]
    await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ Validity window successfully updated to: {new_val}", reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data.clear()
    return ConversationHandler.END

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from config import MAX_PLANS
from database import db
from handlers.admin_modules import ADD_PLAN_NAME, ADD_PLAN_DESC, ADD_PLAN_DURATIONS, ADD_DURATION_INPUT
from handlers.admin_modules.menu import is_admin

logger = logging.getLogger(__name__)

async def start_add_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.message.reply_text("⛔ Access denied.")
        return ConversationHandler.END

    plans = db.get_all_plans()
    if len(plans) >= MAX_PLANS:
        back_btn = InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="menu_plans")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text(f"⚠️ You have already reached the maximum limit of {MAX_PLANS} plans. Delete existing plans before adding new ones.", reply_markup=reply_markup)
        return ConversationHandler.END

    next_id = len(plans) + 1
    existing_ids = {p["plan_id"] for p in plans}
    for i in range(1, MAX_PLANS + 1):
        if i not in existing_ids:
            next_id = i
            break

    context.user_data["new_plan_id"] = next_id
    context.user_data["durations"] = []

    text = (
        f"➕ **Adding Plan #{next_id}**\n\n"
        "Please send the **Plan Name & Title** (e.g., `1️⃣ Series Channel - Premium 📺`).\n\n"
        "Type /cancel to abort."
    )
    back_btn = InlineKeyboardButton("🔙 Cancel / Back", callback_data="cancel_add_plan")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    return ADD_PLAN_NAME

async def receive_plan_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_plan_name"] = update.message.text
    text = (
        "Great! Now send the **Plan Description / Features**\n"
        "(e.g., `Access all exclusive series without interruptions.`).\n\n"
        "Type /cancel to abort."
    )
    await update.message.reply_text(text, parse_mode="Markdown")
    return ADD_PLAN_DESC

async def receive_plan_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_plan_desc"] = update.message.text
    await show_durations_menu(update.message, context)
    return ADD_PLAN_DURATIONS

async def show_durations_menu(target, context: ContextTypes.DEFAULT_TYPE):
    from utils.keyboard_helper import build_grid_keyboard
    plan_id = context.user_data["new_plan_id"]
    name = context.user_data["new_plan_name"]
    desc = context.user_data["new_plan_desc"]
    durations = context.user_data["durations"]

    dur_text = ""
    if durations:
        for d in durations:
            dur_text += f"💰 {d['duration']} – {d['price']}\n"
    else:
        dur_text = "*(No durations added yet)*\n"

    summary = (
        f"📦 **Plan Draft (ID #{plan_id})**:\n\n"
        f"**Title**: {name}\n"
        f"**Description**: {desc}\n\n"
        f"**Configured Durations & Prices**:\n{dur_text}\n"
        "Select an option below to manage durations or save:"
    )

    buttons = [InlineKeyboardButton("➕ Add Duration & Price", callback_data="add_dur_btn")]
    if durations:
        buttons.append(InlineKeyboardButton("✅ Confirm & Save Plan", callback_data="confirm_save_plan"))
    back_btn = InlineKeyboardButton("❌ Cancel / Back to Plans Menu", callback_data="cancel_add_plan")

    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)

    if hasattr(target, 'edit_message_text'):
        await target.edit_message_text(summary, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await target.reply_text(summary, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_durations_menu_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()

    if query.data == "add_dur_btn":
        await query.edit_message_text(
            "⚡ **Add Duration & Price**\n\n"
            "Please send the duration and price separated by `-`\n"
            "(e.g., `1 Month - ₹20` or `2 Months - ₹35`).\n\n"
            "Type /cancel to abort.",
            parse_mode="Markdown"
        )
        return ADD_DURATION_INPUT
    elif query.data == "confirm_save_plan":
        plan_id = context.user_data["new_plan_id"]
        name = context.user_data["new_plan_name"]
        desc = context.user_data["new_plan_desc"]
        durations = context.user_data["durations"]

        amount_range = f"{durations[0]['price']} - {durations[-1]['price']}" if len(durations) > 1 else durations[0]['price']
        db.save_plan(plan_id, name, desc, amount_range, durations)

        back_btn = InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="menu_plans")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text(f"✅ **Plan '{name}' successfully saved with {len(durations)} duration options!**", reply_markup=reply_markup, parse_mode="Markdown")
        context.user_data.clear()
        return ConversationHandler.END
    elif query.data == "cancel_add_plan":
        back_btn = InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="menu_plans")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text("❌ Action cancelled.", reply_markup=reply_markup)
        context.user_data.clear()
        return ConversationHandler.END

async def receive_duration_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if "-" not in text:
        await update.message.reply_text("⚠️ Invalid format. Please make sure to separate duration and price with `-` (e.g., `1 Month - ₹20`).")
        return ADD_DURATION_INPUT

    parts = text.split("-")
    dur = parts[0].strip()
    price = parts[1].strip()

    context.user_data["durations"].append({"duration": dur, "price": price})
    await update.message.reply_text(f"✅ Added: {dur} – {price}")
    await show_durations_menu(update.message, context)
    return ADD_PLAN_DURATIONS

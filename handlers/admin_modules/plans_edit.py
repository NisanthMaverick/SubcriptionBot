import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database import db
from handlers.admin_modules import EDIT_PLAN_TITLE, EDIT_PLAN_DESC, EDIT_PLAN_LINK, ADD_PLAN_DURATIONS
from handlers.admin_modules.plans import show_durations_menu

logger = logging.getLogger(__name__)

async def list_edit_plans(query):
    from utils.keyboard_helper import build_grid_keyboard
    plans = db.get_all_plans()
    if not plans:
        back_btn = InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="menu_plans")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text("📭 No active subscription plans to edit.", reply_markup=reply_markup)
        return
    text = "✏️ **Select Plan to Edit:**"
    buttons = []
    for p in plans:
        name_clean = p['name'].split('\n')[0][:40]
        buttons.append(InlineKeyboardButton(f"✏️ {name_clean}", callback_data=f"edit_plan_{p['plan_id']}"))
    back_btn = InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="menu_plans")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def list_delete_plans(query):
    from utils.keyboard_helper import build_grid_keyboard
    plans = db.get_all_plans()
    if not plans:
        back_btn = InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="menu_plans")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text("📭 No active subscription plans to delete.", reply_markup=reply_markup)
        return
    text = "🗑️ **Select Plan to Delete:**"
    buttons = []
    for p in plans:
        name_clean = p['name'].split('\n')[0][:40]
        buttons.append(InlineKeyboardButton(f"🗑️ {name_clean}", callback_data=f"del_plan_{p['plan_id']}"))
    back_btn = InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="menu_plans")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_edit_plan_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    p = db.get_plan(pid)
    if not p:
        back_btn = InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="menu_plans")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await query.edit_message_text("❌ Plan not found.", reply_markup=reply_markup)
        return

    cur_link = db.get_setting(f"plan_link_{pid}", "Not Configured")
    cur_ext_btns = db.get_setting(f"link_custom_buttons_{pid}", "None")
    plan_title_clean = p['name'].split('\n')[0]
    text = (
        f"✏️ **Editing Plan #{pid}: {plan_title_clean}**\n\n"
        f"**Current Title**: {p['name']}\n"
        f"**Current Description**:\n{p['description']}\n"
        f"**Channel Join Link**: `{cur_link}`\n"
        f"**Extra Link Buttons**: `{cur_ext_btns}`\n\n"
        "What would you like to edit?"
    )
    buttons = [
        InlineKeyboardButton("📝 Edit Title", callback_data=f"ep_title_{pid}"),
        InlineKeyboardButton("📄 Edit Description", callback_data=f"ep_desc_{pid}"),
        InlineKeyboardButton("💰 Reset & Edit Durations", callback_data=f"ep_dur_{pid}"),
        InlineKeyboardButton("🔗 Set Channel Link", callback_data=f"ep_link_{pid}"),
        InlineKeyboardButton("➕ Add Extra Link Button", callback_data=f"ep_extbtn_{pid}"),
        InlineKeyboardButton("🗑️ Reset Extra Buttons", callback_data=f"ep_resext_{pid}")
    ]
    back_btn = InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="list_edit_plans")
    reply_markup = build_grid_keyboard(buttons, back_button=back_btn)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def start_edit_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    context.user_data["edit_pid"] = pid
    back_btn = InlineKeyboardButton("❌ Cancel / Back", callback_data="menu_plans")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await query.edit_message_text(f"📝 **Edit Title for Plan #{pid}**\n\nPlease send the new title/name:\n\nType /cancel to abort.", reply_markup=reply_markup, parse_mode="Markdown")
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return EDIT_PLAN_TITLE

async def receive_edited_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    new_title = update.message.text
    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    pid = context.user_data["edit_pid"]
    p = db.get_plan(pid)
    if p:
        db.save_plan(pid, new_title, p['description'], p['amount'], p['durations'])
        back_btn = InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="menu_plans")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ Title for Plan #{pid} updated successfully!", reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END

async def start_edit_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    context.user_data["edit_pid"] = pid
    back_btn = InlineKeyboardButton("❌ Cancel / Back", callback_data="menu_plans")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await query.edit_message_text(f"📄 **Edit Description for Plan #{pid}**\n\nPlease send the new description text:\n\nType /cancel to abort.", reply_markup=reply_markup, parse_mode="Markdown")
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return EDIT_PLAN_DESC

async def receive_edited_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    new_desc = update.message.text
    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    pid = context.user_data["edit_pid"]
    p = db.get_plan(pid)
    if p:
        db.save_plan(pid, p['name'], new_desc, p['amount'], p['durations'])
        back_btn = InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="menu_plans")
        reply_markup = build_grid_keyboard([], back_button=back_btn)
        await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ Description for Plan #{pid} updated successfully!", reply_markup=reply_markup)
    context.user_data.clear()
    return ConversationHandler.END

async def start_edit_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    context.user_data["edit_pid"] = pid
    cur_link = db.get_setting(f"plan_link_{pid}", "Not Configured")
    back_btn = InlineKeyboardButton("❌ Cancel / Back", callback_data="list_edit_plans")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await query.edit_message_text(
        f"🔗 **Set Channel Join Link for Plan #{pid}**\n\n"
        f"**Current Link**: `{cur_link}`\n\n"
        "Please send the private invite/join link for this plan (e.g., `https://t.me/+xyz123`):\n\n"
        "Type /cancel to abort.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    context.user_data["prompt_msg_id"] = query.message.message_id
    context.user_data["prompt_chat_id"] = query.message.chat_id
    return EDIT_PLAN_LINK

async def receive_edited_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from utils.keyboard_helper import build_grid_keyboard
    new_link = update.message.text.strip()
    try:
        await update.message.delete()
    except Exception:
        pass
    if "prompt_msg_id" in context.user_data:
        try:
            await context.bot.delete_message(chat_id=context.user_data["prompt_chat_id"], message_id=context.user_data["prompt_msg_id"])
        except Exception:
            pass

    pid = context.user_data["edit_pid"]
    db.set_setting(f"plan_link_{pid}", new_link)
    back_btn = InlineKeyboardButton("🔙 Back to Plans Menu", callback_data="list_edit_plans")
    reply_markup = build_grid_keyboard([], back_button=back_btn)
    await context.bot.send_message(chat_id=update.message.chat_id, text=f"✅ Channel join link for Plan #{pid} successfully updated to:\n`{new_link}`", reply_markup=reply_markup, parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

async def start_edit_durations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    pid = int(query.data.split("_")[-1])
    p = db.get_plan(pid)
    if not p:
        return ConversationHandler.END

    context.user_data["new_plan_id"] = pid
    context.user_data["new_plan_name"] = p['name']
    context.user_data["new_plan_desc"] = p['description']
    context.user_data["durations"] = []

    await show_durations_menu(query, context)
    return ADD_PLAN_DURATIONS

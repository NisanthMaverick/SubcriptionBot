from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from utils.translator import translate_text

async def unexpected_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Replies to any unexpected text message outside active conversation flows.
    """
    if not update.message or not update.message.text or update.message.text.startswith("/"):
        return

    lang = update.effective_user.language_code
    guide = "Type /plan to subscribe or /start to begin."
    await update.message.reply_text(translate_text(guide, lang))

def get_common_handlers() -> list:
    return [
        MessageHandler(filters.TEXT & ~filters.COMMAND, unexpected_message_handler)
    ]

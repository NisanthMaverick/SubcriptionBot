import logging
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from telegram import Update
from telegram.ext import Application
from config import BOT_TOKEN
from handlers.admin import get_admin_handlers
from handlers.user import get_user_handlers
from handlers.approval import get_approval_handlers
from handlers.common import get_common_handlers
from jobs.notifications import check_subscription_expiry

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        logger.error("BOT_TOKEN is missing or not configured in .env file!")
        print("❌ ERROR: BOT_TOKEN is missing or not configured in .env file. Please edit .env and restart.")
        sys.exit(1)

    logger.info("Initializing Telegram Subscription Bot...")

    # Build application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register admin handlers first
    for handler in get_admin_handlers():
        application.add_handler(handler)

    # Register user handlers
    for handler in get_user_handlers():
        application.add_handler(handler)

    # Register approval callbacks
    for handler in get_approval_handlers():
        application.add_handler(handler)

    # Register common/fallback handlers last
    for handler in get_common_handlers():
        application.add_handler(handler)

    # Setup JobQueue for automated expiry notifications
    if application.job_queue:
        logger.info("Scheduling automated expiry notification job (runs every hour)...")
        application.job_queue.run_repeating(check_subscription_expiry, interval=3600, first=10)
    else:
        logger.warning("JobQueue is not enabled or available in this environment.")

    logger.info("Bot successfully initialized. Starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

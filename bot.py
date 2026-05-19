import logging
import sys
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from telegram import Update
from telegram.ext import Application, ChatMemberHandler
from config import BOT_TOKEN
from handlers.admin import get_admin_handlers
from handlers.user import get_user_handlers
from handlers.approval import get_approval_handlers
from handlers.common import get_common_handlers
from jobs.notifications import check_subscription_expiry
from jobs.raid_scanner import scan_channels_job, on_chat_member_update

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

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is running!")
        
def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    logger.info(f"Starting dummy HTTP server on port {port} for cloud platform health checks...")
    server.serve_forever()

def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        logger.error("BOT_TOKEN is missing or not configured in .env file!")
        print("❌ ERROR: BOT_TOKEN is missing or not configured in .env file. Please edit .env and restart.")
        sys.exit(1)

    logger.info("Initializing Telegram Subscription Bot...")

    # Start dummy web server for cloud deployment health checks (e.g., Render)
    server_thread = threading.Thread(target=start_dummy_server, daemon=True)
    server_thread.start()

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

    # Register chat member update handler for real-time join scans
    application.add_handler(ChatMemberHandler(on_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    # Setup JobQueue for automated expiry notifications
    if application.job_queue:
        logger.info("Scheduling automated expiry notification job (runs every hour)...")
        application.job_queue.run_repeating(check_subscription_expiry, interval=3600, first=10)
        logger.info("Scheduling automated channel raid scan job checker (runs every 5 minutes)...")
        application.job_queue.run_repeating(scan_channels_job, interval=300, first=30)
    else:
        logger.warning("JobQueue is not enabled or available in this environment.")

    logger.info("Bot successfully initialized. Starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

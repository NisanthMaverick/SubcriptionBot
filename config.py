import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
try:
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    ADMIN_ID = 0

DATABASE_URL = os.getenv("DATABASE_URL", "")
LOG_CHANNEL = os.getenv("LOG_CHANNEL", "")

MAX_PLANS = 10

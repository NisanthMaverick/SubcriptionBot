import logging
from datetime import datetime, timedelta
from database import db
from utils.formatters import duration_to_days, clean_username
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

def check_user_active_sub(user_id: int) -> tuple:
    """
    Checks if a user has any active premium subscription.
    Returns (active_subscription_dict, is_active)
    """
    active_subs = db.get_active_paid_subscriptions()
    now = datetime.now()
    for s in active_subs:
        if s["user_id"] == user_id:
            expiry_str = s.get("expiry_date")
            if expiry_str:
                try:
                    expiry_dt = datetime.strptime(expiry_str, "%d/%m/%Y").replace(hour=23, minute=59, second=59)
                    if expiry_dt >= now:
                        return s, True
                except Exception:
                    pass
    return None, False

def calculate_extended_expiry(old_expiry_str: str, duration_str: str) -> str:
    """
    Parses old expiry date and adds the new plan duration in days.
    """
    try:
        old_expiry = datetime.strptime(old_expiry_str, "%d/%m/%Y")
    except Exception:
        old_expiry = datetime.now()
    
    days_to_add = duration_to_days(duration_str)
    new_expiry = old_expiry + timedelta(days=days_to_add)
    return new_expiry.strftime("%d/%m/%Y")

async def send_user_instructions(bot, user_id: int, plan_id: int, expiry_date_str: str, duration_str: str, plan_name: str) -> None:
    """
    Sends detailed instructions to the subscriber about their active plan, access, and renewal.
    """
    try:
        expiry_dt = datetime.strptime(expiry_date_str, "%d/%m/%Y").replace(hour=23, minute=59, second=59)
    except Exception:
        expiry_dt = datetime.now()

    remaining = expiry_dt - datetime.now()
    remaining_days = max(0, remaining.days)
    remaining_hours = max(0, int(remaining.seconds // 3600))
    
    channels = db.get_channels_for_plan(plan_id)
    channel_links = ""
    if channels:
        channel_links = "\n".join([f"📺 **{c['title']}**: [Join Channel]({c['invite_link']})" for c in channels])
    else:
        plan_link = db.get_setting(f"plan_link_{plan_id}")
        if plan_link:
            channel_links = f"📺 **Premium Channel**: [Join Channel]({plan_link})"
        else:
            channel_links = "📺 **Premium Channel**: (No link configured, contact Admin)"

    instruction_msg = (
        "👑 **Premium Subscription Instructions** 👑\n\n"
        f"📦 **Current Active Plan**: {plan_name}\n"
        f"⏰ **Plan Duration**: {duration_str}\n"
        f"📅 **Updated Expiry**: {expiry_date_str}\n"
        f"⏳ **Remaining Time**: {remaining_days} Days, {remaining_hours} Hours\n\n"
        "━━━━━━━━━━━━━━━\n"
        "🔗 **Your Accessible Channels**:\n"
        f"{channel_links}\n"
        "━━━━━━━━━━━━━━━\n\n"
        "🔄 **Renewal Process**:\n"
        "To renew your subscription early and stack your validity, use the `/plan` command anytime. Select your plan, make the payment, and upload your screenshot. The bot will automatically extend your active subscription without interruption!"
    )
    
    buttons = []
    for c in channels:
        buttons.append([InlineKeyboardButton(f"Join {c['title']}", url=c['invite_link'])])
    
    if not channels:
        plan_link = db.get_setting(f"plan_link_{plan_id}")
        if plan_link:
            buttons.append([InlineKeyboardButton("Join Premium Channel", url=plan_link)])
            
    buttons.append([InlineKeyboardButton("👤 Contact Admin", url="https://t.me/aLooser")])
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=instruction_msg,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Failed to send instructions to user {user_id}: {e}")

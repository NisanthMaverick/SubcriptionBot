import logging
from datetime import datetime
from telegram.ext import ContextTypes
from database import db

logger = logging.getLogger(__name__)

async def check_subscription_expiry(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Scheduled job that runs periodically to check for expiring subscriptions.
    If expiry notifications are enabled by admin, sends reminders continuously
    based on the reminder window and interval hours.
    Also handles marking expired subscriptions.
    """
    enabled = db.get_setting("expiry_notify_enabled", "0")
    if enabled != "1":
        return

    try:
        notify_hours = int(db.get_setting("expiry_notify_hours", "24"))
    except ValueError:
        notify_hours = 24

    try:
        notify_interval = int(db.get_setting("expiry_notify_interval", "10"))
    except ValueError:
        notify_interval = 10

    active_subs = db.get_active_paid_subscriptions()
    now = datetime.now()

    for sub in active_subs:
        expiry_str = sub.get("expiry_date")
        if not expiry_str:
            continue

        try:
            # All dates use DD/MM/YYYY format
            expiry_dt = datetime.strptime(expiry_str, "%d/%m/%Y")
            # Set expiry to end of day 23:59:59
            expiry_dt = expiry_dt.replace(hour=23, minute=59, second=59)
        except Exception as e:
            logger.error(f"Error parsing expiry date for sub {sub['sub_id']}: {e}")
            continue

        remaining = expiry_dt - now
        total_hours_remaining = remaining.total_seconds() / 3600.0

        if total_hours_remaining <= 0:
            # Subscription has expired
            if sub["status"] == "Paid" or sub["status"] == "Granted":
                db.update_subscription_status(sub["sub_id"], status="Expired")
                expired_msg = (
                    "🔴 **Premium Subscription Expired** 🔴\n\n"
                    f"Hello {sub['username']}, your premium subscription for **{sub['plan_name']}** has officially expired.\n\n"
                    "⚡ Type /plan to renew your subscription and regain VIP access instantly!"
                )
                try:
                    await context.bot.send_message(chat_id=sub["user_id"], text=expired_msg, parse_mode="Markdown")
                except Exception as e:
                    logger.error(f"Failed to send expiry notice to user {sub['user_id']}: {e}")
        elif total_hours_remaining <= notify_hours:
            # Approaching expiry - continuous reminder check
            last_notified_str = sub.get("last_notified_at", "")
            should_notify = False

            if not last_notified_str:
                should_notify = True
            else:
                try:
                    last_notified_dt = datetime.strptime(last_notified_str, "%Y-%m-%d %H:%M:%S")
                    hours_since_notify = (now - last_notified_dt).total_seconds() / 3600.0
                    if hours_since_notify >= notify_interval:
                        should_notify = True
                except Exception:
                    should_notify = True

            if should_notify:
                days = int(total_hours_remaining // 24)
                hours = int(total_hours_remaining % 24)
                remaining_str = f"{days}d {hours}h" if days > 0 else f"{hours}h"

                reminder_msg = (
                    "⚠️ **Premium Expiry Reminder** ⚠️\n\n"
                    f"Hello {sub['username']}, your premium subscription for **{sub['plan_name']}** will expire in approximately **{remaining_str}**.\n"
                    f"📅 **Expiry Date**: {sub['expiry_date']} (End of day)\n\n"
                    "⚡ Avoid any service interruption! Type /plan to renew your subscription early."
                )
                try:
                    await context.bot.send_message(chat_id=sub["user_id"], text=reminder_msg, parse_mode="Markdown")
                    db.update_last_notified_at(sub["sub_id"], now.strftime("%Y-%m-%d %H:%M:%S"))
                except Exception as e:
                    logger.error(f"Failed to send reminder notice to user {sub['user_id']}: {e}")

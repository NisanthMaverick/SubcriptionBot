from datetime import datetime, timedelta
import re

def clean_username(name: str) -> str:
    if not name:
        return "User"
    for char in ['_', '*', '[', ']', '`']:
        name = str(name).replace(char, "")
    return name.strip() or "User"

def calculate_expiry_date(start_date_str: str, duration_str: str) -> str:
    """
    Calculates the expiry date based on a start date string (DD/MM/YYYY)
    and a duration string (e.g., '1 month', '3 months', '1 year', '7 days').
    """
    try:
        start_date = datetime.strptime(start_date_str, "%d/%m/%Y")
    except ValueError:
        start_date = datetime.now()

    duration_lower = duration_str.lower().strip()
    days_to_add = 0

    # Extract number if present
    match = re.search(r'(\d+)', duration_lower)
    num = int(match.group(1)) if match else 1

    if 'year' in duration_lower:
        days_to_add = num * 365
    elif 'month' in duration_lower:
        days_to_add = num * 30
    elif 'week' in duration_lower:
        days_to_add = num * 7
    elif 'day' in duration_lower:
        days_to_add = num
    elif 'hour' in duration_lower:
        days_to_add = max(1, num // 24)
    else:
        days_to_add = 30 # default 1 month

    expiry_date = start_date + timedelta(days=days_to_add)
    return expiry_date.strftime("%d/%m/%Y")

def build_premium_user_details(sub: dict) -> str:
    """
    Builds a beautifully spaced, clean Premium User Details card.
    """
    status_emoji = "✅ Active" if sub.get("status") in ["Paid", "Granted"] else f"⚠️ {sub.get('status')}"
    notes = sub.get("notes") or "N/A"
    start_date = sub.get("start_date") or "N/A"
    expiry_date = sub.get("expiry_date") or "N/A"

    template = (
        "💎 **VIP SUBSCRIBER ACCESS CARD** 💎\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👤 **USER INFORMATION**\n"
        f"  • **Name**: {sub.get('username', 'Unknown')}\n"
        f"  • **User ID**: `{sub.get('user_id', '')}`\n"
        f"  • **Profile**: [Open Chat]({sub.get('profile_link', 'https://t.me')})\n\n"
        "📦 **PLAN CONFIGURATION**\n"
        f"  • **Selected Plan**: {sub.get('plan_name', '')}\n"
        f"  • **Plan ID**: `{sub.get('plan_id', '')}`\n"
        f"  • **Duration**: {sub.get('duration', '')}\n\n"
        "📅 **VALIDITY PERIOD**\n"
        f"  • **Start Date**: `{start_date}`\n"
        f"  • **Expiry Date**: `{expiry_date}`\n\n"
        "💵 **PAYMENT SUMMARY**\n"
        f"  • **Total Amount**: `{sub.get('amount', '')}`\n"
        f"  • **Status**: {status_emoji}\n"
        f"  • **Notes**: *{notes}*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ *Manage subscriber invite links below:* 🚀"
    )
    return template

def duration_to_days(duration_str: str) -> int:
    """
    Parses a duration string (e.g. '30 Days', '1 Month', '1 Year') and returns duration in days.
    """
    duration_lower = duration_str.lower().strip()
    match = re.search(r'(\d+)', duration_lower)
    num = int(match.group(1)) if match else 1

    if 'year' in duration_lower:
        return num * 365
    elif 'month' in duration_lower:
        return num * 30
    elif 'week' in duration_lower:
        return num * 7
    elif 'day' in duration_lower:
        return num
    elif 'hour' in duration_lower:
        return max(1, num // 24)
    else:
        return 30


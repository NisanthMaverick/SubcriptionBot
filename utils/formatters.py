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
    Builds the Premium User Details card matching exactly the required template.
    """
    status_emoji = "✅ Paid" if sub.get("status") == "Paid" else ("❌ Pending" if sub.get("status") == "Pending" else f"❌ {sub.get('status')}")
    notes = sub.get("notes") or "N/A"
    start_date = sub.get("start_date") or "N/A"
    expiry_date = sub.get("expiry_date") or "N/A"

    template = (
        "💎 PREMIUM USER DETAILS 💎\n"
        "──────────────────────────\n"
        "User details:\n"
        f"👤 User Name    : {sub.get('username', 'Unknown')}\n"
        f"🆔 User ID      : {sub.get('user_id', '')}\n"
        f"🔗 Profile Link : {sub.get('profile_link', 'N/A')}\n\n"
        "Plan details:\n"
        f"📦 Selected Plan  : {sub.get('plan_name', '')}\n"
        f"🆔 Plan ID        : {sub.get('plan_id', '')}\n"
        f"⏱ Plan Duration  : {sub.get('duration', '')}\n"
        f"📅 Start Date     : {start_date}\n"
        f"📅 Expiry Date    : {expiry_date}\n\n"
        "Payment details:\n"
        f"💰 Total Amount Paid : {sub.get('amount', '')}\n"
        f"💵 Payment Status    : {status_emoji}\n"
        f"📝 Notes             : {notes}\n"
        "──────────────────────────\n"
        "⚡ Premium activated successfully 🚀"
    )
    return template

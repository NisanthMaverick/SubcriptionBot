import logging
import sys
import os
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from telegram import Update
from telegram.ext import Application, ChatMemberHandler, ContextTypes
from config import BOT_TOKEN
from database import db
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
        parsed_url = urllib.parse.urlparse(self.path)
        if parsed_url.path == "/pay":
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            upi_id = query_params.get("pa", [""])[0]
            payee_name = query_params.get("pn", ["Subscription Bot"])[0]
            amount = query_params.get("am", ["0.00"])[0]
            note = query_params.get("tn", ["Subscription Plan"])[0]
            
            uid = query_params.get("uid", [""])[0]
            pid = query_params.get("pid", [""])[0]
            dur_idx = query_params.get("dur_idx", [""])[0]
            bot = query_params.get("bot", ["TamilanlinkssSubscription_bot"])[0]
            
            try:
                display_amount = f"₹ {float(amount):,.2f}"
            except ValueError:
                display_amount = f"₹ {amount}"
                
            tn_formatted = f"Plan {pid} Duration {dur_idx}"
            tn_encoded = urllib.parse.quote(tn_formatted)
            upi_deep_link = f"upi://pay?pa={upi_id}&tn={tn_encoded}&am={amount}&cu=INR"
            tg_deep_link = f"https://t.me/{bot}?start=pay_success_{uid}_{pid}_{dur_idx}"
            tg_cancel_link = f"https://t.me/{bot}?start=pay_cancel_{uid}_{pid}_{dur_idx}"
            
            try:
                delay_sec = int(db.get_setting("upi_redirect_delay", "4"))
            except ValueError:
                delay_sec = 4
            delay_ms = delay_sec * 1000
            status_ms = delay_ms + 500
            
            test_mode = db.get_setting("testing_mode_enabled", "0")
            if test_mode == "1":
                confirm_buttons_html = f"""
            <div class="divider"></div>
            
            <p class="title" style="margin-bottom: 12px;">Confirm Action Below (TEST MODE)</p>
            
            <a class="btn-success" href="{tg_deep_link}" id="successBtn">
                ✅ Confirm Payment Successful
            </a>
            
            <a class="btn-cancel" href="{tg_cancel_link}" id="cancelBtn">
                ❌ Cancel / Payment Failed
            </a>
"""
            else:
                confirm_buttons_html = ""
            
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Secure UPI Payment Checkout</title>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Plus+Jakarta+Sans:wght@400;500;700&display=swap" rel="stylesheet">
    
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }}
        
        body {{
            background: radial-gradient(circle at 50% 50%, #150f33 0%, #06040d 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            color: #ffffff;
            overflow-x: hidden;
            position: relative;
        }}
        
        .blob {{
            position: absolute;
            width: 250px;
            height: 250px;
            background: linear-gradient(135deg, rgba(168, 85, 247, 0.15) 0%, rgba(6, 182, 212, 0.15) 100%);
            border-radius: 50%;
            filter: blur(80px);
            z-index: 0;
            animation: float 12s ease-in-out infinite alternate;
        }}
        .blob-1 {{
            top: 10%;
            left: 10%;
        }}
        .blob-2 {{
            bottom: 10%;
            right: 10%;
            animation-delay: -6s;
        }}
        
        @keyframes float {{
            0% {{ transform: translateY(0px) scale(1); }}
            100% {{ transform: translateY(-40px) scale(1.1); }}
        }}
        
        .container {{
            width: 100%;
            max-width: 440px;
            padding: 24px;
            z-index: 10;
        }}
        
        .checkout-card {{
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(24px);
            -webkit-backdrop-filter: blur(24px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 28px;
            padding: 35px 28px;
            text-align: center;
            box-shadow: 0 30px 60px rgba(0, 0, 0, 0.4);
            position: relative;
            overflow: hidden;
        }}
        
        .checkout-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, #a855f7, #06b6d4);
        }}
        
        .logo-area {{
            margin-bottom: 24px;
            position: relative;
        }}
        
        .shield-icon {{
            width: 72px;
            height: 72px;
            background: linear-gradient(135deg, rgba(168, 85, 247, 0.1) 0%, rgba(6, 182, 212, 0.1) 100%);
            border: 1.5px solid rgba(6, 182, 212, 0.3);
            border-radius: 50%;
            display: inline-flex;
            justify-content: center;
            align-items: center;
            font-size: 32px;
            color: #06b6d4;
            box-shadow: 0 0 25px rgba(6, 182, 212, 0.15);
            animation: pulse-ring 2s infinite;
        }}
        
        @keyframes pulse-ring {{
            0% {{ box-shadow: 0 0 0 0 rgba(6, 182, 212, 0.4); }}
            70% {{ box-shadow: 0 0 0 15px rgba(6, 182, 212, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(6, 182, 212, 0); }}
        }}
        
        .title {{
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: rgba(255, 255, 255, 0.55);
            margin-bottom: 8px;
        }}
        
        .amount-display {{
            font-family: 'Outfit', sans-serif;
            font-size: 42px;
            font-weight: 800;
            color: #ffffff;
            margin-bottom: 24px;
            background: linear-gradient(to right, #ffffff, #e2e8f0);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 4px;
        }}
        
        .divider {{
            height: 1px;
            background: rgba(255, 255, 255, 0.08);
            margin: 20px 0;
            position: relative;
        }}
        
        .info-grid {{
            text-align: left;
            margin-bottom: 12px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        
        .info-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 0;
        }}
        
        .info-label {{
            font-size: 13px;
            color: rgba(255, 255, 255, 0.45);
        }}
        
        .info-val {{
            font-size: 14px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.95);
        }}
        
        .upi-pay-section {{
            margin: 24px 0;
            padding: 18px;
            background: rgba(37, 99, 235, 0.05);
            border: 1px dashed rgba(37, 99, 235, 0.25);
            border-radius: 18px;
            text-align: center;
        }}
        
        .upi-heading {{
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            color: rgba(255, 255, 255, 0.6);
            margin-bottom: 12px;
        }}
        
        .upi-badge-container {{
            background: rgba(37, 99, 235, 0.1);
            border: 1.5px solid rgba(37, 99, 235, 0.35);
            border-radius: 12px;
            padding: 12px 16px;
            display: inline-flex;
            justify-content: center;
            align-items: center;
            gap: 12px;
            cursor: pointer;
            transition: all 0.2s ease-in-out;
            width: 100%;
        }}
        
        .upi-badge-container:hover {{
            background: rgba(37, 99, 235, 0.15);
            border-color: rgba(37, 99, 235, 0.6);
            transform: translateY(-1px);
        }}
        
        .upi-address {{
            font-size: 14px;
            font-family: monospace;
            font-weight: 700;
            color: #3b82f6;
            letter-spacing: 0.5px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        .copy-btn {{
            background: none;
            border: none;
            color: #3b82f6;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }}
        
        .copy-btn:hover {{
            color: #60a5fa;
            transform: scale(1.1);
        }}
        
        .tap-copy-note {{
            font-size: 11px;
            color: rgba(255, 255, 255, 0.4);
            margin-top: 8px;
        }}
        
        .btn-pay {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #a855f7 0%, #06b6d4 100%);
            border: none;
            border-radius: 16px;
            color: #ffffff;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 8px 24px rgba(168, 85, 247, 0.2);
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
            text-decoration: none;
            position: relative;
            overflow: hidden;
        }}
        
        .btn-pay::after {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
            transition: all 0.6s ease;
        }}
        
        .btn-pay:hover {{
            transform: translateY(-2px);
            box-shadow: 0 12px 30px rgba(6, 182, 212, 0.45);
        }}
        
        .btn-pay:hover::after {{
            left: 100%;
        }}
        
        .btn-pay:active {{
            transform: translateY(1px);
        }}
        
        .btn-success {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            border: none;
            border-radius: 14px;
            color: #ffffff;
            font-size: 14px;
            font-weight: 700;
            cursor: pointer;
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.25);
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
            text-decoration: none;
            margin-top: 16px;
        }}
        
        .btn-success:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(16, 185, 129, 0.35);
        }}
        
        .btn-cancel {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            width: 100%;
            padding: 14px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 14px;
            color: rgba(255, 255, 255, 0.8);
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
            text-decoration: none;
            margin-top: 12px;
        }}
        
        .btn-cancel:hover {{
            background: rgba(239, 68, 68, 0.1);
            border-color: rgba(239, 68, 68, 0.4);
            color: #ef4444;
            transform: translateY(-1px);
        }}
        
        .status-msg {{
            margin-top: 20px;
            font-size: 12px;
            color: rgba(255, 255, 255, 0.4);
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 6px;
        }}
        
        .pulse-dot {{
            width: 6px;
            height: 6px;
            background-color: #eab308;
            border-radius: 50%;
            display: inline-block;
            animation: pulse-dot 1.5s infinite;
        }}
        
        @keyframes pulse-dot {{
            0% {{ transform: scale(0.9); opacity: 0.4; }}
            50% {{ transform: scale(1.2); opacity: 1; }}
            100% {{ transform: scale(0.9); opacity: 0.4; }}
        }}
        
        .footer-note {{
            margin-top: 30px;
            font-size: 11px;
            color: rgba(255, 255, 255, 0.3);
            line-height: 1.5;
        }}
        
        .toast {{
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background: rgba(16, 185, 129, 0.95);
            color: #ffffff;
            padding: 12px 24px;
            border-radius: 50px;
            font-size: 13px;
            font-weight: 600;
            box-shadow: 0 10px 25px rgba(16, 185, 129, 0.3);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            z-index: 100;
            opacity: 0;
        }}
        
        .toast.show {{
            transform: translateX(-50%) translateY(0);
            opacity: 1;
        }}
    </style>
</head>
<body>
    <div class="blob blob-1"></div>
    <div class="blob blob-2"></div>
    
    <div class="container">
        <div class="checkout-card">
            <div class="logo-area">
                <div class="shield-icon">🛡️</div>
            </div>
            
            <p class="title">Secure Checkout</p>
            <div class="amount-display">{display_amount}</div>
            
            <div class="divider"></div>
            
            <div class="info-grid">
                <div class="info-row">
                    <span class="info-label">Payee Name</span>
                    <span class="info-val">{payee_name}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Plan / Purpose</span>
                    <span class="info-val">{note}</span>
                </div>
            </div>
            
            <!-- Prominent UPI ID Card with heading and Blue color with perfect gap -->
            <div class="upi-pay-section">
                <p class="upi-heading">PAYMENT UPI ID</p>
                <div class="upi-badge-container" onclick="copyUPI()">
                    <span class="upi-address" id="upiVpa">{upi_id}</span>
                    <span class="copy-btn">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                        </svg>
                    </span>
                </div>
                <p class="tap-copy-note">👆 Tap anywhere on the box to Copy UPI ID</p>
            </div>
            
            <a class="btn-pay" href="{upi_deep_link}" id="payBtn">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="margin-top: -1px;">
                    <rect x="5" y="2" width="14" height="20" rx="2" ry="2"></rect>
                    <line x1="12" y1="18" x2="12.01" y2="18"></line>
                </svg>
                Pay via UPI App
            </a>
            
{confirm_buttons_html}
            
            <div class="status-msg" style="margin-top: 24px;">
                <span class="pulse-dot" id="statusDot"></span>
                <span id="statusText">Redirecting you to UPI app...</span>
            </div>
            
            <div style="background: linear-gradient(135deg, rgba(234, 179, 8, 0.15) 0%, rgba(249, 115, 22, 0.15) 100%); border: 1px solid rgba(234, 179, 8, 0.3); border-radius: 12px; padding: 14px; margin: 20px 0; text-align: left; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);">
                <div style="display: flex; gap: 10px; align-items: flex-start;">
                    <span style="font-size: 20px; line-height: 1;">⚠️</span>
                    <div>
                        <p style="color: #fef08a; font-weight: 700; font-size: 13px; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;">Amount Pre-fill Instruction</p>
                        <p style="color: #f3f4f6; font-size: 12.5px; line-height: 1.5; font-weight: 500;">
                            If your UPI app shows a blank amount field, please enter <strong style="color: #fde047; font-size: 14px; font-weight: 800;">{display_amount}</strong> manually inside the app to complete the payment!
                        </p>
                    </div>
                </div>
            </div>
            
            <p class="footer-note">
                Please complete the transaction inside your bank/payment app. Once done, click one of the confirmation buttons above to complete the process.
            </p>
        </div>
    </div>
    
    <div class="toast" id="toast">Copied UPI ID successfully!</div>
    
    <script>
        function copyUPI() {{
            const copyText = document.getElementById("upiVpa").innerText;
            navigator.clipboard.writeText(copyText).then(() => {{
                const toast = document.getElementById("toast");
                toast.classList.add("show");
                setTimeout(() => {{
                    toast.classList.remove("show");
                }}, 2500);
            }}).catch(err => {{
                console.error("Failed to copy VPA", err);
            }});
        }}
        
        window.addEventListener('DOMContentLoaded', () => {{
            const upiUrl = "{upi_deep_link}";
            
            // Auto-launch UPI App after dynamic delay to allow user to read instructions
            setTimeout(() => {{
                window.location.href = upiUrl;
            }}, {delay_ms});
            
            // Update status message
            setTimeout(() => {{
                document.getElementById("statusText").innerText = "Awaiting transaction confirmation. Please complete the transfer in your UPI app and click one of the buttons above!";
            }}, {status_ms});
        }});
    </script>
</body>
</html>
"""
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        else:
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Bot is running!")

async def keep_db_alive_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pings the database every few minutes to keep serverless connections warm."""
    try:
        db.ping_databases()
    except Exception as e:
        logger.error(f"Keep-alive job failed: {e}")

def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = ThreadingHTTPServer(('0.0.0.0', port), DummyHandler)
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
        logger.info("Scheduling database keep-alive job (runs every 3 minutes)...")
        application.job_queue.run_repeating(keep_db_alive_job, interval=180, first=15)
    else:
        logger.warning("JobQueue is not enabled or available in this environment.")

    logger.info("Bot successfully initialized. Starting polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

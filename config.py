import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# OSINT APIs
OSINT_API_NUMBER_URL = os.getenv("OSINT_API_NUMBER_URL", "https://ft-osint-api.duckdns.org/api/number")
OSINT_API_NUMLEAK_URL = os.getenv("OSINT_API_NUMLEAK_URL", "https://ft-osint-api.duckdns.org/api/numleak")
OSINT_API_KEY = os.getenv("OSINT_API_KEY", "lesbian-hathi")

# Optional API relay/proxy URL (set this if Railway blocks direct API access)
# Example: "https://your-relay.workers.dev/proxy" or "http://your-vps:8080/proxy"
API_RELAY_URL = os.getenv("API_RELAY_URL", "")

# Admin IDs (comma-separated Telegram user IDs)
_admin_str = os.getenv("ADMIN_IDS", "8722759285,7392346621")
ADMIN_IDS = [int(x.strip()) for x in _admin_str.split(",") if x.strip()]

# UPI Payment Details
UPI_ID = os.getenv("UPI_ID", "yourupi@paytm")
UPI_NAME = os.getenv("UPI_NAME", "Your Name")

# Credit Packages
CREDIT_PACKAGES = {
    "daily": {"credits": 10, "price": 10, "label": "1 Day Pack"},
    "weekly": {"credits": 100, "price": 100, "label": "1 Week Pack"},
    "monthly": {"credits": 200, "price": 200, "label": "1 Month Pack"},
}

# Free credits for new users
FREE_CREDITS = 3

# Database - use relative path for Railway compatibility
DB_PATH = os.getenv("DB_PATH", "osint_bot.db")

# Payment QR Code
QR_CODE_PATH = os.getenv("QR_CODE_PATH", "media/qr_code.png")

# Export Image Branding
BRAND_NAME = os.getenv("BRAND_NAME", "HATHI02")
BRAND_TAGLINE = os.getenv("BRAND_TAGLINE", "Phone Number OSINT Report")
LOGO_PATH = os.getenv("LOGO_PATH", "media/logo.png")

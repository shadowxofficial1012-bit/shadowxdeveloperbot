import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "8426678718:AAHmYodZH82VD2DOq60vFwXoJSwfG8eLt2I")

# Admin IDs (comma-separated Telegram user IDs)
_admin_str = os.getenv("ADMIN_IDS", "8722759285,7392346621")
ADMIN_IDS = [int(x.strip()) for x in _admin_str.split(",") if x.strip()]

# UPI Payment Details
UPI_ID = os.getenv("UPI_ID", "yourupi@paytm")
UPI_NAME = os.getenv("UPI_NAME", "Your Name")

# Subscription Packages
SUBSCRIPTION_PACKAGES = {
    "daily": {"duration_hours": 24, "price": 20, "label": "1 Day Pack"},
    "weekly": {"duration_hours": 168, "price": 200, "label": "1 Week Pack"},
    "monthly": {"duration_hours": 720, "price": 400, "label": "1 Month Pack"},
}

# Free trial hours for new users
FREE_TRIAL_HOURS = 0

# Required Channels
REQUIRED_CHANNELS = [
    "@hathixshadow",
    "@suh_gf4u",
]

# Database
DB_PATH = os.getenv("DB_PATH", "osint_bot.db")

# Payment QR Code
QR_CODE_PATH = os.getenv("QR_CODE_PATH", "media/qr_code.png")

# Branding
BRAND_NAME = "HathixShadow"
BRAND_TAGLINE = "OSINT Bot"
LOGO_PATH = os.getenv("LOGO_PATH", "media/logo.png")
DEVELOPER = "Utkarsh"

# === NEW API ENDPOINTS ===
API_IP_INFO = "https://ip-info-api.hcjffjggjf.workers.dev/api/v1/ip"
API_VEHICLE_FULL = "https://full-vehicle-info.vercel.app/"
API_VEHICLE_MPARIVAHAN = "https://m-parivahan-api.onrender.com/api/vehicle"
API_NAME_INFO = "https://name-info-2.vercel.app/info"
API_HOTX = "https://hot-x-api.razaisback509.workers.dev/"
API_AADHAAR_FAMILY = "https://aadhaar-family-xyz.rasiksarkarrasiksarkar.workers.dev/get-family-data"
API_NUMINFO = "https://numinfo-1m.hcjffjggjf.workers.dev/"

# API relay proxy URL
API_RELAY_URL = os.getenv("API_RELAY_URL", "")

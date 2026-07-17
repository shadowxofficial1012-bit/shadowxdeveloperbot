import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN", "8426678718:AAHmYodZH82VD2DOq60vFwXoJSwfG8eLt2I")

# OSINT APIs
OSINT_API_NUMBER_URL = os.getenv("OSINT_API_NUMBER_URL", "https://ft-osint-api.duckdns.org/api/number")
OSINT_API_NUMLEAK_URL = os.getenv("OSINT_API_NUMLEAK_URL", "https://ft-osint-api.duckdns.org/api/numleak")
OSINT_API_NUMTOUPI_URL = os.getenv("OSINT_API_NUMTOUPI_URL", "https://ft-osint-api.duckdns.org/api/numtoupi")
OSINT_API_VEHICLE_URL = os.getenv("OSINT_API_VEHICLE_URL", "https://vh-num.vercel.app/fetch")
OSINT_API_KEY = os.getenv("OSINT_API_KEY", "lesbian-hathi2")

# API relay proxy URL (bypasses Railway network restrictions)
# If empty/unset, the bot calls APIs directly (with fallback).
# Set this to your Cloudflare Worker URL if you need to bypass Railway's network blocks.
API_RELAY_URL = os.getenv("API_RELAY_URL", "")

# Admin IDs (comma-separated Telegram user IDs)
_admin_str = os.getenv("ADMIN_IDS", "8722759285,7392346621")
ADMIN_IDS = [int(x.strip()) for x in _admin_str.split(",") if x.strip()]

# UPI Payment Details
UPI_ID = os.getenv("UPI_ID", "yourupi@paytm")
UPI_NAME = os.getenv("UPI_NAME", "Your Name")

# Subscription Packages (unlimited searches for duration)
SUBSCRIPTION_PACKAGES = {
    "daily": {"duration_hours": 24, "price": 10, "label": "1 Day Pack"},
    "weekly": {"duration_hours": 168, "price": 100, "label": "1 Week Pack"},
    "monthly": {"duration_hours": 720, "price": 200, "label": "1 Month Pack"},
}

# Free trial hours for new users (24 hours of free unlimited searches)
FREE_TRIAL_HOURS = 0

# Required Channels/Groups - users must join before using the bot
REQUIRED_CHANNELS = [
    "@hathixshadow",  # https://t.me/hathixshadow
    "@suh_gf4u",       # https://t.me/suh_gf4u
]

# Database - use relative path for Railway compatibility
DB_PATH = os.getenv("DB_PATH", "osint_bot.db")

# Payment QR Code
QR_CODE_PATH = os.getenv("QR_CODE_PATH", "media/qr_code.png")

# Export Image Branding
BRAND_NAME = os.getenv("BRAND_NAME", "HATHI02")
BRAND_TAGLINE = os.getenv("BRAND_TAGLINE", "Phone Number OSINT Report")
LOGO_PATH = os.getenv("LOGO_PATH", "media/logo.png")

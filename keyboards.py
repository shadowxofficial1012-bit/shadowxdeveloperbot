from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from config import SUBSCRIPTION_PACKAGES, REQUIRED_CHANNELS


def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("🌐 IP Lookup"), KeyboardButton("📱 Num Info"), KeyboardButton("📖 Name Info")],
        [KeyboardButton("🚗 Vehicle Lookup"), KeyboardButton("🔍 M-Parivahan")],
        [KeyboardButton("📞 HotX Lookup"), KeyboardButton("👨‍👩‍👧 Aadhaar Family")],
        [KeyboardButton("💰 Buy Plan"), KeyboardButton("❓ Help"), KeyboardButton("🎁 Redeem Code")],
        [KeyboardButton("🤳 Contact Admin"), KeyboardButton("🔧 Admin Panel")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def admin_keyboard():
    keyboard = [
        [KeyboardButton("👥 Total Users"), KeyboardButton("🔍 Lookup History")],
        [KeyboardButton("✅ Activate Plan"), KeyboardButton("💳 Add Credits")],
        [KeyboardButton("👤 Check User"), KeyboardButton("🎁 Create Code")],
        [KeyboardButton("📋 View All Codes"), KeyboardButton("📢 Broadcast")],
        [KeyboardButton("🏥 API Health"), KeyboardButton("🏠 Main Menu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def buy_plan_keyboard():
    buttons = []
    for key, pkg in SUBSCRIPTION_PACKAGES.items():
        text = f"💰 {pkg['label']} — Unlimited • ₹{pkg['price']}"
        buttons.append([InlineKeyboardButton(text, callback_data=f"buy_{key}")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def confirm_payment_keyboard(package_key: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm Payment", callback_data=f"confirm_{package_key}"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment"),
        ]
    ])


def admin_approve_keyboard(tx_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{tx_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{tx_id}"),
        ]
    ])


def back_button(target: str = "back_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=target)]])


def main_menu_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="back_main")]])


def confirm_ban_keyboard(user_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Ban", callback_data=f"doban_{user_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
        ]
    ])


def pdf_button(service_name: str, query: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Download PDF Report", callback_data=f"pdf_{service_name}_{query}")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="back_main")],
    ])


def history_list_keyboard(lookups: list):
    buttons = []
    for entry in lookups:
        text = f"📱 {entry['username']} - {entry['created_at'][:10]}"
        buttons.append([InlineKeyboardButton(text, callback_data=f"reexport_{entry['id']}")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def reexport_keyboard(lookup_id: int, username: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                f"🖼 Export {username} as Image",
                callback_data=f"reexportimg_{lookup_id}",
            )
        ],
        [
            InlineKeyboardButton("⬅️ Back to History", callback_data="history"),
        ],
    ])


def required_channels_keyboard():
    buttons = []
    for channel in REQUIRED_CHANNELS:
        channel_name = channel.replace("@", "")
        buttons.append([
            InlineKeyboardButton(f"📢 Join @{channel_name}", url=f"https://t.me/{channel_name}")
        ])
    buttons.append([
        InlineKeyboardButton("🔄 I've Joined - Verify", callback_data="verify_channels")
    ])
    return InlineKeyboardMarkup(buttons)


def redeem_code_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ])

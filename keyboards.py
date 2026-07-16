from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from config import SUBSCRIPTION_PACKAGES, REQUIRED_CHANNELS


def main_menu_keyboard():
    """Main menu reply keyboard matching the screenshot design."""
    keyboard = [
        [KeyboardButton("📱 Phone Lookup"), KeyboardButton("💰 Buy Plan"), KeyboardButton("💳 UPI Lookup")],
        [KeyboardButton("🚗 Vehicle Lookup"), KeyboardButton("❓ Help Guide"), KeyboardButton("🎁 Redeem Code")],
        [KeyboardButton("🤳 Contact Admin"), KeyboardButton("🔧 Admin Panel")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def admin_keyboard():
    """Admin panel reply keyboard matching the screenshot design."""
    keyboard = [
        [KeyboardButton("👥 Total Users"), KeyboardButton("🔍 Lookup History")],
        [KeyboardButton("✅ Activate Plan"), KeyboardButton("💳 Add Credits")],
        [KeyboardButton("👤 Check User"), KeyboardButton("🎁 Create Code")],
        [KeyboardButton("📋 View All Codes"), KeyboardButton("📢 Broadcast")],
        [KeyboardButton("🏠 Main Menu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def buy_plan_keyboard():
    """Inline keyboard for subscription packages."""
    buttons = []
    for key, pkg in SUBSCRIPTION_PACKAGES.items():
        text = f"💰 {pkg['label']} — Unlimited • ₹{pkg['price']}"
        buttons.append([InlineKeyboardButton(text, callback_data=f"buy_{key}")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def confirm_payment_keyboard(package_key: str):
    """Inline keyboard to confirm payment after sending screenshot."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirm Payment", callback_data=f"confirm_{package_key}"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment"),
            ]
        ]
    )


def admin_approve_keyboard(tx_id: int):
    """Inline keyboard for admin to approve/reject a transaction."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{tx_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{tx_id}"),
            ]
        ]
    )


def back_button(target: str = "back_main"):
    """Simple back button."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=target)]])


def main_menu_button():
    """Main menu inline button."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="back_main")]])


def confirm_ban_keyboard(user_id: int):
    """Confirm ban user."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Yes, Ban", callback_data=f"doban_{user_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_action"),
            ]
        ]
    )


def export_keyboard(username: str):
    """Inline keyboard for exporting report as image."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🖼 Export as Image",
                    callback_data=f"export_{username}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 Back to Menu",
                    callback_data="back_main",
                )
            ],
        ]
    )


def history_list_keyboard(lookups: list):
    """Inline keyboard showing past lookups for re-export."""
    buttons = []
    for entry in lookups:
        text = f"📱 @{entry['username']} - {entry['created_at'][:10]}"
        buttons.append([InlineKeyboardButton(text, callback_data=f"reexport_{entry['id']}")])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def reexport_keyboard(lookup_id: int, username: str):
    """Inline keyboard for re-exporting a past lookup."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"🖼 Export @{username} as Image",
                    callback_data=f"reexportimg_{lookup_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Back to History",
                    callback_data="history",
                )
            ],
        ]
    )


def required_channels_keyboard():
    """Inline keyboard showing required channels to join with verify button."""
    buttons = []
    for channel in REQUIRED_CHANNELS:
        channel_name = channel.replace("@", "")
        buttons.append([
            InlineKeyboardButton(
                f"📢 Join @{channel_name}",
                url=f"https://t.me/{channel_name}",
            )
        ])
    buttons.append([
        InlineKeyboardButton("🔄 I've Joined - Verify", callback_data="verify_channels")
    ])
    return InlineKeyboardMarkup(buttons)


def redeem_code_keyboard():
    """Keyboard shown when user taps Redeem Code."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ])

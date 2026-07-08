from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from config import CREDIT_PACKAGES


def main_menu_keyboard():
    """Main menu reply keyboard."""
    keyboard = [
        [KeyboardButton("\U0001f50d Instagram Lookup"), KeyboardButton("\U0001f4b0 My Balance")],
        [KeyboardButton("\U0001f4b3 Buy Credits"), KeyboardButton("\U0001f4cb My History")],
        [KeyboardButton("\U0001f4dd Help"), KeyboardButton("\U0001f464 Profile")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def admin_keyboard():
    """Admin panel reply keyboard."""
    keyboard = [
        [KeyboardButton("\U0001f4ca Stats"), KeyboardButton("\U0001f4e6 Pending Payments")],
        [KeyboardButton("\U0001f464 User Lookup"), KeyboardButton("\U0001f4b0 Add Credits")],
        [KeyboardButton("\U0001f6ab Ban User"), KeyboardButton("\U0001f6ab Unban User")],
        [KeyboardButton("\U0001f519 Main Menu")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def buy_credits_keyboard():
    """Inline keyboard for credit packages."""
    buttons = []
    for key, pkg in CREDIT_PACKAGES.items():
        text = f"\U0001f4b0 {pkg['label']} \u2014 {pkg['credits']} credits \u2022 \u20b9{pkg['price']}"
        buttons.append([InlineKeyboardButton(text, callback_data=f"buy_{key}")])
    buttons.append([InlineKeyboardButton("\u21a9\ufe0f Back", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def confirm_payment_keyboard(package_key: str):
    """Inline keyboard to confirm payment after sending screenshot."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("\u2705 Confirm Payment", callback_data=f"confirm_{package_key}"),
                InlineKeyboardButton("\u274c Cancel", callback_data="cancel_payment"),
            ]
        ]
    )


def admin_approve_keyboard(tx_id: int):
    """Inline keyboard for admin to approve/reject a transaction."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("\u2705 Approve", callback_data=f"approve_{tx_id}"),
                InlineKeyboardButton("\u274c Reject", callback_data=f"reject_{tx_id}"),
            ]
        ]
    )


def back_button(target: str = "back_main"):
    """Simple back button."""
    return InlineKeyboardMarkup([[InlineKeyboardButton("\u21a9\ufe0f Back", callback_data=target)]])


def confirm_ban_keyboard(user_id: int):
    """Confirm ban user."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("\u2705 Yes, Ban", callback_data=f"doban_{user_id}"),
                InlineKeyboardButton("\u274c Cancel", callback_data="cancel_action"),
            ]
        ]
    )


def export_keyboard(username: str):
    """Inline keyboard for exporting report as image."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "\U0001f4f7 Export as Image",
                    callback_data=f"export_{username}",
                )
            ],
            [
                InlineKeyboardButton(
                    "\U0001f519 Back to Menu",
                    callback_data="back_main",
                )
            ],
        ]
    )


def history_list_keyboard(lookups: list):
    """Inline keyboard showing past lookups for re-export."""
    buttons = []
    for entry in lookups:
        text = f"\U0001f4f1 @{entry['username']} - {entry['created_at'][:10]}"
        buttons.append([InlineKeyboardButton(text, callback_data=f"reexport_{entry['id']}")])
    buttons.append([InlineKeyboardButton("\u21a9\ufe0f Back", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)


def reexport_keyboard(lookup_id: int, username: str):
    """Inline keyboard for re-exporting a past lookup."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"\U0001f4f7 Export @{username} as Image",
                    callback_data=f"reexportimg_{lookup_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "\u21a9\ufe0f Back to History",
                    callback_data="history",
                )
            ],
        ]
    )

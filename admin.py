import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from keyboards import admin_keyboard, admin_approve_keyboard, confirm_ban_keyboard, back_button
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel entry point."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("\U0001f6ab <b>Access Denied.</b>", parse_mode="HTML")
        return

    text = (
        "\U0001f3f7\ufe0f <b>Admin Panel</b>\n\n"
        "Choose an action \u2193"
    )
    await update.message.reply_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics."""
    if not is_admin(update.effective_user.id):
        return

    stats = db.get_stats()
    text = (
        "\U0001f4ca <b>Bot Statistics</b>\n\n"
        f"\U0001f465 <b>Total Users:</b> {stats['total_users']}\n"
        f"\U0001f50d <b>Total Lookups:</b> {stats['total_lookups']}\n"
        f"\U0001f4b3 <b>Revenue:</b> \u20b9{stats['total_revenue']}\n"
        f"\U0001f4b0 <b>Credits Issued:</b> {stats['total_credits_issued']}\n"
        f"\u23f3 <b>Pending Payments:</b> {stats['pending_transactions']}\n"
    )
    await update.message.reply_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")


async def admin_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending transactions."""
    if not is_admin(update.effective_user.id):
        return

    txs = db.get_pending_transactions()
    if not txs:
        await update.message.reply_text(
            "\u2705 <b>No pending transactions.</b>",
            reply_markup=admin_keyboard(),
            parse_mode="HTML",
        )
        return

    for tx in txs[:5]:
        text = (
            f"\U0001f4e2 <b>Payment #{tx['id']}</b>\n\n"
            f"User: <code>{tx['user_id']}</code>\n"
            f"Package: <b>{tx['package'].title()}</b>\n"
            f"Amount: \u20b9{tx['amount']}\n"
            f"Credits: {tx['credits_added']}\n"
            f"Date: {tx['created_at'][:16]}\n"
        )
        # Send screenshot if available
        if tx.get("screenshot_file_id"):
            try:
                await context.bot.send_photo(
                    update.effective_chat.id,
                    photo=tx["screenshot_file_id"],
                    caption=text,
                    reply_markup=admin_approve_keyboard(tx["id"]),
                    parse_mode="HTML",
                )
                continue
            except Exception:
                pass
        await update.message.reply_text(
            text,
            reply_markup=admin_approve_keyboard(tx["id"]),
            parse_mode="HTML",
        )


async def admin_add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add credits to a user (admin)."""
    if not is_admin(update.effective_user.id):
        return
    context.admin_action = "add_credits"
    await update.message.reply_text(
        "Send: <b>user_id amount</b>\nExample: <code>123456789 10</code>",
        reply_markup=back_button("admin_cancel"),
        parse_mode="HTML",
    )


async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user."""
    if not is_admin(update.effective_user.id):
        return
    context.admin_action = "ban_user"
    await update.message.reply_text(
        "Send the <b>user_id</b> to ban:",
        reply_markup=back_button("admin_cancel"),
        parse_mode="HTML",
    )


async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user."""
    if not is_admin(update.effective_user.id):
        return
    context.admin_action = "unban_user"
    await update.message.reply_text(
        "Send the <b>user_id</b> to unban:",
        reply_markup=back_button("admin_cancel"),
        parse_mode="HTML",
    )


async def admin_user_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Look up a user by ID."""
    if not is_admin(update.effective_user.id):
        return
    context.admin_action = "user_lookup"
    await update.message.reply_text(
        "Send a <b>user_id</b> to look up:",
        reply_markup=back_button("admin_cancel"),
        parse_mode="HTML",
    )


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages when admin is in an action state."""
    if not is_admin(update.effective_user.id):
        return False

    action = getattr(context, "admin_action", None)
    if not action:
        return False

    text = update.message.text.strip()

    if text in ("\U0001f519 Main Menu", "\u21a9\ufe0f Back"):
        context.admin_action = None
        await update.message.reply_text(
            "\U0001f3f7\ufe0f <b>Admin Panel</b>", reply_markup=admin_keyboard(), parse_mode="HTML"
        )
        return True

    if action == "add_credits":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("\u274c Format: <code>user_id amount</code>", parse_mode="HTML")
            return True
        try:
            uid = int(parts[0])
            amount = int(parts[1])
        except ValueError:
            await update.message.reply_text("\u274c Invalid numbers.", parse_mode="HTML")
            return True

        db.add_credits(uid, amount)
        await update.message.reply_text(
            f"\u2705 Added <b>{amount}</b> credits to user <code>{uid}</code>.\n"
            f"New balance: {db.get_credits(uid)}",
            reply_markup=admin_keyboard(),
            parse_mode="HTML",
        )
        context.admin_action = None
        return True

    if action == "ban_user":
        try:
            uid = int(text)
        except ValueError:
            await update.message.reply_text("\u274c Invalid user_id.", parse_mode="HTML")
            return True
        db.ban_user(uid)
        await update.message.reply_text(
            f"\U0001f6ab User <code>{uid}</code> has been banned.",
            reply_markup=admin_keyboard(),
            parse_mode="HTML",
        )
        context.admin_action = None
        return True

    if action == "unban_user":
        try:
            uid = int(text)
        except ValueError:
            await update.message.reply_text("\u274c Invalid user_id.", parse_mode="HTML")
            return True
        db.unban_user(uid)
        await update.message.reply_text(
            f"\u2705 User <code>{uid}</code> has been unbanned.",
            reply_markup=admin_keyboard(),
            parse_mode="HTML",
        )
        context.admin_action = None
        return True

    if action == "user_lookup":
        try:
            uid = int(text)
        except ValueError:
            await update.message.reply_text("\u274c Invalid user_id.", parse_mode="HTML")
            return True

        db_user = db.get_or_create_user(uid)
        if not db_user:
            await update.message.reply_text("\u274c User not found.", reply_markup=admin_keyboard())
            context.admin_action = None
            return True

        status = "\U0001f6ab Banned" if db_user["is_banned"] else "\u2705 Active"
        text_msg = (
            f"\U0001f464 <b>User Info</b>\n\n"
            f"<b>User ID:</b> <code>{db_user['user_id']}</code>\n"
            f"<b>Username:</b> @{db_user['username'] or 'N/A'}\n"
            f"<b>Name:</b> {db_user['first_name'] or 'N/A'}\n"
            f"<b>Credits:</b> {db_user['credits']}\n"
            f"<b>Lookups:</b> {db_user['total_lookups']}\n"
            f"<b>Status:</b> {status}\n"
            f"<b>Joined:</b> {db_user['created_at'][:10]}\n"
            f"<b>Last Active:</b> {db_user['last_active'][:16]}"
        )
        await update.message.reply_text(text_msg, reply_markup=admin_keyboard(), parse_mode="HTML")
        context.admin_action = None
        return True

    return False

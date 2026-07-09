import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from keyboards import admin_keyboard, admin_approve_keyboard
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel entry point."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("\U0001f6ab <b>Access Denied.</b>", parse_mode="HTML")
        return

    stats = db.get_stats()
    text = (
        f"\U0001f3f7\ufe0f <b>Admin Panel</b>\n\n"
        f"\U0001f465 <b>Users:</b> {stats['total_users']} | "
        f"\U0001f50d <b>Lookups:</b> {stats['total_lookups']}\n"
        f"\U0001f4b3 <b>Revenue:</b> \u20b9{stats['total_revenue']} | "
        f"\u23f3 <b>Pending:</b> {stats['pending_transactions']}\n\n"
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
            reply_markup=admin_keyboard(), parse_mode="HTML",
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
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_set_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set exact credits for a user."""
    if not is_admin(update.effective_user.id):
        return
    context.admin_action = "set_credits"
    await update.message.reply_text(
        "Send: <b>user_id amount</b>\nExample: <code>123456789 50</code>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_reset_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset user credits to 0."""
    if not is_admin(update.effective_user.id):
        return
    context.admin_action = "reset_credits"
    await update.message.reply_text(
        "Send the <b>user_id</b> to reset credits to 0:",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user."""
    if not is_admin(update.effective_user.id):
        return
    context.admin_action = "ban_user"
    await update.message.reply_text(
        "Send the <b>user_id</b> to ban:",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user."""
    if not is_admin(update.effective_user.id):
        return
    context.admin_action = "unban_user"
    await update.message.reply_text(
        "Send the <b>user_id</b> to unban:",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_user_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Look up a user by ID."""
    if not is_admin(update.effective_user.id):
        return
    context.admin_action = "user_lookup"
    await update.message.reply_text(
        "Send a <b>user_id</b> to look up:",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all users with pagination."""
    if not is_admin(update.effective_user.id):
        return

    users = db.get_all_users()
    if not users:
        await update.message.reply_text(
            "\U0001f465 <b>No users found.</b>",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )
        return

    text = f"\U0001f465 <b>All Users ({len(users)})</b>\n\n"
    for i, u in enumerate(users[:20], 1):
        status = "\U0001f6ab" if u.get("is_banned") else "\u2705"
        username = f"@{u['username']}" if u.get("username") else "N/A"
        text += (
            f"{status} <code>{u['user_id']}</code> | {username}\n"
            f"   \U0001f4b0 {u['credits']} credits | \U0001f50d {u.get('total_lookups', 0)} lookups\n"
        )
    if len(users) > 20:
        text += f"\n... and {len(users) - 20} more users"

    await update.message.reply_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")


async def admin_lookup_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent lookup logs."""
    if not is_admin(update.effective_user.id):
        return

    logs = db.get_recent_lookups(limit=15)
    if not logs:
        await update.message.reply_text(
            "\U0001f50d <b>No lookup logs found.</b>",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )
        return

    text = "\U0001f50d <b>Recent Lookup Logs</b>\n\n"
    for log in logs:
        status = "\u2705" if log.get("success") else "\u274c"
        text += f"{status} <code>{log.get('user_id', 'N/A')}</code> | {log.get('username', 'N/A')} | {log.get('created_at', '')[:16]}\n"

    await update.message.reply_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast a message to all users."""
    if not is_admin(update.effective_user.id):
        return
    context.admin_action = "broadcast_confirm"
    await update.message.reply_text(
        "\U0001f4e2 <b>Broadcast Message</b>\n\n"
        "Type the message to send to ALL users:",
        reply_markup=admin_keyboard(),
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
            await update.message.reply_text("\u274c Format: <code>user_id amount</code>", reply_markup=admin_keyboard(), parse_mode="HTML")
            return True
        try:
            uid = int(parts[0])
            amount = int(parts[1])
        except ValueError:
            await update.message.reply_text("\u274c Invalid numbers.", reply_markup=admin_keyboard(), parse_mode="HTML")
            return True

        db.add_credits(uid, amount)
        await update.message.reply_text(
            f"\u2705 Added <b>{amount}</b> credits to user <code>{uid}</code>.\n"
            f"New balance: {db.get_credits(uid)}",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )
        context.admin_action = None
        return True

    if action == "set_credits":
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("\u274c Format: <code>user_id amount</code>", reply_markup=admin_keyboard(), parse_mode="HTML")
            return True
        try:
            uid = int(parts[0])
            amount = int(parts[1])
        except ValueError:
            await update.message.reply_text("\u274c Invalid numbers.", reply_markup=admin_keyboard(), parse_mode="HTML")
            return True

        db.set_credits(uid, amount)
        await update.message.reply_text(
            f"\u2705 Set credits for user <code>{uid}</code> to <b>{amount}</b>.",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )
        context.admin_action = None
        return True

    if action == "reset_credits":
        try:
            uid = int(text)
        except ValueError:
            await update.message.reply_text("\u274c Invalid user_id.", reply_markup=admin_keyboard(), parse_mode="HTML")
            return True
        db.set_credits(uid, 0)
        await update.message.reply_text(
            f"\u2705 Reset credits for user <code>{uid}</code> to 0.",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )
        context.admin_action = None
        return True

    if action == "ban_user":
        try:
            uid = int(text)
        except ValueError:
            await update.message.reply_text("\u274c Invalid user_id.", reply_markup=admin_keyboard(), parse_mode="HTML")
            return True
        db.ban_user(uid)
        await update.message.reply_text(
            f"\U0001f6ab User <code>{uid}</code> has been banned.",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )
        context.admin_action = None
        return True

    if action == "unban_user":
        try:
            uid = int(text)
        except ValueError:
            await update.message.reply_text("\u274c Invalid user_id.", reply_markup=admin_keyboard(), parse_mode="HTML")
            return True
        db.unban_user(uid)
        await update.message.reply_text(
            f"\u2705 User <code>{uid}</code> has been unbanned.",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )
        context.admin_action = None
        return True

    if action == "user_lookup":
        try:
            uid = int(text)
        except ValueError:
            await update.message.reply_text("\u274c Invalid user_id.", reply_markup=admin_keyboard(), parse_mode="HTML")
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

    if action == "broadcast":
        if text.upper() != "YES":
            await update.message.reply_text(
                "\u274c Broadcast cancelled.",
                reply_markup=admin_keyboard(), parse_mode="HTML",
            )
            context.admin_action = None
            return True

        # Get the broadcast message from context
        broadcast_msg = getattr(context, "broadcast_message", None)
        if not broadcast_msg:
            await update.message.reply_text(
                "\u274c No broadcast message found.",
                reply_markup=admin_keyboard(), parse_mode="HTML",
            )
            context.admin_action = None
            return True

        users = db.get_all_users()
        sent = 0
        failed = 0
        for u in users:
            try:
                await context.bot.send_message(
                    u["user_id"], broadcast_msg, parse_mode="HTML"
                )
                sent += 1
            except Exception:
                failed += 1

        await update.message.reply_text(
            f"\U0001f4e2 <b>Broadcast Complete</b>\n\n"
            f"\u2705 Sent: {sent}\n"
            f"\u274c Failed: {failed}\n"
            f"\U0001f465 Total: {len(users)}",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )
        context.admin_action = None
        context.broadcast_message = None
        return True

    if action == "broadcast_confirm":
        context.broadcast_message = text
        context.admin_action = "broadcast"
        await update.message.reply_text(
            f"\U0001f4e2 <b>Broadcast Preview:</b>\n\n"
            f"{text}\n\n"
            f"\u26a0\ufe0f This will be sent to <b>{db.get_user_count()}</b> users.\n"
            f"Type <b>YES</b> to confirm or <b>CANCEL</b> to abort.",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )
        return True

    return False

import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from keyboards import admin_keyboard, admin_approve_keyboard, main_menu_keyboard
from config import ADMIN_IDS

logger = logging.getLogger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel entry point."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 <b>Access Denied.</b>", parse_mode="HTML")
        return

    stats = db.get_stats()
    code_stats = db.get_redeem_code_stats()
    text = (
        f"🔧 <b>Admin Panel</b>\n\n"
        f"👥 <b>Users:</b> {stats['total_users']} | "
        f"🔍 <b>Lookups:</b> {stats['total_lookups']}\n"
        f"💰 <b>Revenue:</b> ₹{stats['total_revenue']} | "
        f"⏳ <b>Pending:</b> {stats['pending_transactions']}\n"
        f"🎁 <b>Codes:</b> {code_stats['unused']} unused / {code_stats['total']} total\n\n"
        "Choose an action 👇"
    )
    await update.message.reply_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")


async def admin_activate_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ✅ Activate Plan button."""
    if not is_admin(update.effective_user.id):
        return
    context.user_data["admin_action"] = "activate_plan"
    await update.message.reply_text(
        "✅ <b>Activate Plan</b>\n\n"
        "Send: <b>user_id hours</b>\n"
        "Example: <code>123456789 24</code>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 💳 Add Credits button."""
    if not is_admin(update.effective_user.id):
        return
    context.user_data["admin_action"] = "add_credits"
    await update.message.reply_text(
        "💳 <b>Add Credits</b>\n\n"
        "Send: <b>user_id hours</b>\n"
        "Example: <code>123456789 24</code>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_check_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 👤 Check User button."""
    if not is_admin(update.effective_user.id):
        return
    context.user_data["admin_action"] = "check_user"
    await update.message.reply_text(
        "👤 <b>Check User</b>\n\n"
        "Send a <b>user_id</b> to look up:",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_create_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 🎁 Create Code button."""
    if not is_admin(update.effective_user.id):
        return
    context.user_data["admin_action"] = "create_code"
    await update.message.reply_text(
        "🎁 <b>Create Redeem Code</b>\n\n"
        "Send: <b>count hours</b>\n"
        "Example: <code>5 24</code> (creates 5 codes, each 24h)\n\n"
        "Or just send <b>hours</b> for a single code.\n"
        "Example: <code>24</code>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def admin_view_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 📋 View All Codes button."""
    if not is_admin(update.effective_user.id):
        return

    stats = db.get_redeem_code_stats()
    codes = db.get_all_redeem_codes(limit=20)

    if not codes:
        await update.message.reply_text(
            "📋 <b>No redeem codes found.</b>\n\n"
            "Use '🎁 Create Code' to generate codes.",
            reply_markup=admin_keyboard(),
            parse_mode="HTML",
        )
        return

    text = (
        f"📋 <b>Redeem Codes</b>\n\n"
        f"📊 Total: {stats['total']} | ✅ Used: {stats['used']} | ⏳ Unused: {stats['unused']}\n\n"
    )

    for code in codes[:15]:
        status = "✅" if code["is_used"] else "⏳"
        used_by = f" → User {code['used_by']}" if code["is_used"] else ""
        text += (
            f"{status} <code>{code['code']}</code> | "
            f"{code['hours']}h{used_by}\n"
        )

    if len(codes) > 15:
        text += f"\n... and {len(codes) - 15} more codes"

    await update.message.reply_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages when admin is in an action state."""
    if not is_admin(update.effective_user.id):
        return False

    action = context.user_data.get("admin_action")
    if not action:
        return False

    text = update.message.text.strip()

    # Back to admin panel
    if text in ("🏠 Main Menu", "⬅️ Back"):
        context.user_data["admin_action"] = None
        await update.message.reply_text(
            "🔧 <b>Admin Panel</b>", reply_markup=admin_keyboard(), parse_mode="HTML"
        )
        return True

    # Activate Plan / Add Credits (same logic)
    if action in ("activate_plan", "add_credits"):
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ Format: <code>user_id hours</code>\nExample: <code>123456789 24</code>",
                reply_markup=admin_keyboard(), parse_mode="HTML"
            )
            return True
        try:
            uid = int(parts[0])
            hours = int(parts[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid numbers.", reply_markup=admin_keyboard(), parse_mode="HTML")
            return True

        expiry = db.set_subscription(uid, hours)
        try:
            exp_dt = datetime.fromisoformat(expiry)
            msg = f"✅ Added <b>{hours}h</b> subscription to user <code>{uid}</code>.\nExpires: {exp_dt.strftime('%d %b %Y, %I:%M %p')}"
        except:
            msg = f"✅ Added <b>{hours}h</b> subscription to user <code>{uid}</code>."
        await update.message.reply_text(msg, reply_markup=admin_keyboard(), parse_mode="HTML")
        context.user_data["admin_action"] = None
        return True

    # Check User
    if action == "check_user":
        try:
            uid = int(text)
        except ValueError:
            await update.message.reply_text("❌ Invalid user_id.", reply_markup=admin_keyboard(), parse_mode="HTML")
            return True

        db_user = db.get_or_create_user(uid)
        if not db_user:
            await update.message.reply_text("❌ User not found.", reply_markup=admin_keyboard())
            context.user_data["admin_action"] = None
            return True

        status = "🚫 Banned" if db_user["is_banned"] else "✅ Active"
        sub_status = "✅ Active" if db.has_active_subscription(uid) else "⚠️ Expired/None"
        sub_expiry = db.get_subscription_expiry(uid) or "N/A"
        text_msg = (
            f"👤 <b>User Info</b>\n\n"
            f"<b>User ID:</b> <code>{db_user['user_id']}</code>\n"
            f"<b>Username:</b> @{db_user['username'] or 'N/A'}\n"
            f"<b>Name:</b> {db_user['first_name'] or 'N/A'}\n"
            f"<b>Subscription:</b> {sub_status}\n"
            f"<b>Expires:</b> {sub_expiry[:16] if sub_expiry != 'N/A' else 'N/A'}\n"
            f"<b>Lookups:</b> {db_user['total_lookups']}\n"
            f"<b>Joined:</b> {db_user['created_at'][:10]}\n"
            f"<b>Last Active:</b> {db_user['last_active'][:16]}"
        )
        await update.message.reply_text(text_msg, reply_markup=admin_keyboard(), parse_mode="HTML")
        context.user_data["admin_action"] = None
        return True

    # Create Code
    if action == "create_code":
        parts = text.split()
        admin_id = update.effective_user.id

        if len(parts) == 1:
            # Single code: just hours
            try:
                hours = int(parts[0])
            except ValueError:
                await update.message.reply_text("❌ Invalid hours.", reply_markup=admin_keyboard(), parse_mode="HTML")
                return True
            code = db.generate_redeem_code(hours, admin_id)
            await update.message.reply_text(
                f"🎁 <b>Code Created!</b>\n\n"
                f"Code: <code>{code}</code>\n"
                f"Hours: {hours}\n\n"
                f"Share this code with the user.",
                reply_markup=admin_keyboard(), parse_mode="HTML"
            )
            context.user_data["admin_action"] = None
            return True

        elif len(parts) == 2:
            # Bulk: count hours
            try:
                count = int(parts[0])
                hours = int(parts[1])
            except ValueError:
                await update.message.reply_text("❌ Invalid numbers.", reply_markup=admin_keyboard(), parse_mode="HTML")
                return True

            if count > 50:
                await update.message.reply_text("❌ Max 50 codes at once.", reply_markup=admin_keyboard(), parse_mode="HTML")
                return True

            codes = db.generate_bulk_codes(count, hours, admin_id)
            codes_text = "\n".join([f"<code>{c}</code>" for c in codes])
            await update.message.reply_text(
                f"🎁 <b>{count} Codes Created!</b>\n\n"
                f"Hours per code: {hours}\n\n"
                f"Codes:\n{codes_text}\n\n"
                f"Share these codes with users.",
                reply_markup=admin_keyboard(), parse_mode="HTML"
            )
            context.user_data["admin_action"] = None
            return True

        else:
            await update.message.reply_text(
                "❌ Format: <code>count hours</code>\nOr just <code>hours</code>",
                reply_markup=admin_keyboard(), parse_mode="HTML"
            )
            return True

    return False

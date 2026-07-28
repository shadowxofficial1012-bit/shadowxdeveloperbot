import logging
import json
import time
import asyncio
import io
import os
from urllib.parse import quote
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

import database as db
import api_client
import user_data_store as uds
from keyboards import (
    main_menu_keyboard,
    buy_plan_keyboard,
    confirm_payment_keyboard,
    back_button,
    export_keyboard,
    history_list_keyboard,
    reexport_keyboard,
    admin_keyboard,
    required_channels_keyboard,
    main_menu_button,
)
from datetime import datetime
from config import SUBSCRIPTION_PACKAGES, UPI_ID, UPI_NAME, FREE_TRIAL_HOURS, LOGO_PATH, BRAND_NAME, BRAND_TAGLINE, ADMIN_IDS, REQUIRED_CHANNELS


def generate_upi_qr(amount: int, note: str = "") -> io.BytesIO:
    """Generate a QR code image with UPI deep link for exact amount."""
    import qrcode
    upi_link = (
        f"upi://pay?pa={UPI_ID}"
        f"&pn={quote(UPI_NAME)}"
        f"&am={amount}.00"
        f"&tn={quote(note)}"
        f"&cu=INR"
    )
    qr = qrcode.make(upi_link)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    buf.seek(0)
    return buf

logger = logging.getLogger(__name__)

# --- Channel Membership Check ---
async def check_user_channels(user_id: int, bot) -> tuple[bool, list[str]]:
    """
    Check if user has joined all required channels/groups.
    Returns (is_member, list of channel names user needs to join).
    
    IMPORTANT: The bot MUST be an admin in the required channels to check membership.
    If the bot is NOT an admin, get_chat_member will fail with BadRequest.
    In this case, we allow the user through (assume they're a member) to avoid blocking everyone.
    """
    not_joined = []
    bot_cant_check = []
    
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["creator", "administrator", "member", "restricted"]:
                # User is a member - continue
                continue
            elif member.status == "left" or member.status == "kicked":
                # User explicitly left or was kicked
                not_joined.append(channel)
            else:
                # Unknown status - don't block
                logger.warning(f"Unknown member status '{member.status}' for {channel}")
                continue
        except BadRequest as e:
            # ANY BadRequest means bot can't check membership
            # This usually happens when bot is not admin in the channel
            # In this case, we MUST allow the user through
            logger.warning(f"Bot cannot check membership for {channel}: {e}. Allowing user through.")
            bot_cant_check.append(channel)
            continue
        except Exception as e:
            # On any other error, don't block the user
            logger.error(f"Unexpected error checking {channel}: {e}. Allowing user through.")
            bot_cant_check.append(channel)
            continue
    
    if bot_cant_check:
        logger.warning(f"Could not verify membership for channels: {bot_cant_check}. "
                       f"Bot must be added as admin to these channels for proper verification.")
    
    return (len(not_joined) == 0, not_joined)


# Max Telegram message length
MAX_MSG_LEN = 4096
MAX_CAPTION_LEN = 1024

# --- Rate Limiting ---
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 60
_rate_limit_tracker: dict[int, list[float]] = defaultdict(list)


def _check_rate_limit(user_id: int) -> tuple[bool, int]:
    now = time.time()
    _rate_limit_tracker[user_id] = [
        ts for ts in _rate_limit_tracker[user_id] if now - ts < RATE_LIMIT_WINDOW
    ]
    if len(_rate_limit_tracker[user_id]) >= RATE_LIMIT_MAX:
        oldest = _rate_limit_tracker[user_id][0]
        wait = int(RATE_LIMIT_WINDOW - (now - oldest)) + 1
        return False, wait
    return True, 0


def _record_lookup(user_id: int):
    _rate_limit_tracker[user_id].append(time.time())


def safe_str(val, default="N/A") -> str:
    if val is None or val == "":
        return default
    return str(val)


def escape_html(text: str) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_number(n):
    if n is None:
        return "0"
    try:
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return str(n)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with branded header image."""
    user = update.effective_user
    db_user = db.get_or_create_user(user.id, user.username, user.first_name)

    is_new = db_user["total_lookups"] == 0

    # Enforce channel join for non-admins
    if user.id not in ADMIN_IDS:
        is_member, not_joined = await check_user_channels(user.id, context.bot)
        if not is_member:
            channel_list = "\n".join([f"• {ch}" for ch in not_joined])
            text = (
                "🔴 <b>Join Required Channels!</b>\n\n"
                "You must join the following channels before using this bot:\n\n"
                f"{channel_list}\n\n"
                "After joining, tap the button below to verify."
            )
            await update.message.reply_text(
                text,
                reply_markup=required_channels_keyboard(),
                parse_mode="HTML",
            )
            return

    # Try to send branded header image
    try:
        from header import generate_header_image
        header_img = generate_header_image(
            brand_name=BRAND_NAME,
            tagline=BRAND_TAGLINE,
            logo_path=LOGO_PATH,
            credits=0,
            is_new=is_new,
        )
        await update.message.reply_photo(
            photo=header_img,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Header image failed: {e}")

    # Send welcome text
    is_admin_user = user.id in ADMIN_IDS
    has_access = is_admin_user or db.has_active_subscription(user.id)
    
    welcome = (
        f"👋 Welcome, <b>{user.first_name}</b>!\n\n"
        f"🔍 <b>Phone OSINT by @HATHI02</b>\n"
        "Get detailed information about any phone number.\n\n"
    )

    if is_new:
        welcome += "🎁 Start with our packages for unlimited searches!\n\n"

    if has_access:
        welcome += "✅ <b>Active Subscription</b> — Unlimited lookups!\n\n"
    else:
        welcome += "⚠️ <b>No active subscription</b> — Buy a package to continue.\n\n"

    if is_admin_user:
        welcome += "🏷 Admin: Tap <b>🔧 Admin Panel</b> below\n\n"

    welcome += "Choose an option below 👇"

    await update.message.reply_text(
        welcome,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help and ❓ Help Guide button."""
    text = (
        "📖 <b>Phone OSINT Bot by @HATHI02</b>\n\n"
        "🔍 <b>How to Use</b>\n"
        "1. Tap '💰 Buy Plan' to purchase access\n"
        "2. Or tap '🎁 Redeem Code' if you have a code\n"
        "3. Send a phone number (e.g., 9876543210)\n"
        "4. Get detailed OSINT data instantly!\n\n"
        "💡 <b>What You Get</b>\n"
        "• Full name & address\n"
        "• Alternative numbers\n"
        "• SIM card details\n"
        "• Location & carrier info\n"
        "• PDF report export\n\n"
        "💳 <b>Payment</b>\n"
        "Pay via UPI, upload screenshot, and get instant access.\n\n"
        "🛡 <b>Unlimited lookups</b> while your subscription is active.\n\n"
        "For support, contact @HATHI02."
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - check API health for all endpoints."""
    user = update.effective_user

    loading_msg = await update.message.reply_text(
        "🏥 <b>Checking API Health...</b>\n"
        "Pinging all endpoints, please wait...",
        parse_mode="HTML",
    )

    results = await api_client.check_api_health()

    lines = []
    lines.append("🏥 <b>API Health Status</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    for r in results:
        status = r["status"]
        name = r["name"]
        ms = r["ms"]
        detail = r["detail"]

        if status == "ok":
            icon = "✅"
            speed = "⚡" if ms < 1000 else "🟡" if ms < 3000 else "🐌"
            lines.append(f"{icon} <b>{name}</b> — {speed} {ms}ms")
        elif status == "blocked":
            lines.append(f"🚫 <b>{name}</b> — BLOCKED (403)")
        elif status == "timeout":
            lines.append(f"⏰ <b>{name}</b> — TIMEOUT ({ms}ms)")
        else:
            lines.append(f"❌ <b>{name}</b> — ERROR: {detail}")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # Summary
    ok_count = sum(1 for r in results if r["status"] == "ok")
    blocked_count = sum(1 for r in results if r["status"] == "blocked")
    error_count = sum(1 for r in results if r["status"] in ("error", "timeout"))
    total = len(results)

    if ok_count == total:
        lines.append("🟢 <b>All systems operational</b>")
    elif blocked_count > 0 and error_count == 0:
        lines.append(f"🟡 <b>{blocked_count}</b> endpoint(s) blocked — data may be partial")
    elif error_count > 0 and blocked_count == 0:
        lines.append(f"🔴 <b>{error_count}</b> endpoint(s) down — please try again later")
    else:
        lines.append(f"🔴 <b>{blocked_count + error_count}</b> endpoint(s) with issues")

    lines.append(f"")
    lines.append(f"📊 {ok_count}/{total} endpoints healthy")

    text = "\n".join(lines)
    await loading_msg.edit_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())


async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 🤳 Contact Admin button."""
    text = (
        "🤳 <b>Contact Admin</b>\n\n"
        "For support, payments, or any queries:\n\n"
        "📩 <b>Telegram:</b> @HATHI02\n\n"
        "Tap the link below to message us directly 👇"
    )
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Message @HATHI02", url="https://t.me/HATHI02")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
    ])
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle 🎁 Redeem Code button - ask user to enter their code."""
    text = (
        "🎁 <b>Redeem Code</b>\n\n"
        "Enter your redeem code below:\n\n"
        "Example: <code>ABC123XYZ9</code>"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    context.user_data["awaiting_redeem_code"] = True


async def process_redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process a redeem code entered by user."""
    code = update.message.text.strip()
    user = update.effective_user
    
    success, message, hours = db.redeem_code(code, user.id)
    
    if success:
        await update.message.reply_text(
            f"{message}\n\n🎉 Enjoy unlimited lookups!",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"{message}\n\nPlease try again or contact admin.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile."""
    user = update.effective_user
    db_user = db.get_or_create_user(user.id, user.username, user.first_name)
    
    is_admin_user = user.id in ADMIN_IDS
    has_access = db.has_active_subscription(user.id)
    expiry = db.get_subscription_expiry(user.id)
    
    text = (
        "👤 <b>Your Profile</b>\n\n"
        f"<b>Name:</b> {db_user['first_name'] or 'N/A'}\n"
        f"<b>Username:</b> @{db_user['username'] or 'N/A'}\n"
        f"<b>User ID:</b> <code>{db_user['user_id']}</code>\n"
        f"<b>Total Lookups:</b> {db_user['total_lookups']}\n"
        f"<b>Member Since:</b> {db_user['created_at'][:10]}\n"
    )
    
    if is_admin_user:
        text += "\n🏷 <b>Access:</b> ∞ Unlimited (Admin)"
    elif has_access:
        try:
            exp_dt = datetime.fromisoformat(expiry)
            text += f"\n✅ <b>Subscription active until:</b> {exp_dt.strftime('%d %b %Y, %I:%M %p')}"
        except:
            text += "\n✅ <b>Subscription active</b>"
    else:
        text += "\n⚠️ <b>No active subscription</b>"
    
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user balance/subscription status."""
    user = update.effective_user
    db.get_or_create_user(user.id, user.username, user.first_name)
    has_access = db.has_active_subscription(user.id)
    expiry = db.get_subscription_expiry(user.id)
    is_admin_user = user.id in ADMIN_IDS

    text = "💰 <b>Access Status</b>\n\n"
    
    if is_admin_user:
        text += "✅ <b>Status:</b> ∞ Unlimited (Admin)\n"
        text += "✅ Admin account — unlimited lookups."
    elif has_access:
        text += "✅ <b>Status:</b> <b>Active</b>\n"
        try:
            exp_dt = datetime.fromisoformat(expiry)
            remaining = exp_dt - datetime.now()
            hours = int(remaining.total_seconds() // 3600)
            mins = int((remaining.total_seconds() % 3600) // 60)
            text += f"📅 <b>Expires:</b> {exp_dt.strftime('%d %b %Y, %I:%M %p')}\n"
            text += f"⏰ <b>Time left:</b> {hours}h {mins}m\n\n"
            text += "You have <b>unlimited lookups</b> while active."
        except:
            text += "You have <b>unlimited lookups</b> while active."
    else:
        text += "⚠️ <b>Status:</b> <b>No Active Subscription</b>\n\n"
        text += "Buy a package to get unlimited lookups!"

    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def tx_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user transaction history."""
    user = update.effective_user
    txs = db.get_user_transactions(user.id, limit=10)

    if not txs:
        text = "📋 <b>Transaction History</b>\n\nNo transactions yet."
    else:
        text = "📋 <b>Transaction History</b>\n\n"
        for tx in txs:
            icon = "✅" if tx["status"] == "approved" else "⏳" if tx["status"] == "pending" else "❌"
            text += (
                f"{icon} <b>{tx['package'].title()}</b> — "
                f"₹{tx['amount']} • Unlimited lookups\n"
                f"   📅 {tx['created_at'][:16]}\n\n"
            )

    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def buy_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show subscription packages with QR code."""
    text = (
        "💰 <b>Buy Plan — Unlimited Lookups</b>\n\n"
        "Choose a package below:\n\n"
        f"💵 <b>UPI ID:</b> <code>{UPI_ID}</code>\n"
        f"👤 <b>Name:</b> {UPI_NAME}\n\n"
        "🔐 <b>Unlimited lookups</b> for the duration!\n"
        "Send payment, then upload screenshot to confirm."
    )
    # Generate and send QR code image with UPI details (no amount yet — user selects package first)
    try:
        import qrcode
        upi_link = (
            f"upi://pay?pa={UPI_ID}"
            f"&pn={quote(UPI_NAME)}"
            f"&cu=INR"
        )
        qr = qrcode.make(upi_link)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        buf.seek(0)
        await update.message.reply_photo(
            photo=buf,
            caption=text,
            reply_markup=buy_plan_keyboard(),
            parse_mode="HTML",
        )
        return
    except Exception as e:
        logger.error(f"Failed to generate QR code: {e}")
    # Fallback: text only
    await update.message.reply_text(text, reply_markup=buy_plan_keyboard(), parse_mode="HTML")


# --- Admin Payment Approve/Reject Helpers ---

async def _approve_transaction(tx_id: int, context, query=None):
    """Approve a transaction: update status, activate subscription, notify user."""
    db.update_transaction_status(tx_id, "approved")

    # Update payment status in unified JSON store
    try:
        uds.update_payment_status(tx_id, "approved")
    except Exception as e:
        logger.warning(f"JSON store update_payment_status failed: {e}")

    conn = db.get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
    row = c.fetchone()
    conn.close()

    if row:
        tx = dict(row)
        if tx["package"] in SUBSCRIPTION_PACKAGES:
            hours = SUBSCRIPTION_PACKAGES[tx["package"]]["duration_hours"]
            expiry = db.set_subscription(tx["user_id"], hours)
            # Save subscription to unified JSON store
            try:
                uds.save_subscription(tx["user_id"], tx["package"], tx["amount"], expiry)
            except Exception as e:
                logger.warning(f"JSON store save_subscription failed: {e}")
            try:
                await context.bot.send_message(
                    tx["user_id"],
                    f"✅ <b>Payment Approved!</b>\n\n"
                    f"Package: <b>{tx['package'].title()}</b>\n"
                    f"💰 <b>Unlimited lookups activated!</b>\n"
                    f"Valid until: {datetime.fromisoformat(expiry).strftime('%d %b %Y, %I:%M %p')}",
                    parse_mode="HTML",
                )
            except Exception:
                pass

    result = f"✅ <b>Transaction #{tx_id} Approved</b>\nSubscription activated for user."
    if query:
        try:
            await query.edit_message_text(result, parse_mode="HTML")
        except BadRequest:
            await query.message.reply_text(result, parse_mode="HTML")
    return result


async def _reject_transaction(tx_id: int, context, query=None):
    """Reject a transaction: update status, notify user."""
    db.update_transaction_status(tx_id, "rejected")

    # Update payment status in unified JSON store
    try:
        uds.update_payment_status(tx_id, "rejected")
    except Exception as e:
        logger.warning(f"JSON store update_payment_status failed: {e}")

    conn = db.get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
    row = c.fetchone()
    conn.close()

    if row:
        tx = dict(row)
        try:
            await context.bot.send_message(
                tx["user_id"],
                f"❌ <b>Payment Rejected</b>\n\n"
                f"Package: {tx['package'].title()}\n"
                "Contact admin for support.",
                parse_mode="HTML",
            )
        except Exception:
            pass

    result = f"❌ <b>Transaction #{tx_id} Rejected</b>"
    if query:
        try:
            await query.edit_message_text(result, parse_mode="HTML")
        except BadRequest:
            await query.message.reply_text(result, parse_mode="HTML")
    return result


USERS_PAGE_SIZE = 10


async def _send_userdata_page(update_or_query, context, page_num: int):
    """Send a paginated user list page with navigation buttons."""
    all_users = uds.get_all_users()
    total = len(all_users)
    total_pages = max(1, (total + USERS_PAGE_SIZE - 1) // USERS_PAGE_SIZE)
    page_num = max(0, min(page_num, total_pages - 1))

    start_idx = page_num * USERS_PAGE_SIZE
    page_users = all_users[start_idx:start_idx + USERS_PAGE_SIZE]

    lines = []
    lines.append(f"👥 <b>Users (Page {page_num + 1}/{total_pages})</b>")
    lines.append(f"📊 Total: {total} users")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    for u in page_users:
        sub = u.get('subscription', {})
        sub_status = "✅" if sub.get('status') == 'active' else "⚠️"
        sub_pkg = sub.get('package', 'None') or 'None'
        lines.append(
            f"{sub_status} <b>{u.get('first_name', 'N/A')}</b> "
            f"(@{u.get('username', 'N/A')}) "
            f"ID: <code>{u.get('user_id')}</code>"
        )
        lines.append(
            f"   📊 {u.get('total_lookups', 0)} lookups | "
            f"💰 ₹{u.get('total_spent', 0)} spent | "
            f"📋 {sub_pkg}"
        )
    lines.append("")
    lines.append(f"Page {page_num + 1} of {total_pages}")

    text = "\n".join(lines)

    # Build pagination keyboard
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = []
    nav_row = []
    if page_num > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"udpage_{page_num - 1}"))
    nav_row.append(InlineKeyboardButton(f"{page_num + 1}/{total_pages}", callback_data="noop"))
    if page_num < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"udpage_{page_num + 1}"))
    buttons.append(nav_row)
    buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="back_main")])
    keyboard = InlineKeyboardMarkup(buttons)

    # Edit or send
    if hasattr(update_or_query, 'edit_message_text'):
        try:
            await update_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        except BadRequest:
            await update_or_query.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update_or_query.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def _send_single_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Display full data for a single user."""
    user_data = uds.get_user_full_data(user_id)
    if not user_data:
        await update.message.reply_text(
            f"❌ User <code>{user_id}</code> not found in database.",
            parse_mode="HTML",
        )
        return

    lines = []
    lines.append(f"👤 <b>User Profile — {user_id}</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    # Profile section
    lines.append("<b>📋 Profile</b>")
    lines.append(f"   👤 Name: <b>{user_data.get('first_name', 'N/A')}</b>")
    lines.append(f"   📛 Username: @{user_data.get('username', 'N/A')}")
    lines.append(f"   🆔 User ID: <code>{user_data.get('user_id')}</code>")
    lines.append(f"   📅 First Seen: {user_data.get('first_seen', 'N/A')[:16]}")
    lines.append(f"   🕐 Last Active: {user_data.get('last_active', 'N/A')[:16]}")
    lines.append(f"   🚫 Banned: {'Yes' if user_data.get('is_banned') else 'No'}")
    lines.append("")

    # Subscription section
    sub = user_data.get('subscription', {})
    lines.append("<b>💰 Subscription</b>")
    sub_status = sub.get('status', 'inactive')
    if sub_status == 'active':
        lines.append(f"   ✅ Status: <b>Active</b>")
        lines.append(f"   📦 Package: {sub.get('package', 'N/A')}")
        lines.append(f"   📅 Expiry: {sub.get('expiry', 'N/A')}")
        lines.append(f"   🕐 Activated: {sub.get('activated_at', 'N/A')[:16]}")
        # Check if expired
        try:
            exp_dt = datetime.fromisoformat(sub.get('expiry', ''))
            if exp_dt < datetime.now():
                lines.append(f"   ⚠️ <b>EXPIRED</b>")
        except:
            pass
    else:
        lines.append(f"   ⚠️ Status: <b>Inactive</b>")
    lines.append("")

    # Usage stats
    lines.append("<b>📊 Usage Stats</b>")
    lines.append(f"   🔍 Total Lookups: {user_data.get('total_lookups', 0)}")
    lines.append(f"   💳 Total Spent: ₹{user_data.get('total_spent', 0)}")
    lines.append(f"   💰 Total Paid: ₹{user_data.get('total_paid', 0)}")
    lines.append("")

    # Payments
    payments = user_data.get('all_payments', [])
    if payments:
        lines.append("<b>💳 Payment History</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for p in payments[-10:]:  # Last 10 payments
            icon = "✅" if p.get('status') == 'approved' else "⏳" if p.get('status') == 'pending' else "❌"
            lines.append(
                f"   {icon} <b>{p.get('package', 'N/A').title()}</b> — "
                f"₹{p.get('amount', 0)} | {p.get('status', 'N/A')}"
            )
            lines.append(f"      📅 {p.get('timestamp', 'N/A')[:16]}")
        if len(payments) > 10:
            lines.append(f"   ... and {len(payments) - 10} more payments")
        lines.append("")

    # Lookups
    lookups = user_data.get('all_lookups', [])
    if lookups:
        lines.append("<b>🔍 Lookup History</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for l in lookups[-10:]:  # Last 10 lookups
            icon = "✅" if l.get('success') else "❌"
            lines.append(
                f"   {icon} {l.get('lookup_type', 'N/A')} — "
                f"<code>{l.get('query', 'N/A')}</code>"
            )
            lines.append(f"      📅 {l.get('timestamp', 'N/A')[:16]}")
        if len(lookups) > 10:
            lines.append(f"   ... and {len(lookups) - 10} more lookups")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("📊 <b>Owner: @HATHI02 | Developer: @shadowxdeveloper</b>")

    text = "\n".join(lines)

    # Split if too long
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Users", callback_data="udpage_0")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="back_main")]
    ])

    if len(text) + 50 > MAX_MSG_LEN:
        part1 = text[:3800]
        part2 = text[3800:]
        await update.message.reply_text(part1, parse_mode="HTML")
        await update.message.reply_text(part2, parse_mode="HTML", reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def handle_userdata_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /userdata command - show stats and export user_data.json.
    
    Usage:
      /userdata         - Show all users with pagination
      /userdata <id>    - Show single user's full data
    """
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 <b>Access Denied.</b>", parse_mode="HTML")
        return

    # Check if a user_id was provided
    if context.args and len(context.args) > 0:
        try:
            target_user_id = int(context.args[0])
            await _send_single_user_data(update, context, target_user_id)
            return
        except ValueError:
            await update.message.reply_text(
                "❌ <b>Invalid User ID!</b>\n\n"
                "Usage: <code>/userdata</code> or <code>/userdata &lt;user_id&gt;</code>\n"
                "Example: <code>/userdata 123456789</code>",
                parse_mode="HTML",
            )
            return

    loading_msg = await update.message.reply_text(
        "📊 <b>Loading user data...</b>",
        parse_mode="HTML",
    )

    try:
        stats = uds.get_stats()
        all_users = uds.get_all_users()
        all_payments = uds.get_all_payments(limit=50)

        # Build stats message
        lines = []
        lines.append("📊 <b>User Data Report</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append(f"👥 <b>Total Users:</b> {stats.get('total_users', 0)}")
        lines.append(f"🔍 <b>Total Lookups:</b> {stats.get('total_lookups', 0)}")
        lines.append(f"💳 <b>Total Payments:</b> {stats.get('total_payments', 0)}")
        lines.append(f"✅ <b>Approved:</b> {stats.get('approved_payments', 0)}")
        lines.append(f"⏳ <b>Pending:</b> {stats.get('pending_payments', 0)}")
        lines.append(f"💰 <b>Total Revenue:</b> ₹{stats.get('total_revenue', 0)}")
        lines.append("")

        # Lookup type breakdown
        lookup_types = stats.get('lookup_types', {})
        if lookup_types:
            lines.append("🔍 <b>Lookup Breakdown:</b>")
            for lt, count in lookup_types.items():
                lines.append(f"   • {lt}: {count}")
            lines.append("")

        # Active subscriptions
        lines.append(f"✅ <b>Active Subscriptions:</b> {stats.get('active_subscriptions', 0)}")
        lines.append("")

        # User list with pagination
        PAGE_SIZE = 10
        total_users_count = len(all_users)
        total_pages = max(1, (total_users_count + PAGE_SIZE - 1) // PAGE_SIZE)
        current_page = 0
        page_users = all_users[current_page * PAGE_SIZE:(current_page + 1) * PAGE_SIZE]

        lines.append(f"👥 <b>Users (Page {current_page + 1}/{total_pages}):</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        for u in page_users:
            sub = u.get('subscription', {})
            sub_status = "✅" if sub.get('status') == 'active' else "⚠️"
            sub_pkg = sub.get('package', 'None') or 'None'
            lines.append(
                f"{sub_status} <b>{u.get('first_name', 'N/A')}</b> "
                f"(@{u.get('username', 'N/A')}) "
                f"ID: <code>{u.get('user_id')}</code>"
            )
            lines.append(
                f"   📊 {u.get('total_lookups', 0)} lookups | "
                f"💰 ₹{u.get('total_spent', 0)} spent | "
                f"📋 {sub_pkg}"
            )
        lines.append("")

        # Recent payments
        if all_payments:
            lines.append("💳 <b>Recent Payments:</b>")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            for p in all_payments[:10]:
                icon = "✅" if p.get('status') == 'approved' else "⏳" if p.get('status') == 'pending' else "❌"
                lines.append(
                    f"{icon} <b>{p.get('package', 'N/A').title()}</b> — "
                    f"₹{p.get('amount', 0)} | "
                    f"{p.get('username', 'N/A')} | "
                    f"{p.get('timestamp', 'N/A')[:16]}"
                )
            lines.append("")

        text = "\n".join(lines)

        # Send stats text (split if too long)
        if len(text) + 50 > MAX_MSG_LEN:
            part1 = text[:3800]
            part2 = text[3800:]
            await loading_msg.edit_text(part1, parse_mode="HTML")
            if part2:
                await update.message.reply_text(part2, parse_mode="HTML")
        else:
            await loading_msg.edit_text(text, parse_mode="HTML")

        # Send the JSON file as attachment
        try:
            import user_data_store as _uds_file
            json_path = _uds_file.USER_DATA_FILE
            if os.path.exists(json_path):
                with open(json_path, 'rb') as f:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=f,
                        filename="user_data.json",
                        caption="📄 <b>Full user_data.json export</b>",
                        parse_mode="HTML",
                    )
            else:
                await update.message.reply_text(
                    "⚠️ user_data.json not found yet. Data will appear after first user interaction.",
                    parse_mode="HTML",
                )
        except Exception as e:
            logger.error(f"Failed to send user_data.json: {e}")
            await update.message.reply_text(
                f"⚠️ Could not send file: {str(e)[:100]}",
                parse_mode="HTML",
            )

        # Generate and send CSV files for spreadsheet analysis
        try:
            import csv as csv_mod

            # --- Users CSV ---
            users_buf = io.BytesIO()
            users_writer = csv_mod.writer(users_buf)
            users_writer.writerow([
                "User ID", "Username", "First Name", "First Seen", "Last Active",
                "Total Lookups", "Total Spent", "Sub Status", "Sub Package",
                "Sub Expiry", "Is Banned"
            ])
            for u in all_users:
                sub = u.get('subscription', {})
                users_writer.writerow([
                    u.get('user_id', ''),
                    u.get('username', ''),
                    u.get('first_name', ''),
                    u.get('first_seen', ''),
                    u.get('last_active', ''),
                    u.get('total_lookups', 0),
                    u.get('total_spent', 0),
                    sub.get('status', 'inactive'),
                    sub.get('package', ''),
                    sub.get('expiry', ''),
                    u.get('is_banned', False),
                ])
            users_buf.seek(0)
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=users_buf,
                filename="users_export.csv",
                caption="📊 <b>Users CSV</b> — Open in Excel/Sheets",
                parse_mode="HTML",
            )

            # --- Payments CSV ---
            all_payments_full = uds.get_all_payments(limit=500)
            if all_payments_full:
                pays_buf = io.BytesIO()
                pays_writer = csv_mod.writer(pays_buf)
                pays_writer.writerow([
                    "Payment ID", "User ID", "Username", "Package", "Amount",
                    "Status", "Timestamp", "TX ID"
                ])
                for p in all_payments_full:
                    pays_writer.writerow([
                        p.get('id', ''),
                        p.get('user_id', ''),
                        p.get('username', ''),
                        p.get('package', ''),
                        p.get('amount', 0),
                        p.get('status', ''),
                        p.get('timestamp', ''),
                        p.get('tx_id', ''),
                    ])
                pays_buf.seek(0)
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=pays_buf,
                    filename="payments_export.csv",
                    caption="💳 <b>Payments CSV</b> — Open in Excel/Sheets",
                    parse_mode="HTML",
                )

        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            await update.message.reply_text(
                f"⚠️ CSV export failed: {str(e)[:100]}",
                parse_mode="HTML",
            )

    except Exception as e:
        logger.error(f"userdata command failed: {e}")
        await loading_msg.edit_text(
            f"❌ <b>Error loading data:</b> {str(e)[:200]}",
            parse_mode="HTML",
        )


async def handle_approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /approve <tx_id> command."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 <b>Access Denied.</b>", parse_mode="HTML")
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ Usage: <code>/approve &lt;tx_id&gt;</code>\nExample: <code>/approve 5</code>",
            parse_mode="HTML",
        )
        return
    try:
        tx_id = int(args[0])
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Invalid transaction ID. Example: <code>/approve 5</code>",
            parse_mode="HTML",
        )
        return
    await _approve_transaction(tx_id, context)
    await update.message.reply_text(
        f"✅ <b>Transaction #{tx_id} Approved</b>\nSubscription activated for user.",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def handle_reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /reject <tx_id> command."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 <b>Access Denied.</b>", parse_mode="HTML")
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ Usage: <code>/reject &lt;tx_id&gt;</code>\nExample: <code>/reject 5</code>",
            parse_mode="HTML",
        )
        return
    try:
        tx_id = int(args[0])
    except (ValueError, IndexError):
        await update.message.reply_text(
            "❌ Invalid transaction ID. Example: <code>/reject 5</code>",
            parse_mode="HTML",
        )
        return
    await _reject_transaction(tx_id, context)
    await update.message.reply_text(
        f"❌ <b>Transaction #{tx_id} Rejected</b>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline button callbacks."""
    query = update.callback_query
    data = query.data

    # Only respond in private chats (DMs)
    if update.effective_chat.type != "private":
        await query.answer()
        return

    await query.answer()

    user = query.from_user

    # Verify channels membership - this is always allowed
    if data == "verify_channels":
        is_member, not_joined = await check_user_channels(user.id, context.bot)
        if is_member:
            text = (
                "✅ <b>Verification Successful!</b>\n\n"
                "You have joined all required channels.\n"
                "You can now use the bot."
            )
            try:
                await query.edit_message_text(text, reply_markup=main_menu_button(), parse_mode="HTML")
            except BadRequest:
                await query.message.reply_text(text, reply_markup=main_menu_button(), parse_mode="HTML")
        else:
            channel_list = "\n".join([f"• {ch}" for ch in not_joined])
            text = (
                "🔴 <b>Not Yet Verified!</b>\n\n"
                "You still need to join:\n"
                f"{channel_list}\n\n"
                "Join then tap verify again."
            )
            try:
                await query.edit_message_text(text, reply_markup=required_channels_keyboard(), parse_mode="HTML")
            except BadRequest:
                await query.message.reply_text(text, reply_markup=required_channels_keyboard(), parse_mode="HTML")
        return

    # Channel check for ALL other callbacks (non-admins only)
    if user.id not in ADMIN_IDS:
        is_member, not_joined = await check_user_channels(user.id, context.bot)
        if not is_member:
            channel_list = "\n".join([f"• {ch}" for ch in not_joined])
            text = (
                "🔴 <b>Join Required Channels!</b>\n\n"
                "You must join the following channels:\n\n"
                f"{channel_list}\n\n"
                "After joining, tap verify below."
            )
            try:
                await query.edit_message_text(text, reply_markup=required_channels_keyboard(), parse_mode="HTML")
            except BadRequest:
                await query.message.reply_text(text, reply_markup=required_channels_keyboard(), parse_mode="HTML")
            return

    # Back to main menu
    if data == "back_main":
        is_admin_user = user.id in ADMIN_IDS
        has_access = is_admin_user or db.has_active_subscription(user.id)
        expiry = db.get_subscription_expiry(user.id)
        
        if is_admin_user:
            status_text = "∞ Unlimited (Admin)"
        elif has_access:
            try:
                exp_dt = datetime.fromisoformat(expiry)
                status_text = f"Active until {exp_dt.strftime('%d %b')}"
            except:
                status_text = "Active"
        else:
            status_text = "No active subscription"
        
        text = (
            f"👋 Hey, <b>{user.first_name}</b>!\n\n"
            f"💰 <b>Status:</b> {status_text}\n\n"
            "Choose an option 👇"
        )
        try:
            await query.edit_message_text(text, reply_markup=main_menu_button(), parse_mode="HTML")
        except BadRequest:
            await query.message.reply_text(text, reply_markup=main_menu_button(), parse_mode="HTML")
        return

    # Buy plan package selection
    if data.startswith("buy_"):
        package_key = data.replace("buy_", "")
        if package_key not in SUBSCRIPTION_PACKAGES:
            await query.edit_message_text("Invalid package.", reply_markup=main_menu_button())
            return

        pkg = SUBSCRIPTION_PACKAGES[package_key]
        text = (
            f"💰 <b>{pkg['label']}</b>\n\n"
            f"💵 <b>Price:</b> ₹{pkg['price']}\n"
            f"💰 <b>Access:</b> Unlimited lookups\n"
            f"📅 <b>Duration:</b> {pkg['label']}\n\n"
            f"💳 <b>Send payment to:</b>\n"
            f"<code>{UPI_ID}</code>\n"
            f"Name: {UPI_NAME}\n\n"
            "After payment, send a screenshot of the payment confirmation.\n"
            "Include your <b>User ID</b> in the payment reference."
        )
        context.user_data["pending_package"] = package_key
        try:
            await query.edit_message_text(text, reply_markup=confirm_payment_keyboard(package_key), parse_mode="HTML")
        except BadRequest:
            await query.message.reply_text(text, reply_markup=confirm_payment_keyboard(package_key), parse_mode="HTML")
        return

    # Confirm payment - generate UPI QR with exact amount
    if data.startswith("confirm_"):
        package_key = data.replace("confirm_", "")
        if package_key not in SUBSCRIPTION_PACKAGES:
            await query.edit_message_text("Invalid package.", reply_markup=main_menu_button())
            return
        context.user_data["awaiting_screenshot"] = package_key
        pkg = SUBSCRIPTION_PACKAGES[package_key]

        # Generate QR code with exact amount
        try:
            qr_buf = generate_upi_qr(pkg["price"], note=f"{BRAND_NAME} {pkg['label']}")
            caption = (
                f"💳 <b>Scan to Pay - {pkg['label']}</b>\n\n"
                f"💵 <b>Amount:</b> ₹{pkg['price']}\n"
                f"💰 <b>Access:</b> Unlimited lookups\n"
                f"📅 <b>Duration:</b> {pkg['label']}\n\n"
                f"💳 <b>UPI ID:</b> <code>{UPI_ID}</code>\n"
                f"👤 <b>Name:</b> {UPI_NAME}\n\n"
                "📸 After payment, <b>send the screenshot</b> of the confirmation below.\n"
                "Make sure the screenshot shows:\n"
                "• UPI ID paid to\n"
                "• Amount paid\n"
                "• Transaction reference/ID"
            )
            try:
                await query.message.delete()
            except Exception:
                pass
            await context.bot.send_photo(
                chat_id=query.message.chat.id,
                photo=qr_buf,
                caption=caption,
                reply_markup=main_menu_button(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"QR generation failed: {e}")
            msg_text = (
                f"📸 <b>Send payment screenshot</b>\n\n"
                f"You selected: <b>{pkg['label']}</b> (₹{pkg['price']})\n\n"
                f"💳 <b>Send payment to:</b>\n"
                f"<code>{UPI_ID}</code>\n"
                f"Name: {UPI_NAME}\n"
                f"Amount: ₹{pkg['price']}\n\n"
                "Upload the payment confirmation screenshot now.\n"
                "Make sure the screenshot shows:\n"
                "• UPI ID paid to\n"
                "• Amount\n"
                "• Transaction reference/ID"
            )
            try:
                await query.edit_message_text(msg_text, parse_mode="HTML")
            except BadRequest:
                await query.message.reply_text(msg_text, parse_mode="HTML")
        return

    # Cancel payment
    if data == "cancel_payment":
        context.user_data.pop("awaiting_screenshot", None)
        context.user_data.pop("pending_package", None)
        try:
            await query.edit_message_text(
                "❌ Payment cancelled.\n\nChoose an option:",
                reply_markup=main_menu_button(),
            )
        except BadRequest:
            await query.message.reply_text(
                "❌ Payment cancelled.\n\nChoose an option:",
                reply_markup=main_menu_button(),
            )
        return

    # Admin: Approve transaction
    if data.startswith("approve_"):
        if user.id not in ADMIN_IDS:
            return
        tx_id = int(data.replace("approve_", ""))
        await _approve_transaction(tx_id, context, query)
        return

    # Admin: Reject transaction
    if data.startswith("reject_"):
        if user.id not in ADMIN_IDS:
            return
        tx_id = int(data.replace("reject_", ""))
        await _reject_transaction(tx_id, context, query)
        return

    # Admin: User data page navigation
    if data.startswith("udpage_"):
        if user.id not in ADMIN_IDS:
            return
        page_num = int(data.replace("udpage_", ""))
        await _send_userdata_page(update, context, page_num)
        return

    # Admin: Confirm ban
    if data.startswith("doban_"):
        if user.id not in ADMIN_IDS:
            return
        ban_uid = int(data.replace("doban_", ""))
        db.ban_user(ban_uid)
        try:
            await query.edit_message_text(
                f"🚫 User <code>{ban_uid}</code> has been banned.",
                parse_mode="HTML",
            )
        except BadRequest:
            await query.message.reply_text(
                f"🚫 User <code>{ban_uid}</code> has been banned.",
                parse_mode="HTML",
            )
        return

    # Cancel action
    if data == "cancel_action":
        try:
            await query.edit_message_text("❌ Action cancelled.", reply_markup=main_menu_button())
        except BadRequest:
            await query.message.reply_text("❌ Action cancelled.", reply_markup=main_menu_button())
        return

    # Export report as image + PDF
    if data.startswith("export_"):
        export_number = data.replace("export_", "")
        lookup_data = context.user_data.get("last_lookup")
        if not lookup_data:
            await query.edit_message_text(
                "❌ No data to export. Please run a lookup first.",
                reply_markup=main_menu_button(),
            )
            return

        await query.answer("🖼 Generating reports...")

        try:
            from exporter import generate_report_image
            image_buffer = generate_report_image(lookup_data)
            await context.bot.send_photo(
                chat_id=query.message.chat.id,
                photo=image_buffer,
                caption=f"🖼 <b>Image Report</b> for {export_number}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Image export failed: {e}")

        try:
            from pdf_exporter import generate_numleak_pdf, generate_upi_pdf, generate_vehicle_pdf
            lookup_type = lookup_data.get("lookup_type", "numleak")
            if lookup_type == "upi":
                pdf_buffer = generate_upi_pdf(lookup_data)
            elif lookup_type == "vehicle":
                pdf_buffer = generate_vehicle_pdf(lookup_data)
            else:
                pdf_buffer = generate_numleak_pdf(lookup_data)
            await context.bot.send_document(
                chat_id=query.message.chat.id,
                document=pdf_buffer,
                filename=f"OSINT_{export_number}.pdf",
                caption=f"📄 <b>PDF Report</b> for {export_number}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"PDF export failed: {e}")

        return

    # History: show lookup list
    if data == "history":
        lookups = db.get_user_lookup_history(user.id, limit=10)
        if not lookups:
            await query.edit_message_text(
                "📋 <b>No lookups yet.</b>\nDo a lookup first!",
                reply_markup=main_menu_button(),
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text(
                "📋 <b>Tap to re-export (no credits):</b>",
                reply_markup=history_list_keyboard(lookups),
                parse_mode="HTML",
            )
        return

    # Re-export: show re-export options
    if data.startswith("reexport_") and not data.startswith("reexportimg_"):
        lookup_id = int(data.replace("reexport_", ""))
        cached = db.get_lookup_by_id(lookup_id, user.id)
        if not cached:
            await query.edit_message_text("❌ Lookup not found.", reply_markup=main_menu_button())
            return
        await query.edit_message_text(
            f"📱 Re-export <b>{cached['username']}</b>\n\n"
            "Tap below to generate the image:",
            reply_markup=reexport_keyboard(lookup_id, cached["username"]),
            parse_mode="HTML",
        )
        return

    # Re-export as image
    if data.startswith("reexportimg_"):
        lookup_id = int(data.replace("reexportimg_", ""))
        cached = db.get_lookup_by_id(lookup_id, user.id)
        if not cached:
            await query.edit_message_text("❌ Lookup not found.", reply_markup=main_menu_button())
            return

        await query.answer("🖼 Generating report...")

        try:
            import json as _json
            lookup_data = _json.loads(cached["api_data"])
            from exporter import generate_report_image
            image_buffer = generate_report_image(lookup_data)
            await context.bot.send_photo(
                chat_id=query.message.chat.id,
                photo=image_buffer,
                caption=f"🖼 <b>Re-exported Report</b> for {cached['username']}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Re-export failed: {e}")
            await query.edit_message_text(
                f"❌ <b>Export failed</b>\n\nError: {str(e)[:200]}",
                reply_markup=main_menu_button(),
                parse_mode="HTML",
            )
        return


async def demo_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a demo result so users can see how output looks."""
    from pdf_exporter import generate_numleak_text_report, generate_numleak_pdf
    
    demo_data = {
        "number": "9876543210",
        "numleak_data": {
            "chain": {
                "title": "Indian Mobile Number Database Leak",
                "description": "Leaked database containing mobile number registration details",
                "records": [{
                    "FullName": "Rahul Kumar",
                    "FatherName": "Suresh Kumar",
                    "Phone": "9876543210",
                    "Phone2": "9123456789",
                    "DocumentNumber": "DEMO12345",
                    "Adres": "123 MG Road, Connaught Place, New Delhi, Delhi 110001",
                    "Region": "Delhi NCR"
                }]
            },
            "calltracer": {
                "Number": "+91-9876543210",
                "SIM card": "Jio (Reliance Jio Infocomm Limited)",
                "Mobile State": "Delhi",
                "Connection": "Prepaid 4G SIM card",
                "Hometown": "New Delhi, India",
                "Language": "Hindi",
                "IMEI number": "3567***9***12345",
                "Tracking History": "Traced by 5 people in 24 hrs"
            }
        }
    }
    
    text_report = generate_numleak_text_report(demo_data)
    await update.message.reply_text(
        f"<pre>{text_report}</pre>",
        parse_mode="HTML",
    )
    
    try:
        pdf_buffer = generate_numleak_pdf(demo_data)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename="DEMO_OSINT_REPORT.pdf",
            caption="📄 <b>Demo PDF Report</b>\nThis is how your reports will look.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Demo PDF failed: {e}")
    
    await update.message.reply_text(
        "ℹ️ <b>That was a demo!</b>\n"
        "Enter a real phone number to get actual OSINT data.\n"
        "Tap '💰 Buy Plan' to start.",
        reply_markup=main_menu_keyboard(), 
        parse_mode="HTML",
    )


async def demo_upi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a demo UPI lookup result."""
    from pdf_exporter import generate_upi_text_report, generate_upi_pdf
    
    demo_data = {
        "number": "9876543210",
        "upi_data": {
            "upi": {
                "vpa": "rahul.kumar@okicici",
                "name": "Rahul Kumar",
                "bank": "ICICI Bank",
                "mcc": "0000",
                "account_status": "Active",
                "last_transaction": "2026-07-15 14:30:00"
            },
            "account": {
                "account_holder": "Rahul Kumar",
                "bank_name": "ICICI Bank",
                "account_type": "Savings",
                "ifsc": "ICIC0001234",
                "branch": "Connaught Place, New Delhi"
            },
            "transaction": {
                "total_transactions": "247",
                "total_amount": "₹3,45,678",
                "average_transaction": "₹1,399",
                "last_30_days": "58 transactions"
            }
        }
    }
    
    text_report = generate_upi_text_report(demo_data)
    await update.message.reply_text(
        f"<pre>{text_report}</pre>",
        parse_mode="HTML",
    )
    
    try:
        pdf_buffer = generate_upi_pdf(demo_data)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename="DEMO_UPI_REPORT.pdf",
            caption="📄 <b>Demo UPI Report</b>\nThis is how your UPI reports will look.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Demo UPI PDF failed: {e}")
    
    await update.message.reply_text(
        "ℹ️ <b>That was a demo!</b>\n"
        "Enter a real phone number to get actual UPI data.\n"
        "Tap '💰 Buy Plan' to start.",
        reply_markup=main_menu_keyboard(), 
        parse_mode="HTML",
    )


async def demo_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a demo vehicle lookup result."""
    from pdf_exporter import generate_vehicle_text_report, generate_vehicle_pdf
    
    demo_data = {
        "vehicle_plate": "MH12AB1234",
        "vehicle_data": {
            "vehicle": {
                "registration_number": "MH12AB1234",
                "registration_date": "2020-05-15",
                "vehicle_class": "Motor Car (LMV)",
                "fuel_type": "Petrol",
                "maker": "Maruti Suzuki",
                "model": "Swift Dzire",
                "color": "Pearl Arctic White",
                "engine_number": "K12N***",
                "chassis_number": "MA3FJ***"
            },
            "owner": {
                "owner_name": "Rahul Kumar",
                "father_name": "Suresh Kumar",
                "present_address": "123 MG Road, Connaught Place, New Delhi, Delhi 110001",
                "permanent_address": "456 Park Street, Mumbai, Maharashtra 400001",
                "mobile_number": "+91-9876543210",
                "ownership_count": 1
            },
            "tax": {
                "tax_upto": "2027-03-31",
                "tax_paid": "₹4,500",
                "fitness_upto": "2027-05-15",
                "insurance_upto": "2027-01-20"
            }
        }
    }
    
    text_report = generate_vehicle_text_report(demo_data)
    await update.message.reply_text(
        f"<pre>{text_report}</pre>",
        parse_mode="HTML",
    )
    
    try:
        pdf_buffer = generate_vehicle_pdf(demo_data)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename="DEMO_VEHICLE_REPORT.pdf",
            caption="📄 <b>Demo Vehicle Report</b>\nThis is how your vehicle reports will look.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Demo Vehicle PDF failed: {e}")
    
    await update.message.reply_text(
        "ℹ️ <b>That was a demo!</b>\n"
        "Enter a real vehicle plate number to get actual data.\n"
        "Tap '💰 Buy Plan' to start.",
        reply_markup=main_menu_keyboard(), 
        parse_mode="HTML",
    )


async def handle_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone number lookup with full code-formatted output."""
    user = update.effective_user
    is_admin_user = user.id in ADMIN_IDS

    # Enforce channel join for non-admins
    if not is_admin_user:
        is_member, not_joined = await check_user_channels(user.id, context.bot)
        if not is_member:
            channel_list = "\n".join([f"• {ch}" for ch in not_joined])
            text = (
                "🔴 <b>Join Required Channels!</b>\n\n"
                "You must join the following channels:\n\n"
                f"{channel_list}\n\n"
                "After joining, tap the button below to verify."
            )
            await update.message.reply_text(
                text,
                reply_markup=required_channels_keyboard(),
                parse_mode="HTML",
            )
            return

    if db.is_banned(user.id):
        await update.message.reply_text(
            "🚫 You are <b>banned</b> from using this bot.\nContact admin for support.",
            parse_mode="HTML",
        )
        return

    if not is_admin_user:
        if not db.has_active_subscription(user.id):
            await update.message.reply_text(
                "⚠️ <b>No Active Subscription!</b>\n\n"
                "You need an active subscription to use the bot.\n"
                "Buy a package for unlimited lookups!",
                reply_markup=main_menu_keyboard(), parse_mode="HTML",
            )
            return

    allowed, wait_secs = _check_rate_limit(user.id)
    if not allowed:
        rate_msg = (
            f"⏰ <b>Rate Limit!</b>\n\n"
            f"You've made {RATE_LIMIT_MAX} lookups in the last minute.\n"
            f"Please wait <b>{wait_secs}s</b> before trying again.\n\n"
            "This prevents API abuse and keeps the bot running for everyone."
        )
        await update.message.reply_text(
            rate_msg,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    phone_number = update.message.text.strip().replace(" ", "").replace("-", "").replace("+", "")

    if not phone_number or not phone_number.isdigit() or len(phone_number) < 10 or len(phone_number) > 15:
        await update.message.reply_text(
            "❌ <b>Invalid phone number!</b>\n\n"
            "Please enter a valid phone number.\n"
            "Example: <code>9876543210</code>",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    loading_msg = await update.message.reply_text(
        f"🔍 <b>Looking up</b> <code>{phone_number}</code>...\nPlease wait.",
        parse_mode="HTML",
    )

        # Single API call: numleak contains both phone info + leak data
    try:
        result_leak = await asyncio.wait_for(
            api_client.lookup_numleak(phone_number, timeout=25),
            timeout=30
        )
    except asyncio.TimeoutError:
        await loading_msg.edit_text(
            f"\u23f0 <b>Request Timeout</b>\n\n"
            f"The phone lookup for <code>{phone_number}</code> took too long.\n"
            "The API servers may be slow. Please try again later.",
            parse_mode="HTML",
        )
        return

    if isinstance(result_leak, Exception):
        logger.error(f"Numleak API exception: {result_leak}")
        result_leak = {"success": False, "error": str(result_leak)}

    logger.info(f"Numleak API: success={result_leak.get('success')}, error={result_leak.get('raw_error', result_leak.get('error'))}")

    numleak_data_raw = result_leak.get("data", {}) if result_leak.get("success") else {}

    # Check if we got useful data
    has_leak_data = bool(
        numleak_data_raw.get("chain") or numleak_data_raw.get("calltracer") or
        numleak_data_raw.get("results") or numleak_data_raw.get("data") or
        (isinstance(numleak_data_raw, dict) and len(numleak_data_raw) > 0)
    )

    logger.info(f"Data check: has_leak_data={has_leak_data}")

    if not has_leak_data:
        err_detail = result_leak.get("error", "no data") if not result_leak.get("success") else "No data found"
        await loading_msg.edit_text(
            f"\u274c <b>No data found</b> for <code>{phone_number}</code>.\n\n"
            f"Error: {err_detail}\n\n"
            "The number may not exist in the database or the API is rate limited.",
            parse_mode="HTML",
        )
        return

    if not is_admin_user:
        db.record_lookup(user.id)

    _record_lookup(user.id)

    combined_data = {
        "number": phone_number,
        "numleak_data": numleak_data_raw,
        "lookup_type": "numleak",
    }

    # Save user data to JSON store for persistence across restarts
    try:
        uds.save_user(user.id, user.username, user.first_name)
        uds.save_lookup(user.id, user.username or user.first_name, "numleak", phone_number, combined_data, True)
    except Exception as e:
        logger.warning(f"User data store save failed: {e}")

    try:
        await loading_msg.delete()
    except Exception:
        pass

    from pdf_exporter import generate_text_report, generate_osint_pdf
    
    text_report = generate_text_report(combined_data)
    code_block = f"<pre>{text_report}</pre>"
    
    if len(code_block) + 50 > MAX_MSG_LEN:
        part1 = text_report[:3800]
        part2 = text_report[3800:]
        await update.message.reply_text(
            f"<pre>{part1}</pre>",
            parse_mode="HTML",
        )
        if part2:
            await update.message.reply_text(
                f"<pre>{part2}</pre>",
                parse_mode="HTML",
            )
    else:
        await update.message.reply_text(
            code_block,
            parse_mode="HTML",
        )

    try:
        pdf_buffer = generate_osint_pdf(combined_data)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=f"OSINT_{phone_number}.pdf",
            caption=f"📄 <b>PDF Report</b> for <code>{phone_number}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        await update.message.reply_text(
            f"⚠️ PDF generation failed: {str(e)[:100]}\nText report above is still valid.",
            parse_mode="HTML",
        )

    header = (
        f"📱 <b>Lookup Complete for {phone_number}</b>\n"
        f"💰 <b>Unlimited lookups</b> — Active subscription"
    )
    await update.message.reply_text(
        header,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )

    context.user_data["last_lookup"] = combined_data

    await update.message.reply_text(
        "📥 <b>Export Report</b>\n\nTap below to download this report as a styled image.",
        reply_markup=export_keyboard(phone_number),
        parse_mode="HTML",
    )


async def handle_upi_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /upi command - Mobile number to UPI details lookup."""
    user = update.effective_user
    is_admin_user = user.id in ADMIN_IDS

    # Enforce channel join for non-admins
    if not is_admin_user:
        is_member, not_joined = await check_user_channels(user.id, context.bot)
        if not is_member:
            channel_list = "\n".join([f"• {ch}" for ch in not_joined])
            text = (
                "🔴 <b>Join Required Channels!</b>\n\n"
                "You must join the following channels:\n\n"
                f"{channel_list}\n\n"
                "After joining, tap the button below to verify."
            )
            await update.message.reply_text(
                text,
                reply_markup=required_channels_keyboard(),
                parse_mode="HTML",
            )
            return

    if db.is_banned(user.id):
        await update.message.reply_text(
            "🚫 You are <b>banned</b> from using this bot.\nContact admin for support.",
            parse_mode="HTML",
        )
        return

    if not is_admin_user:
        if not db.has_active_subscription(user.id):
            await update.message.reply_text(
                "⚠️ <b>No Active Subscription!</b>\n\n"
                "You need an active subscription to use the bot.\n"
                "Buy a package for unlimited lookups!",
                reply_markup=main_menu_keyboard(), parse_mode="HTML",
            )
            return

    allowed, wait_secs = _check_rate_limit(user.id)
    if not allowed:
        rate_msg = (
            f"⏰ <b>Rate Limit!</b>\n\n"
            f"You've made {RATE_LIMIT_MAX} lookups in the last minute.\n"
            f"Please wait <b>{wait_secs}s</b> before trying again.\n\n"
            "This prevents API abuse and keeps the bot running for everyone."
        )
        await update.message.reply_text(
            rate_msg,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    # Parse phone number from command arguments or message
    phone_number = None
    if context.args and len(context.args) > 0:
        phone_number = context.args[0].replace(" ", "").replace("-", "").replace("+", "")
    else:
        await update.message.reply_text(
            "🔍 <b>Enter Phone Number for UPI Lookup:</b>\n\n"
            "Usage: <code>/upi 9876543210</code>\n"
            "Or just type a 10-digit phone number.\n\n"
            "💡 Or tap any button to cancel.",
            parse_mode="HTML",
        )
        context.user_data["awaiting_upi"] = True
        return

    if not phone_number or not phone_number.isdigit() or len(phone_number) < 10 or len(phone_number) > 15:
        await update.message.reply_text(
            "❌ <b>Invalid phone number!</b>\n\n"
            "Please enter a valid phone number.\n"
            "Example: <code>/upi 9876543210</code>",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    loading_msg = await update.message.reply_text(
        f"🔍 <b>Looking up UPI details for</b> <code>{phone_number}</code>...\nPlease wait.",
        parse_mode="HTML",
    )

    # Fetch numtoupi data with generous timeout (APIs can be slow)
    try:
        result_upi = await asyncio.wait_for(
            api_client.lookup_numtoupi(phone_number, timeout=25),
            timeout=30
        )
    except asyncio.TimeoutError:
        await loading_msg.edit_text(
            f"⏰ <b>Request Timeout</b>\n\n"
            f"The UPI lookup for <code>{phone_number}</code> took too long.\n"
            "The API server may be slow. Please try again later.",
            parse_mode="HTML",
        )
        return

    logger.info(f"Numtoupi API: success={result_upi['success']}, error={result_upi.get('raw_error', result_upi.get('error'))}")

    if not result_upi["success"]:
        err_upi = result_upi.get('error', 'Unknown')
        await loading_msg.edit_text(
            f"❌ <b>UPI Lookup Failed</b>\n\n"
            f"Error: {err_upi}\n\n"
            "Please try again later.",
            parse_mode="HTML",
        )
        return

    upi_data_raw = result_upi.get("data", {})
    # Check for all known UPI response formats: nested (upi/account keys), flat (vpa/name keys), or any non-empty dict
    has_upi_data = bool(
        upi_data_raw.get("upi") or upi_data_raw.get("account") or 
        upi_data_raw.get("transaction") or upi_data_raw.get("data") or
        upi_data_raw.get("vpa") or upi_data_raw.get("name") or 
        upi_data_raw.get("bank") or upi_data_raw.get("upi_id") or
        upi_data_raw.get("account_holder") or
        (isinstance(upi_data_raw, dict) and len(upi_data_raw) > 0)
    )

    if not has_upi_data:
        await loading_msg.edit_text(
            f"❌ <b>No UPI data found</b> for <code>{phone_number}</code>.\n\n"
            "The number may not be linked to any UPI account or the API is rate limited.",
            parse_mode="HTML",
        )
        return

    if not is_admin_user:
        db.record_lookup(user.id)

    _record_lookup(user.id)

    combined_data = {
        "number": phone_number,
        "upi_data": upi_data_raw,
        "lookup_type": "numtoupi"
    }

    db.log_lookup(user.id, phone_number, True)
    db.save_lookup_result(user.id, phone_number, json.dumps(combined_data))

    # Save user data to JSON store for persistence across restarts
    try:
        uds.save_user(user.id, user.username, user.first_name)
        uds.save_lookup(user.id, user.username or user.first_name, "numtoupi", phone_number, combined_data, True)
    except Exception as e:
        logger.warning(f"User data store save failed: {e}")

    try:
        await loading_msg.delete()
    except Exception:
        pass

    # Generate text report
    from pdf_exporter import generate_upi_text_report
    text_report = generate_upi_text_report(combined_data)
    code_block = f"<pre>{text_report}</pre>"
    
    if len(code_block) + 50 > MAX_MSG_LEN:
        part1 = text_report[:3800]
        part2 = text_report[3800:]
        await update.message.reply_text(f"<pre>{part1}</pre>", parse_mode="HTML")
        if part2:
            await update.message.reply_text(f"<pre>{part2}</pre>", parse_mode="HTML")
    else:
        await update.message.reply_text(code_block, parse_mode="HTML")

    # Generate PDF
    try:
        from pdf_exporter import generate_upi_pdf
        pdf_buffer = generate_upi_pdf(combined_data)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=f"UPI_{phone_number}.pdf",
            caption=f"📄 <b>UPI Report</b> for <code>{phone_number}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        await update.message.reply_text(
            f"⚠️ PDF generation failed: {str(e)[:100]}\nText report above is still valid.",
            parse_mode="HTML",
        )

    header = (
        f"📱 <b>UPI Lookup Complete for {phone_number}</b>\n"
        f"💰 <b>Unlimited lookups</b> — Active subscription"
    )
    await update.message.reply_text(
        header,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )

    context.user_data["last_lookup"] = combined_data

    await update.message.reply_text(
        "📥 <b>Export Report</b>\n\nTap below to download this report as a styled image.",
        reply_markup=export_keyboard(phone_number),
        parse_mode="HTML",
    )


async def handle_vehicle_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /vehicle command - Vehicle registration details lookup."""
    user = update.effective_user
    is_admin_user = user.id in ADMIN_IDS

    # Enforce channel join for non-admins
    if not is_admin_user:
        is_member, not_joined = await check_user_channels(user.id, context.bot)
        if not is_member:
            channel_list = "\n".join([f"• {ch}" for ch in not_joined])
            text = (
                "🔴 <b>Join Required Channels!</b>\n\n"
                "You must join the following channels:\n\n"
                f"{channel_list}\n\n"
                "After joining, tap the button below to verify."
            )
            await update.message.reply_text(
                text,
                reply_markup=required_channels_keyboard(),
                parse_mode="HTML",
            )
            return

    if db.is_banned(user.id):
        await update.message.reply_text(
            "🚫 You are <b>banned</b> from using this bot.\nContact admin for support.",
            parse_mode="HTML",
        )
        return

    if not is_admin_user:
        if not db.has_active_subscription(user.id):
            await update.message.reply_text(
                "⚠️ <b>No Active Subscription!</b>\n\n"
                "You need an active subscription to use the bot.\n"
                "Buy a package for unlimited lookups!",
                reply_markup=main_menu_keyboard(), parse_mode="HTML",
            )
            return

    allowed, wait_secs = _check_rate_limit(user.id)
    if not allowed:
        rate_msg = (
            f"⏰ <b>Rate Limit!</b>\n\n"
            f"You've made {RATE_LIMIT_MAX} lookups in the last minute.\n"
            f"Please wait <b>{wait_secs}s</b> before trying again.\n\n"
            "This prevents API abuse and keeps the bot running for everyone."
        )
        await update.message.reply_text(
            rate_msg,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    # Parse vehicle plate from command arguments or message
    vehicle_plate = None
    if context.args and len(context.args) > 0:
        vehicle_plate = context.args[0].strip().upper()
    else:
        await update.message.reply_text(
            "🚗 <b>Enter Vehicle Registration Number:</b>\n\n"
            "Usage: <code>/vehicle MH12AB1234</code>\n"
            "Or just type a valid vehicle plate number.\n\n"
            "💡 Or tap any button to cancel.",
            parse_mode="HTML",
        )
        context.user_data["awaiting_vehicle"] = True
        return

    if not vehicle_plate or len(vehicle_plate) < 5 or len(vehicle_plate) > 15:
        await update.message.reply_text(
            "❌ <b>Invalid vehicle number!</b>\n\n"
            "Please enter a valid vehicle registration number.\n"
            "Example: <code>/vehicle MH12AB1234</code>",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    loading_msg = await update.message.reply_text(
        f"🚗 <b>Looking up vehicle details for</b> <code>{vehicle_plate}</code>...\nPlease wait.",
        parse_mode="HTML",
    )

    # Fetch vehicle data with generous timeout (APIs can be slow)
    try:
        result_vehicle = await asyncio.wait_for(
            api_client.lookup_vehicle(vehicle_plate, timeout=25),
            timeout=35
        )
    except asyncio.TimeoutError:
        await loading_msg.edit_text(
            f"⏰ <b>Request Timeout</b>\n\n"
            f"The vehicle lookup for <code>{vehicle_plate}</code> took too long.\n"
            "The API server may be slow. Please try again later.",
            parse_mode="HTML",
        )
        return

    logger.info(f"Vehicle API: success={result_vehicle['success']}, error={result_vehicle.get('raw_error', result_vehicle.get('error'))}")

    if not result_vehicle["success"]:
        err_vehicle = result_vehicle.get('error', 'Unknown')
        await loading_msg.edit_text(
            f"❌ <b>Vehicle Lookup Failed</b>\n\n"
            f"Error: {err_vehicle}\n\n"
            "Please try again later.",
            parse_mode="HTML",
        )
        return

    vehicle_data_raw = result_vehicle.get("data", {})
    # Check for all known vehicle response formats: nested (vehicle/owner keys), flat (regNo/owner keys), or any non-empty dict
    has_vehicle_data = bool(
        vehicle_data_raw.get("vehicle") or vehicle_data_raw.get("owner") or 
        vehicle_data_raw.get("data") or vehicle_data_raw.get("registration_number") or
        vehicle_data_raw.get("regNo") or vehicle_data_raw.get("reg_no") or
        vehicle_data_raw.get("manufacturer") or vehicle_data_raw.get("maker") or
        (isinstance(vehicle_data_raw, dict) and len(vehicle_data_raw) > 0)
    )

    if not has_vehicle_data:
        await loading_msg.edit_text(
            f"❌ <b>No vehicle data found</b> for <code>{vehicle_plate}</code>.\n\n"
            "The vehicle may not exist in the database or the API is rate limited.",
            parse_mode="HTML",
        )
        return

    if not is_admin_user:
        db.record_lookup(user.id)

    _record_lookup(user.id)

    combined_data = {
        "vehicle_plate": vehicle_plate,
        "vehicle_data": vehicle_data_raw,
        "lookup_type": "vehicle"
    }

    db.log_lookup(user.id, vehicle_plate, True)
    db.save_lookup_result(user.id, vehicle_plate, json.dumps(combined_data))

    # Save user data to JSON store for persistence across restarts
    try:
        uds.save_user(user.id, user.username, user.first_name)
        uds.save_lookup(user.id, user.username or user.first_name, "vehicle", vehicle_plate, combined_data, True)
    except Exception as e:
        logger.warning(f"User data store save failed: {e}")

    try:
        await loading_msg.delete()
    except Exception:
        pass

    # Generate text report
    from pdf_exporter import generate_vehicle_text_report
    text_report = generate_vehicle_text_report(combined_data)
    code_block = f"<pre>{text_report}</pre>"
    
    if len(code_block) + 50 > MAX_MSG_LEN:
        part1 = text_report[:3800]
        part2 = text_report[3800:]
        await update.message.reply_text(f"<pre>{part1}</pre>", parse_mode="HTML")
        if part2:
            await update.message.reply_text(f"<pre>{part2}</pre>", parse_mode="HTML")
    else:
        await update.message.reply_text(code_block, parse_mode="HTML")

    # Generate PDF
    try:
        from pdf_exporter import generate_vehicle_pdf
        pdf_buffer = generate_vehicle_pdf(combined_data)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=f"VEHICLE_{vehicle_plate}.pdf",
            caption=f"📄 <b>Vehicle Report</b> for <code>{vehicle_plate}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        await update.message.reply_text(
            f"⚠️ PDF generation failed: {str(e)[:100]}\nText report above is still valid.",
            parse_mode="HTML",
        )

    header = (
        f"🚗 <b>Vehicle Lookup Complete for {vehicle_plate}</b>\n"
        f"💰 <b>Unlimited lookups</b> — Active subscription"
    )
    await update.message.reply_text(
        header,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )

    context.user_data["last_lookup"] = combined_data

    await update.message.reply_text(
        "📥 <b>Export Report</b>\n\nTap below to download this report as a styled image.",
        reply_markup=export_keyboard(vehicle_plate),
        parse_mode="HTML",
    )


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user lookup history with re-export options."""
    user = update.effective_user
    lookups = db.get_user_lookup_history(user.id, limit=10)

    if not lookups:
        text = (
            "📋 <b>Lookup History</b>\n\n"
            "No lookups yet.\n"
            "Do a lookup first, then you can re-export past reports here."
        )
        await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
        return

    text = (
        "📋 <b>Lookup History</b>\n\n"
        "Tap a lookup to re-export it (no credits needed):"
    )
    await update.message.reply_text(
        text,
        reply_markup=history_list_keyboard(lookups),
        parse_mode="HTML",
    )


async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment screenshot upload."""
    user = update.effective_user
    awaiting = context.user_data.get("awaiting_screenshot")

    if not awaiting or awaiting not in SUBSCRIPTION_PACKAGES:
        return

    pkg = SUBSCRIPTION_PACKAGES[awaiting]
    screenshot_file_id = None

    if update.message.photo:
        screenshot_file_id = update.message.photo[-1].file_id
    elif update.message.document:
        screenshot_file_id = update.message.document.file_id
    else:
        await update.message.reply_text(
            "❌ Please send a <b>photo</b> or <b>document</b> screenshot.",
            parse_mode="HTML",
        )
        return

    tx_id = db.create_transaction(user.id, awaiting, pkg["duration_hours"], pkg["price"], screenshot_file_id)

    # Save payment to unified JSON store
    try:
        uds.save_payment(user.id, user.username or user.first_name, awaiting, pkg["price"], "pending", tx_id)
    except Exception as e:
        logger.warning(f"JSON store save_payment failed: {e}")

    context.user_data.pop("awaiting_screenshot", None)
    context.user_data.pop("pending_package", None)

    await update.message.reply_text(
        f"⏳ <b>Payment Screenshot Received!</b>\n\n"
        f"Package: <b>{pkg['label']}</b>\n"
        f"Amount: ₹{pkg['price']}\n"
        f"📢 Transaction ID: <code>#{tx_id}</code>\n\n"
        "Your payment is being verified by an admin.\n"
        "You will be notified once it's approved.\n\n"
        "This usually takes a few minutes.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )

    from keyboards import admin_approve_keyboard
    for admin_id in ADMIN_IDS:
        try:
            admin_text = (
                f"📢 <b>New Payment - Pending Approval</b>\n\n"
                f"User: <b>{user.first_name}</b> (@{user.username or 'N/A'})\n"
                f"User ID: <code>{user.id}</code>\n"
                f"Package: <b>{pkg['label']}</b>\n"
                f"Amount: ₹{pkg['price']}\n"
                f"Duration: {pkg['label']}\n"
                f"Transaction: <code>#{tx_id}</code>\n\n"
                "Review the screenshot and approve or reject:"
            )
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=screenshot_file_id,
                caption=admin_text,
                reply_markup=admin_approve_keyboard(tx_id),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
            try:
                await context.bot.send_message(
                    admin_id,
                    f"📢 <b>New Payment - Pending Approval</b>\n\n"
                    f"User: <b>{user.first_name}</b> (@{user.username or 'N/A'})\n"
                    f"User ID: <code>{user.id}</code>\n"
                    f"Package: <b>{pkg['label']}</b>\n"
                    f"Amount: ₹{pkg['price']}\n"
                    f"Transaction: <code>#{tx_id}</code>\n\n"
                    f"Approve: /approve_{tx_id}\n"
                    f"Reject: /reject_{tx_id}",
                    parse_mode="HTML",
                )
            except Exception:
                pass

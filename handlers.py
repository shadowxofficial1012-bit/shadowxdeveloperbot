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
from config import SUBSCRIPTION_PACKAGES, UPI_ID, UPI_NAME, FREE_TRIAL_HOURS, QR_CODE_PATH, LOGO_PATH, BRAND_NAME, BRAND_TAGLINE, ADMIN_IDS, REQUIRED_CHANNELS


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
    # Send QR code image if available
    if os.path.exists(QR_CODE_PATH):
        try:
            await update.message.reply_photo(
                photo=QR_CODE_PATH,
                caption=text,
                reply_markup=buy_plan_keyboard(),
                parse_mode="HTML",
            )
            return
        except Exception as e:
            logger.error(f"Failed to send QR code: {e}")
    # Fallback: text only
    await update.message.reply_text(text, reply_markup=buy_plan_keyboard(), parse_mode="HTML")


# --- Admin Payment Approve/Reject Helpers ---

async def _approve_transaction(tx_id: int, context, query=None):
    """Approve a transaction: update status, activate subscription, notify user."""
    db.update_transaction_status(tx_id, "approved")

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

    # Call BOTH endpoints in parallel for complete data:
    # /api/number  -> detailed records (name, address, SIM, etc.)
    # /api/numleak -> breach/leak data + calltracer
    result_number, result_leak = await asyncio.gather(
        api_client.lookup_number(phone_number, timeout=10),
        api_client.lookup_numleak(phone_number, timeout=10),
        return_exceptions=True,
    )

    # Handle exceptions from gather (return_exceptions=True wraps them)
    if isinstance(result_number, Exception):
        logger.error(f"Number API exception: {result_number}")
        result_number = {"success": False, "error": str(result_number)}
    if isinstance(result_leak, Exception):
        logger.error(f"Numleak API exception: {result_leak}")
        result_leak = {"success": False, "error": str(result_leak)}

    logger.info(f"Number API: success={result_number.get('success')}, error={result_number.get('error')}")
    logger.info(f"Numleak API: success={result_leak.get('success')}, error={result_leak.get('error')}")

    # Extract raw data from both endpoints
    number_data_raw = result_number.get("data", {}) if result_number.get("success") else {}
    numleak_data_raw = result_leak.get("data", {}) if result_leak.get("success") else {}

    # Handle nested response formats: {"data": {"results": [...]}} or {"results": [...]
    if not number_data_raw.get("results") and number_data_raw.get("data"):
        nested = number_data_raw["data"]
        if isinstance(nested, dict) and nested.get("results"):
            number_data_raw = nested  # unwrap nested data

    # Check if we got ANY useful data from either endpoint
    has_number_data = bool(number_data_raw.get("results"))
    has_leak_data = bool(numleak_data_raw.get("chain") or numleak_data_raw.get("calltracer"))

    logger.info(f"Data check: has_number_data={has_number_data}, has_leak_data={has_leak_data}")

    # If data is not in expected keys, check if data exists at all
    if not has_number_data and number_data_raw and isinstance(number_data_raw, dict) and len(number_data_raw) > 0:
        # The API returned something, just not in the expected nested format
        # Mark as data found so we still display it
        has_number_data = True

    if not has_leak_data and numleak_data_raw and isinstance(numleak_data_raw, dict) and len(numleak_data_raw) > 0:
        has_leak_data = True

    if not has_number_data and not has_leak_data:
        # Both endpoints failed or returned no data
        err_msgs = []
        if not result_number.get("success"):
            err_msgs.append(f"Number API: {result_number.get('error', 'no data')}")
        if not result_leak.get("success"):
            err_msgs.append(f"Numleak API: {result_leak.get('error', 'no data')}")
        err_detail = " | ".join(err_msgs) if err_msgs else "Unknown"
        await loading_msg.edit_text(
            f"❌ <b>No data found</b> for <code>{phone_number}</code>.\n\n"
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
        "number_data": number_data_raw,
        "numleak_data": numleak_data_raw,
        "lookup_type": "numleak",
    }

    db.log_lookup(user.id, phone_number, True)
    db.save_lookup_result(user.id, phone_number, json.dumps(combined_data))

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

    # Fetch numtoupi data with 10-second timeout
    try:
        result_upi = await asyncio.wait_for(
            api_client.lookup_numtoupi(phone_number),
            timeout=10
        )
    except asyncio.TimeoutError:
        await loading_msg.edit_text(
            f"⏰ <b>Request Timeout</b>\n\n"
            f"The lookup for <code>{phone_number}</code> timed out after 10 seconds.\n"
            "Please try again later or contact @HATHI02.",
            parse_mode="HTML",
        )
        return

    logger.info(f"Numtoupi API: success={result_upi['success']}, error={result_upi.get('error')}")

    if not result_upi["success"]:
        err_upi = result_upi.get('error', 'Unknown')
        await loading_msg.edit_text(
            f"❌ <b>Lookup Failed</b>\n\n"
            f"Error: {err_upi}\n\n"
            "Please try again later or contact @HATHI02.",
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

    # Fetch vehicle data with 10-second timeout
    try:
        result_vehicle = await asyncio.wait_for(
            api_client.lookup_vehicle(vehicle_plate),
            timeout=10
        )
    except asyncio.TimeoutError:
        await loading_msg.edit_text(
            f"⏰ <b>Request Timeout</b>\n\n"
            f"The lookup for <code>{vehicle_plate}</code> timed out after 10 seconds.\n"
            "Please try again later or contact @HATHI02.",
            parse_mode="HTML",
        )
        return

    logger.info(f"Vehicle API: success={result_vehicle['success']}, error={result_vehicle.get('error')}")

    if not result_vehicle["success"]:
        err_vehicle = result_vehicle.get('error', 'Unknown')
        await loading_msg.edit_text(
            f"❌ <b>Lookup Failed</b>\n\n"
            f"Error: {err_vehicle}\n\n"
            "Please try again later or contact @HATHI02.",
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

import logging
import json
import time
import asyncio
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes

import database as db
import api_client
from keyboards import (
    main_menu_keyboard,
    buy_credits_keyboard,
    confirm_payment_keyboard,
    back_button,
    export_keyboard,
    history_list_keyboard,
    reexport_keyboard,
)
from config import CREDIT_PACKAGES, UPI_ID, UPI_NAME, FREE_CREDITS, QR_CODE_PATH, LOGO_PATH, BRAND_NAME, BRAND_TAGLINE, ADMIN_IDS

logger = logging.getLogger(__name__)

# Max Telegram message length
MAX_MSG_LEN = 4096
MAX_CAPTION_LEN = 1024

# --- Rate Limiting ---
# Max lookups per user within the sliding window
RATE_LIMIT_MAX = 5
# Sliding window duration in seconds (1 minute)
RATE_LIMIT_WINDOW = 60
# Stores {user_id: [timestamp, timestamp, ...]}
_rate_limit_tracker: dict[int, list[float]] = defaultdict(list)


def _check_rate_limit(user_id: int) -> tuple[bool, int]:
    """
    Check if a user is within the rate limit.
    Returns (is_allowed, seconds_until_next_slot).
    """
    now = time.time()
    # Remove timestamps older than the window
    _rate_limit_tracker[user_id] = [
        ts for ts in _rate_limit_tracker[user_id] if now - ts < RATE_LIMIT_WINDOW
    ]
    if len(_rate_limit_tracker[user_id]) >= RATE_LIMIT_MAX:
        # Oldest timestamp in the window determines when a slot frees up
        oldest = _rate_limit_tracker[user_id][0]
        wait = int(RATE_LIMIT_WINDOW - (now - oldest)) + 1
        return False, wait
    return True, 0


def _record_lookup(user_id: int):
    """Record a lookup timestamp for rate limiting."""
    _rate_limit_tracker[user_id].append(time.time())


def safe_str(val, default="N/A") -> str:
    """Safely convert a value to string, returning default if None/empty."""
    if val is None or val == "":
        return default
    return str(val)


def escape_html(text: str) -> str:
    """Escape HTML special characters for safe Telegram rendering."""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_number(n):
    """Format a number with commas."""
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

    is_new = db_user["total_lookups"] == 0 and db_user["credits"] == FREE_CREDITS

    # Try to send branded header image
    try:
        from header import generate_header_image
        header_img = generate_header_image(
            brand_name=BRAND_NAME,
            tagline=BRAND_TAGLINE,
            logo_path=LOGO_PATH,
            credits=db_user["credits"],
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
    welcome = (
        f"\U0001f44b Welcome, <b>{user.first_name}</b>!\n\n"
        f"\U0001f50d <b>Phone OSINT by @HATHI02</b>\n"
        "Get detailed information about any phone number.\n\n"
    )

    if is_new:
        welcome += f"\U0001f381 You received <b>{FREE_CREDITS} FREE credits</b> to get started!\n\n"

    credits_display = "\u221e Unlimited" if is_admin_user else str(db_user['credits'])
    welcome += (
        f"\U0001f4b0 <b>Your Balance:</b> {credits_display} credits\n\n"
    )

    if is_admin_user:
        welcome += "\U0001f3f7\ufe0f Admin: Send <code>/admin</code> to access panel\n\n"

    welcome += "Choose an option below \u2193"

    await update.message.reply_text(
        welcome,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    is_admin_user = update.effective_user.id in ADMIN_IDS
    text = (
        "\U0001f4d6 <b>Phone OSINT Bot by @HATHI02</b>\n\n"
        "\U0001f50d <b>Phone Lookup</b>\n"
        "1. Tap 'Phone Lookup' button\n"
        "2. Enter the phone number (e.g., 9876543210)\n"
        "3. Get detailed OSINT data instantly!\n\n"
        "\U0001f4b3 <b>Buy Credits</b>\n"
        "1. Tap 'Buy Credits' button\n"
        "2. Choose a package\n"
        "3. Send payment to the UPI ID shown\n"
        "4. Upload payment screenshot\n"
        "5. Credits added instantly!\n\n"
        "\U0001f4b0 <b>Check Balance</b>\n"
        "Tap 'My Balance' to see your current credits.\n\n"
        "\U0001f4cb <b>History</b>\n"
        "Tap 'My History' to see your past lookups.\n\n"
        "\U0001f6e1\ufe0f Each lookup costs <b>1 credit</b>.\n\n"
    )
    if is_admin_user:
        text += "\U0001f3f7\ufe0f <b>Admin:</b> Send <code>/admin</code> to access panel\n\n"
    text += "For support, contact @HATHI02."
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user profile."""
    user = update.effective_user
    db_user = db.get_or_create_user(user.id, user.username, user.first_name)

    text = (
        "\U0001f464 <b>Your Profile</b>\n\n"
        f"<b>Name:</b> {db_user['first_name'] or 'N/A'}\n"
        f"<b>Username:</b> @{db_user['username'] or 'N/A'}\n"
        f"<b>User ID:</b> <code>{db_user['user_id']}</code>\n"
        f"<b>Credits:</b> {db_user['credits']}\n"
        f"<b>Total Lookups:</b> {db_user['total_lookups']}\n"
        f"<b>Member Since:</b> {db_user['created_at'][:10]}"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user balance."""
    user = update.effective_user
    db.get_or_create_user(user.id, user.username, user.first_name)
    credits = db.get_credits(user.id)
    is_admin_user = user.id in ADMIN_IDS

    if is_admin_user:
        text = "\U0001f4b0 <b>Your Balance</b>\n\n"
        text += "\U0001f4b5 <b>Available Credits:</b> <b>\u221e Unlimited</b>\n\n"
        text += "\u2705 Admin account — unlimited lookups."
    else:
        text = "\U0001f4b0 <b>Your Balance</b>\n\n"
        text += f"\U0001f4b5 <b>Available Credits:</b> <b>{credits}</b>\n\n"

        if credits <= 0:
            text += "\u26a0\ufe0f You have <b>no credits</b> left!\nBuy more credits to continue."
        elif credits <= 1:
            text += "\u26a0\ufe0f Very few credits left. Consider buying more."
        else:
            text += f"You can perform <b>{credits}</b> more lookups."

    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def tx_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user transaction history."""
    user = update.effective_user
    txs = db.get_user_transactions(user.id, limit=10)

    if not txs:
        text = "\U0001f4cb <b>Transaction History</b>\n\nNo transactions yet."
    else:
        text = "\U0001f4cb <b>Transaction History</b>\n\n"
        for tx in txs:
            icon = "\u2705" if tx["status"] == "approved" else "\u23f3" if tx["status"] == "pending" else "\u274c"
            text += (
                f"{icon} <b>{tx['package'].title()}</b> \u2014 "
                f"+{tx['credits_added']} credits \u2022 \u20b9{tx['amount']}\n"
                f"   \U0001f4c5 {tx['created_at'][:16]}\n\n"
            )

    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def buy_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show credit packages with QR code."""
    import os
    text = (
        "\U0001f4b3 <b>Buy Credits</b>\n\n"
        "Choose a package below:\n\n"
        f"\U0001f4b5 <b>UPI ID:</b> <code>{UPI_ID}</code>\n"
        f"\U0001f464 <b>Name:</b> {UPI_NAME}\n\n"
        "\U0001f4b0 Each credit = 1 Phone Lookup\n"
        "\U0001f510 Send payment, then upload screenshot to confirm."
    )
    # Send QR code image if available
    if os.path.exists(QR_CODE_PATH):
        try:
            await update.message.reply_photo(
                photo=QR_CODE_PATH,
                caption=text,
                reply_markup=buy_credits_keyboard(),
                parse_mode="HTML",
            )
            return
        except Exception as e:
            logger.error(f"Failed to send QR code: {e}")
    # Fallback: text only
    await update.message.reply_text(text, reply_markup=buy_credits_keyboard(), parse_mode="HTML")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline button callbacks."""
    query = update.callback_query
    data = query.data
    await query.answer()

    user = query.from_user

    # Back to main menu
    if data == "back_main":
        db_user = db.get_or_create_user(user.id, user.username, user.first_name)
        credits_text = "\u221e" if user.id in ADMIN_IDS else str(db_user['credits'])
        text = (
            f"\U0001f44b Hey, <b>{user.first_name}</b>!\n\n"
            f"\U0001f4b0 <b>Your Balance:</b> {credits_text} credits\n\n"
            "Choose an option \u2193"
        )
        await query.edit_message_text(text, reply_markup=back_button(), parse_mode="HTML")
        return

    # Buy credits package selection
    if data.startswith("buy_"):
        package_key = data.replace("buy_", "")
        if package_key not in CREDIT_PACKAGES:
            await query.edit_message_text("Invalid package.", reply_markup=back_button())
            return

        pkg = CREDIT_PACKAGES[package_key]
        text = (
            f"\U0001f4b3 <b>{pkg['label']}</b>\n\n"
            f"\U0001f4b5 <b>Price:</b> \u20b9{pkg['price']}\n"
            f"\U0001f4b0 <b>Credits:</b> {pkg['credits']}\n\n"
            f"\U0001f4b3 <b>Send payment to:</b>\n"
            f"<code>{UPI_ID}</code>\n"
            f"Name: {UPI_NAME}\n\n"
            "After payment, send a screenshot of the payment confirmation.\n"
            "Include your <b>User ID</b> in the payment reference."
        )
        context.user_data["pending_package"] = package_key
        await query.edit_message_text(text, reply_markup=confirm_payment_keyboard(package_key), parse_mode="HTML")
        return

    # Confirm payment - awaiting screenshot
    if data.startswith("confirm_"):
        package_key = data.replace("confirm_", "")
        if package_key not in CREDIT_PACKAGES:
            await query.edit_message_text("Invalid package.", reply_markup=back_button())
            return
        context.user_data["awaiting_screenshot"] = package_key
        pkg = CREDIT_PACKAGES[package_key]
        await query.edit_message_text(
            f"\U0001f4f8 <b>Send payment screenshot</b>\n\n"
            f"You selected: <b>{pkg['label']}</b> (\u20b9{pkg['price']})\n\n"
            "Upload the payment confirmation screenshot now.\n"
            "Make sure the screenshot shows:\n"
            "\u2022 UPI ID paid to\n"
            "\u2022 Amount\n"
            "\u2022 Transaction reference/ID",
            parse_mode="HTML",
        )
        return

    # Cancel payment
    if data == "cancel_payment":
        context.user_data.pop("awaiting_screenshot", None)
        context.user_data.pop("pending_package", None)
        await query.edit_message_text(
            "\u274c Payment cancelled.\n\nChoose an option:",
            reply_markup=back_button(),
        )
        return

    # Admin: Approve transaction
    if data.startswith("approve_"):
        tx_id = int(data.replace("approve_", ""))
        db.update_transaction_status(tx_id, "approved")

        conn = db.get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
        row = c.fetchone()
        conn.close()

        if row:
            tx = dict(row)
            db.add_credits(tx["user_id"], tx["credits_added"])
            try:
                await context.bot.send_message(
                    tx["user_id"],
                    f"\u2705 <b>Payment Approved!</b>\n\n"
                    f"+{tx['credits_added']} credits added.\n"
                    f"Balance: {db.get_credits(tx['user_id'])} credits",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        await query.edit_message_text(
            f"\u2705 <b>Transaction #{tx_id} Approved</b>\n"
            f"Credits added: {tx['credits_added'] if row else 'N/A'}",
            parse_mode="HTML",
        )
        return

    # Admin: Reject transaction
    if data.startswith("reject_"):
        tx_id = int(data.replace("reject_", ""))
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
                    f"\u274c <b>Payment Rejected</b>\n\n"
                    f"Package: {tx['package'].title()}\n"
                    "Contact admin for support.",
                    parse_mode="HTML",
                )
            except Exception:
                pass

        await query.edit_message_text(f"\u274c <b>Transaction #{tx_id} Rejected</b>", parse_mode="HTML")
        return

    # Admin: Confirm ban
    if data.startswith("doban_"):
        ban_uid = int(data.replace("doban_", ""))
        db.ban_user(ban_uid)
        await query.edit_message_text(
            f"\U0001f6ab User <code>{ban_uid}</code> has been banned.",
            parse_mode="HTML",
        )
        return

    # Cancel action
    if data == "cancel_action":
        await query.edit_message_text("\u274c Action cancelled.", reply_markup=back_button())
        return

    # Export report as image + PDF
    if data.startswith("export_"):
        export_number = data.replace("export_", "")
        lookup_data = context.user_data.get("last_lookup")
        if not lookup_data:
            await query.edit_message_text(
                "\u274c No data to export. Please run a lookup first.",
                reply_markup=back_button(),
            )
            return

        await query.answer("\U0001f4f7 Generating reports...")

        # Send image report
        try:
            from exporter import generate_report_image
            image_buffer = generate_report_image(lookup_data)
            await context.bot.send_photo(
                chat_id=query.message.chat.id,
                photo=image_buffer,
                caption=f"\U0001f4f7 <b>Image Report</b> for {export_number}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Image export failed: {e}")

        # Send PDF report
        try:
            from pdf_exporter import generate_osint_pdf
            pdf_buffer = generate_osint_pdf(lookup_data)
            await context.bot.send_document(
                chat_id=query.message.chat.id,
                document=pdf_buffer,
                filename=f"OSINT_{export_number}.pdf",
                caption=f"\U0001f4c4 <b>PDF Report</b> for {export_number}",
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
                "\U0001f4cb <b>No lookups yet.</b>\nDo a lookup first!",
                reply_markup=back_button(),
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text(
                "\U0001f4cb <b>Tap to re-export (no credits):</b>",
                reply_markup=history_list_keyboard(lookups),
                parse_mode="HTML",
            )
        return

    # Re-export: show re-export options
    if data.startswith("reexport_") and not data.startswith("reexportimg_"):
        lookup_id = int(data.replace("reexport_", ""))
        cached = db.get_lookup_by_id(lookup_id, user.id)
        if not cached:
            await query.edit_message_text("\u274c Lookup not found.", reply_markup=back_button())
            return
        await query.edit_message_text(
            f"\U0001f4f1 Re-export <b>{cached['username']}</b>\n\n"
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
            await query.edit_message_text("\u274c Lookup not found.", reply_markup=back_button())
            return

        await query.answer("\U0001f4f7 Generating report...")

        try:
            import json as _json
            lookup_data = _json.loads(cached["api_data"])
            from exporter import generate_report_image
            image_buffer = generate_report_image(lookup_data)
            await context.bot.send_photo(
                chat_id=query.message.chat.id,
                photo=image_buffer,
                caption=f"\U0001f4f7 <b>Re-exported Report</b> for {cached['username']}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Re-export failed: {e}")
            await query.edit_message_text(
                f"\u274c <b>Export failed</b>\n\nError: {str(e)[:200]}",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML",
            )
        return


async def demo_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a demo result so users can see how output looks."""
    from pdf_exporter import generate_text_report, generate_osint_pdf
    
    demo_data = {
        "number": "9876543210",
        "number_data": {
            "results": [{
                "name": "Rahul Kumar",
                "fname": "Suresh Kumar",
                "mobile": "9876543210",
                "alt": "9123456789",
                "email": "N/A",
                "circle": "DELHI NCR",
                "address": "123 MG Road, Connaught Place, New Delhi, Delhi 110001",
                "id": "DEMO12345"
            }],
            "total": 1,
            "by": "@ftgamer2",
            "channel": "https://t.me/lynx_api"
        },
        "numleak_data": {
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
    
    # Send demo text report
    text_report = generate_text_report(demo_data)
    await update.message.reply_text(
        f"<pre>{text_report}</pre>",
        parse_mode="HTML",
    )
    
    # Send demo PDF
    try:
        pdf_buffer = generate_osint_pdf(demo_data)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename="DEMO_OSINT_REPORT.pdf",
            caption="\U0001f4c4 <b>Demo PDF Report</b>\nThis is how your reports will look.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Demo PDF failed: {e}")
    
    await update.message.reply_text(
        "\u2139\ufe0f <b>That was a demo!</b>\n"
        "Enter a real phone number to get actual OSINT data.\n"
        "Tap 'Phone Lookup' to start.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


async def handle_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone number lookup with full code-formatted output."""
    user = update.effective_user
    is_admin_user = user.id in ADMIN_IDS

    # Check if banned
    if db.is_banned(user.id):
        await update.message.reply_text(
            "\U0001f6ab You are <b>banned</b> from using this bot.\nContact admin for support.",
            parse_mode="HTML",
        )
        return

    # Check credits (admins skip credit check)
    if not is_admin_user:
        credits = db.get_credits(user.id)
        if credits <= 0:
            await update.message.reply_text(
                "\u26a0\ufe0f <b>No Credits!</b>\n\n"
                "You have no credits left.\n"
                "Buy more credits to continue using the bot.",
                reply_markup=main_menu_keyboard(), parse_mode="HTML",
            )
            return

    # Rate limit check
    allowed, wait_secs = _check_rate_limit(user.id)
    if not allowed:
        rate_msg = (
            f"\u23f0 <b>Rate Limit!</b>\n\n"
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

    # Extract phone number from message
    phone_number = update.message.text.strip().replace(" ", "").replace("-", "").replace("+", "")

    # Validate - only digits, 10-15 characters
    if not phone_number or not phone_number.isdigit() or len(phone_number) < 10 or len(phone_number) > 15:
        await update.message.reply_text(
            "\u274c <b>Invalid phone number!</b>\n\n"
            "Please enter a valid phone number.\n"
            "Example: <code>9876543210</code>",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    # Show loading
    loading_msg = await update.message.reply_text(
        f"\U0001f50d <b>Looking up</b> <code>{phone_number}</code>...\nPlease wait.",
        parse_mode="HTML",
    )

    # Call both APIs in parallel
    result_num, result_leak = await asyncio.gather(
        api_client.lookup_number(phone_number),
        api_client.lookup_numleak(phone_number),
    )

    # Check if at least one API succeeded
    logger.info(f"Number API: success={result_num['success']}, error={result_num.get('error')}")
    logger.info(f"Numleak API: success={result_leak['success']}, error={result_leak.get('error')}")

    if not result_num["success"] and not result_leak["success"]:
        err_num = result_num.get('error', 'Unknown')
        err_leak = result_leak.get('error', 'Unknown')
        await loading_msg.edit_text(
            f"\u274c <b>Lookup Failed</b>\n\n"
            f"Number API: {err_num}\n"
            f"Numleak API: {err_leak}\n\n"
            "Please try again later or contact @HATHI02.",
            parse_mode="HTML",
        )
        return

    # Check if we got any data (numleak has chain OR calltracer)
    num_data = result_num.get("data", {}) if result_num["success"] else {}
    numleak_data_raw = result_leak.get("data", {}) if result_leak["success"] else {}
    has_num_data = bool(num_data.get("results"))
    has_leak_data = bool(numleak_data_raw.get("chain") or numleak_data_raw.get("calltracer"))

    logger.info(f"Data check: has_num_data={has_num_data}, has_leak_data={has_leak_data}")
    logger.info(f"num_data keys={list(num_data.keys()) if num_data else 'empty'}")
    logger.info(f"numleak_data keys={list(numleak_data_raw.keys()) if numleak_data_raw else 'empty'}")

    if not has_num_data and not has_leak_data:
        # Show what we actually got for debugging
        details = []
        if result_num["success"] and num_data:
            details.append(f"Number API: got response with keys {list(num_data.keys())}")
        if result_leak["success"] and numleak_data_raw:
            details.append(f"Numleak API: got response with keys {list(numleak_data_raw.keys())}")
        detail_str = "\n".join(details) if details else "APIs returned empty data."
        await loading_msg.edit_text(
            f"\u274c <b>No data found</b> for <code>{phone_number}</code>.\n\n"
            f"{detail_str}\n\n"
            "The number may not exist in the database or the API is rate limited.",
            parse_mode="HTML",
        )
        return

    # Use one credit (admins skip credit deduction)
    if not is_admin_user:
        if not db.use_credit(user.id):
            await loading_msg.edit_text(
                "\u26a0\ufe0f <b>Credits exhausted</b> during lookup.\nBuy more credits.",
                parse_mode="HTML",
            )
            return

    # Record this lookup for rate limiting
    _record_lookup(user.id)

    # Merge data for storage
    combined_data = {
        "number": phone_number,
        "number_data": result_num.get("data", {}),
        "numleak_data": result_leak.get("data", {}),
    }

    db.log_lookup(user.id, phone_number, True)
    # Save full API response for re-export
    db.save_lookup_result(user.id, phone_number, json.dumps(combined_data))

    try:
        await loading_msg.delete()
    except Exception:
        pass

    # PART 1: Send hacker-style text report
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

    # PART 2: Send PDF report
    try:
        pdf_buffer = generate_osint_pdf(combined_data)
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=pdf_buffer,
            filename=f"OSINT_{phone_number}.pdf",
            caption=f"\U0001f4c4 <b>PDF Report</b> for <code>{phone_number}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        await update.message.reply_text(
            f"\u26a0\ufe0f PDF generation failed: {str(e)[:100]}\nText report above is still valid.",
            parse_mode="HTML",
        )

    # PART 3: Summary header
    credits_remaining = "\u221e" if is_admin_user else str(db.get_credits(user.id))
    header = (
        f"\U0001f4f1 <b>Lookup Complete for {phone_number}</b>\n"
        f"Credits remaining: <b>{credits_remaining}</b>"
    )
    await update.message.reply_text(
        header,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )

    # Store data for export
    context.user_data["last_lookup"] = combined_data

    # PART 4: Export button
    await update.message.reply_text(
        "\U0001f4e5 <b>Export Report</b>\n\nTap below to download this report as a styled image.",
        reply_markup=export_keyboard(phone_number),
        parse_mode="HTML",
    )


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user lookup history with re-export options."""
    user = update.effective_user
    lookups = db.get_user_lookup_history(user.id, limit=10)

    if not lookups:
        text = (
            "\U0001f4cb <b>Lookup History</b>\n\n"
            "No lookups yet.\n"
            "Do a lookup first, then you can re-export past reports here."
        )
        await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
        return

    text = (
        "\U0001f4cb <b>Lookup History</b>\n\n"
        "Tap a lookup to re-export it (no credits needed):"
    )
    await update.message.reply_text(
        text,
        reply_markup=history_list_keyboard(lookups),
        parse_mode="HTML",
    )


async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment screenshot upload - auto-approve payments."""
    user = update.effective_user
    awaiting = context.user_data.get("awaiting_screenshot")

    if not awaiting or awaiting not in CREDIT_PACKAGES:
        return

    pkg = CREDIT_PACKAGES[awaiting]
    screenshot_file_id = None

    if update.message.photo:
        screenshot_file_id = update.message.photo[-1].file_id
    elif update.message.document:
        screenshot_file_id = update.message.document.file_id
    else:
        await update.message.reply_text(
            "\u274c Please send a <b>photo</b> or <b>document</b> screenshot.",
            parse_mode="HTML",
        )
        return

    # Create transaction and auto-approve
    tx_id = db.create_transaction(user.id, awaiting, pkg["credits"], pkg["price"], screenshot_file_id)
    db.update_transaction_status(tx_id, "approved")
    db.add_credits(user.id, pkg["credits"])

    context.user_data.pop("awaiting_screenshot", None)
    context.user_data.pop("pending_package", None)

    await update.message.reply_text(
        f"\u2705 <b>Payment Approved!</b>\n\n"
        f"Package: <b>{pkg['label']}</b>\n"
        f"Amount: \u20b9{pkg['price']}\n"
        f"+{pkg['credits']} credits added\n"
        f"Balance: <b>{db.get_credits(user.id)}</b> credits\n\n"
        "You can now use the bot!",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )

    # Notify admins (for record keeping)
    from config import ADMIN_IDS
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id,
                f"\U0001f4e2 <b>Auto-Approved Payment</b>\n\n"
                f"User: <b>{user.first_name}</b> (@{user.username or 'N/A'})\n"
                f"User ID: <code>{user.id}</code>\n"
                f"Package: <b>{pkg['label']}</b>\n"
                f"+{pkg['credits']} credits",
                parse_mode="HTML",
            )
        except Exception:
            pass

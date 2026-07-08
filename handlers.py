import logging
import json
import time
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
from config import CREDIT_PACKAGES, UPI_ID, UPI_NAME, FREE_CREDITS, QR_CODE_PATH, LOGO_PATH, BRAND_NAME, BRAND_TAGLINE

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


def build_osint_report(data: dict) -> str:
    """Build a beautifully formatted OSINT report from API response data."""
    profile = data.get("profile", {})
    osint = data.get("osint", {})
    osint_note = data.get("osint_note", "")

    lines = []
    lines.append("========================================")
    lines.append("  INSTAGRAM OSINT REPORT")
    lines.append("========================================")
    lines.append("")

    # Profile Section
    lines.append("[PROFILE INFO]")
    lines.append("----------------------------------------")
    lines.append(f"  Username    : @{safe_str(profile.get('username'))}")
    lines.append(f"  Full Name   : {escape_html(safe_str(profile.get('full_name')))}")

    verified = "[VERIFIED]" if profile.get("is_verified") else "[NOT VERIFIED]"
    lines.append(f"  Verified    : {verified}")

    private = "[PRIVATE]" if profile.get("is_private") else "[PUBLIC]"
    lines.append(f"  Account     : {private}")

    if profile.get("is_business_account"):
        lines.append("  Type        : Business Account")
    elif profile.get("is_professional_account"):
        lines.append("  Type        : Professional Account")
    else:
        lines.append("  Type        : Personal Account")

    if profile.get("category_name"):
        lines.append(f"  Category    : {escape_html(str(profile['category_name']))}")
    if profile.get("business_category_name"):
        lines.append(f"  Business    : {escape_html(str(profile['business_category_name']))}")

    lines.append("")

    # Stats Section
    lines.append("[STATISTICS]")
    lines.append("----------------------------------------")
    lines.append(f"  Followers   : {format_number(profile.get('followers', 0))}")
    lines.append(f"  Following   : {format_number(profile.get('following', 0))}")
    lines.append(f"  Posts       : {format_number(profile.get('posts', 0))}")
    if profile.get("estimated_creation_year"):
        lines.append(f"  Created     : ~{profile['estimated_creation_year']}")
    if profile.get("id"):
        lines.append(f"  Account ID  : {profile['id']}")
    lines.append("")

    # Bio Section
    bio = profile.get("biography", "")
    if bio:
        lines.append("[BIOGRAPHY]")
        lines.append("----------------------------------------")
        lines.append(f"  {escape_html(bio[:300])}")
        lines.append("")

    # External URL
    url = profile.get("external_url", "")
    if url:
        lines.append(f"[WEBSITE]")
        lines.append(f"  {url}")
        lines.append("")

    # Profile Picture
    pfp = profile.get("pfp", "")
    if pfp:
        lines.append("[PROFILE PICTURE]")
        lines.append(f"  {pfp[:150]}")
        lines.append("")

    # OSINT Data Section
    lines.append("[OSINT LEAKED DATA]")
    lines.append("========================================")

    if osint.get("available") and osint.get("records"):
        lines.append(f"  Status: DATA AVAILABLE ({len(osint['records'])} records found)")
        lines.append("")
        for i, record in enumerate(osint["records"], 1):
            lines.append(f"  --- Record #{i} ---")
            if record.get("id"):
                lines.append(f"  ID       : {record['id']}")
            if record.get("username"):
                lines.append(f"  Username : {escape_html(str(record['username']))}")
            if record.get("name"):
                lines.append(f"  Name     : {escape_html(str(record['name']))}")
            if record.get("email"):
                lines.append(f"  Email    : {escape_html(str(record['email']))}")
            if record.get("phone"):
                lines.append(f"  Phone    : {str(record['phone'])}")
            if record.get("address"):
                lines.append(f"  Address  : {escape_html(str(record['address'][:100]))}")
            lines.append("")
    else:
        lines.append("  Status: NO DATA FOUND")
        if osint_note:
            lines.append(f"  Note: {escape_html(osint_note)}")
        lines.append("")

    # Footer
    lines.append("========================================")
    lines.append(f"  Source    : {safe_str(data.get('by', 'Unknown'))}")
    lines.append(f"  Cached    : {'Yes' if data.get('cached') else 'No'}")
    lines.append(f"  Time      : {safe_str(data.get('cached_at', 'N/A'))[:19]}")
    lines.append("========================================")

    return "\n".join(lines)


def build_raw_json(data: dict) -> str:
    """Build a raw JSON code block of the API response."""
    # Remove the large pfp URL to keep it clean
    clean = dict(data)
    if "profile" in clean and "pfp" in clean["profile"]:
        pfp = clean["profile"]["pfp"]
        clean["profile"] = dict(clean["profile"])
        clean["profile"]["pfp"] = pfp[:80] + "..."

    raw = json.dumps(clean, indent=2, ensure_ascii=False)
    # Truncate if too long for Telegram
    if len(raw) > 3800:
        raw = raw[:3800] + "\n... (truncated)"
    return raw


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
    welcome = (
        f"\U0001f44b Welcome, <b>{user.first_name}</b>!\n\n"
        f"\U0001f50d <b>{BRAND_NAME}</b>\n"
        "Get detailed information about any Instagram account.\n\n"
    )

    if is_new:
        welcome += f"\U0001f381 You received <b>{FREE_CREDITS} FREE credits</b> to get started!\n\n"

    welcome += (
        f"\U0001f4b0 <b>Your Balance:</b> {db_user['credits']} credits\n\n"
        "Choose an option below \u2193"
    )

    await update.message.reply_text(
        welcome,
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    text = (
        "\U0001f4d6 <b>How to Use Hathix Shadow</b>\n\n"
        "\U0001f50d <b>Instagram Lookup</b>\n"
        "1. Tap 'Instagram Lookup' button\n"
        "2. Enter the Instagram username (without @)\n"
        "3. Get detailed OSINT data instantly!\n\n"
        "\U0001f4b3 <b>Buy Credits</b>\n"
        "1. Tap 'Buy Credits' button\n"
        "2. Choose a package\n"
        "3. Send payment to the UPI ID shown\n"
        "4. Upload payment screenshot\n"
        "5. Wait for admin approval\n\n"
        "\U0001f4b0 <b>Check Balance</b>\n"
        "Tap 'My Balance' to see your current credits.\n\n"
        "\U0001f4cb <b>History</b>\n"
        "Tap 'My History' to see your past lookups.\n\n"
        "\U0001f6e1\ufe0f Each lookup costs <b>1 credit</b>.\n\n"
        "For support, contact admin."
    )
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
        "\U0001f4b0 Each credit = 1 Instagram lookup\n"
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
        text = (
            f"\U0001f44b Hey, <b>{user.first_name}</b>!\n\n"
            f"\U0001f4b0 <b>Your Balance:</b> {db_user['credits']} credits\n\n"
            "Choose an option \u2193"
        )
        await query.edit_message_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
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
            reply_markup=main_menu_keyboard(),
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

    # Export report as image
    if data.startswith("export_"):
        export_username = data.replace("export_", "")
        lookup_data = context.user_data.get("last_lookup")
        if not lookup_data:
            await query.edit_message_text(
                "\u274c No data to export. Please run a lookup first.",
                reply_markup=main_menu_keyboard(),
            )
            return

        await query.answer("\U0001f4f7 Generating report image...")

        try:
            from exporter import generate_report_image
            image_buffer = generate_report_image(lookup_data)
            await context.bot.send_photo(
                chat_id=query.message.chat.id,
                photo=image_buffer,
                caption=f"\U0001f4f7 <b>OSINT Report</b> for @{export_username}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Export failed: {e}")
            await query.edit_message_text(
                f"\u274c <b>Export failed</b>\n\nError: {str(e)[:200]}",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML",
            )
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
            f"\U0001f4f1 Re-export <b>@{cached['username']}</b>\n\n"
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
                caption=f"\U0001f4f7 <b>Re-exported Report</b> for @{cached['username']}",
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


async def handle_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Instagram username lookup with full code-formatted output."""
    user = update.effective_user

    # Check if banned
    if db.is_banned(user.id):
        await update.message.reply_text(
            "\U0001f6ab You are <b>banned</b> from using this bot.\nContact admin for support.",
            parse_mode="HTML",
        )
        return

    # Check credits
    credits = db.get_credits(user.id)
    if credits <= 0:
        await update.message.reply_text(
            "\u26a0\ufe0f <b>No Credits!</b>\n\n"
            "You have no credits left.\n"
            "Buy more credits to continue using the bot.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
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

    # Extract username from message
    username = update.message.text.strip().lstrip("@")

    # Validate
    if not username or " " in username or len(username) > 30 or (not username.isalnum() and "_" not in username and "." not in username):
        await update.message.reply_text(
            "\u274c <b>Invalid username!</b>\n\n"
            "Please enter a valid Instagram username.\n"
            "Example: <code>cristiano</code>",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    # Show loading
    loading_msg = await update.message.reply_text(
        f"\U0001f50d <b>Looking up</b> <code>{username}</code>...\nPlease wait.",
        parse_mode="HTML",
    )

    # Call API
    result = await api_client.lookup_instagram(username)

    if not result["success"]:
        await loading_msg.edit_text(
            f"\u274c <b>Lookup Failed</b>\n\nError: {result['error']}\n\nPlease try again later.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    data = result["data"]

    if not data.get("success"):
        await loading_msg.edit_text(
            f"\u274c <b>No data found</b> for <code>{username}</code>.\n\n"
            "The username may not exist or the API is unavailable.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    # Use one credit
    if not db.use_credit(user.id):
        await loading_msg.edit_text(
            "\u26a0\ufe0f <b>Credits exhausted</b> during lookup.\nBuy more credits.",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    # Record this lookup for rate limiting
    _record_lookup(user.id)

    db.log_lookup(user.id, username, True)
    # Save full API response for re-export
    db.save_lookup_result(user.id, username, json.dumps(data))

    # Build the formatted OSINT report
    report = build_osint_report(data)
    pfp = data.get("profile", {}).get("pfp", "")

    # PART 1: Send profile picture with header
    header = (
        f"\U0001f4f1 <b>OSINT Report for @{safe_str(data.get('username', username))}</b>\n"
        f"Credits remaining: <b>{db.get_credits(user.id)}</b>"
    )

    try:
        await loading_msg.delete()
    except Exception:
        pass

    # Send photo with short header if pfp exists
    if pfp and pfp.startswith("http"):
        try:
            await update.message.reply_photo(
                photo=pfp,
                caption=header,
                parse_mode="HTML",
            )
        except Exception:
            # If photo fails, just continue with text
            pass

    # PART 2: Send the full report in a code block
    code_block = f"<pre>{report}</pre>"

    # Telegram has a 4096 char limit for messages
    if len(code_block) + 50 > MAX_MSG_LEN:
        # Split into parts
        part1 = report[:3800]
        part2 = report[3800:]

        await update.message.reply_text(
            f"<pre>{part1}</pre>",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard() if not part2 else None,
        )
        if part2:
            await update.message.reply_text(
                f"<pre>{part2}</pre>",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(),
            )
    else:
        await update.message.reply_text(
            code_block,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )

    # Store data for export
    context.user_data["last_lookup"] = data

    # PART 3: Send raw JSON as a separate code message
    raw_json = build_raw_json(data)
    raw_json_safe = escape_html(raw_json)
    json_header = "\U0001f4cb <b>Raw API Response (JSON):</b>"

    if len(raw_json_safe) + len(json_header) + 50 > MAX_MSG_LEN:
        # Split JSON
        json_part1 = raw_json_safe[:3800]
        json_part2 = raw_json_safe[3800:]

        await update.message.reply_text(
            f"{json_header}\n<pre>{json_part1}</pre>",
            parse_mode="HTML",
        )
        if json_part2:
            await update.message.reply_text(
                f"<pre>{json_part2}</pre>",
                parse_mode="HTML",
            )
    else:
        await update.message.reply_text(
            f"{json_header}\n<pre>{raw_json_safe}</pre>",
            parse_mode="HTML",
        )

    # PART 4: Export button
    export_msg = await update.message.reply_text(
        "\U0001f4e5 <b>Export Report</b>\n\nTap below to download this report as a styled image.",
        reply_markup=export_keyboard(username),
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
    """Handle payment screenshot upload."""
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

    tx_id = db.create_transaction(user.id, awaiting, pkg["credits"], pkg["price"], screenshot_file_id)

    context.user_data.pop("awaiting_screenshot", None)
    context.user_data.pop("pending_package", None)

    await update.message.reply_text(
        f"\u2705 <b>Payment Screenshot Received!</b>\n\n"
        f"Package: <b>{pkg['label']}</b>\n"
        f"Amount: \u20b9{pkg['price']}\n"
        f"Credits: {pkg['credits']}\n"
        f"Transaction ID: <code>#{tx_id}</code>\n\n"
        "\u23f3 Your payment is now <b>pending review</b>.\n"
        "An admin will verify and approve it shortly.\n\n"
        "You will be notified once approved.",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )

    # Notify admins
    from config import ADMIN_IDS
    for admin_id in ADMIN_IDS:
        try:
            caption = (
                f"\U0001f4e2 <b>New Payment Request</b>\n\n"
                f"User: <b>{user.first_name}</b> (@{user.username or 'N/A'})\n"
                f"User ID: <code>{user.id}</code>\n"
                f"Package: <b>{pkg['label']}</b>\n"
                f"Amount: \u20b9{pkg['price']}\n"
                f"Credits: {pkg['credits']}\n"
                f"TX ID: <code>#{tx_id}</code>"
            )
            if update.message.photo:
                await context.bot.send_photo(
                    admin_id,
                    photo=screenshot_file_id,
                    caption=caption,
                    parse_mode="HTML",
                )
            else:
                await context.bot.send_document(
                    admin_id,
                    document=screenshot_file_id,
                    caption=caption,
                    parse_mode="HTML",
                )
        except Exception:
            pass

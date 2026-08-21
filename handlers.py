import logging
import json
import time
import asyncio
import io
import os
from collections import defaultdict
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.error import BadRequest

import database as db
import api_client
import user_data_store as uds
from keyboards import (
    main_menu_keyboard, buy_plan_keyboard, confirm_payment_keyboard,
    back_button, pdf_button, history_list_keyboard, reexport_keyboard,
    admin_keyboard, required_channels_keyboard, main_menu_button,
)
from config import SUBSCRIPTION_PACKAGES, UPI_ID, UPI_NAME, LOGO_PATH, BRAND_NAME, BRAND_TAGLINE, ADMIN_IDS, REQUIRED_CHANNELS, DEVELOPER

logger = logging.getLogger(__name__)
MAX_MSG_LEN = 4096
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW = 60
_rate_limit_tracker = defaultdict(list)


def _check_rate_limit(user_id):
    now = time.time()
    _rate_limit_tracker[user_id] = [ts for ts in _rate_limit_tracker[user_id] if now - ts < RATE_LIMIT_WINDOW]
    if len(_rate_limit_tracker[user_id]) >= RATE_LIMIT_MAX:
        oldest = _rate_limit_tracker[user_id][0]
        return False, int(RATE_LIMIT_WINDOW - (now - oldest)) + 1
    return True, 0


def _record_lookup(user_id):
    _rate_limit_tracker[user_id].append(time.time())


def escape_html(text):
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def check_user_channels(user_id, bot):
    not_joined = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["creator", "administrator", "member", "restricted"]:
                continue
            not_joined.append(channel)
        except (BadRequest, Exception):
            continue
    return (len(not_joined) == 0, not_joined)


async def _pre_lookup_checks(update, context):
    user = update.effective_user
    is_admin = user.id in ADMIN_IDS
    if not is_admin:
        is_member, not_joined = await check_user_channels(user.id, context.bot)
        if not is_member:
            channel_list = "\n".join([f"  {ch}" for ch in not_joined])
            await update.message.reply_text(
                f"Join Required Channels!\n\n{channel_list}\n\nJoin then tap verify.",
                reply_markup=required_channels_keyboard(), parse_mode="HTML")
            return (False, None)
    if db.is_banned(user.id):
        await update.message.reply_text("You are banned.", parse_mode="HTML")
        return (False, None)
    if not is_admin and not db.has_active_subscription(user.id):
        await update.message.reply_text(
            "No Active Subscription!\nBuy a package for unlimited lookups!",
            reply_markup=main_menu_keyboard(), parse_mode="HTML")
        return (False, None)
    allowed, wait_secs = _check_rate_limit(user.id)
    if not allowed:
        await update.message.reply_text(
            f"Rate Limit! Wait {wait_secs}s.",
            reply_markup=main_menu_keyboard(), parse_mode="HTML")
        return (False, None)
    return (True, user)


async def _send_result(update, context, data, service_name, query, user):
    from pdf_exporter import format_text_report, SERVICE_EMOJIS, SERVICE_TITLES
    text = format_text_report(data, service_name, query)
    emoji = SERVICE_EMOJIS.get(service_name, "🔍")
    title = SERVICE_TITLES.get(service_name, "OSINT REPORT")
    escaped = escape_html(text)
    if len(escaped) + 100 > MAX_MSG_LEN:
        part1 = escape_html(text[:3900])
        part2 = escape_html(text[3900:])
        await update.message.reply_text(part1, parse_mode="HTML")
        if part2:
            await update.message.reply_text(part2, parse_mode="HTML")
    else:
        await update.message.reply_text(escaped, parse_mode="HTML")
    _record_lookup(user.id)
    if user.id not in ADMIN_IDS:
        db.record_lookup(user.id)
    try:
        uds.save_user(user.id, user.username, user.first_name)
        uds.save_lookup(user.id, user.username or user.first_name, service_name, query, data, True)
    except Exception:
        pass
    try:
        db.log_lookup(user.id, user.username or user.first_name, True)
        db.save_lookup_result(user.id, user.username or user.first_name, json.dumps(data))
    except Exception:
        pass
    await update.message.reply_text(
        f"{emoji} <b>{title}</b> complete for <code>{escape_html(query)}</code>",
        reply_markup=pdf_button(service_name, query), parse_mode="HTML")


async def start(update, context):
    user = update.effective_user
    db_user = db.get_or_create_user(user.id, user.username, user.first_name)
    is_new = db_user["total_lookups"] == 0
    if user.id not in ADMIN_IDS:
        is_member, not_joined = await check_user_channels(user.id, context.bot)
        if not is_member:
            channel_list = "\n".join([f"  {ch}" for ch in not_joined])
            await update.message.reply_text(
                f"Join Required Channels!\n\n{channel_list}\n\nJoin then verify.",
                reply_markup=required_channels_keyboard(), parse_mode="HTML")
            return
    try:
        from header import generate_header_image
        header_img = generate_header_image(
            brand_name=BRAND_NAME, tagline=BRAND_TAGLINE,
            logo_path=LOGO_PATH, credits=0, is_new=is_new)
        await update.message.reply_photo(photo=header_img, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Header image failed: {e}")
    is_admin_user = user.id in ADMIN_IDS
    has_access = is_admin_user or db.has_active_subscription(user.id)
    welcome = (
        f"Welcome, <b>{user.first_name}</b>!\n\n"
        f"<b>{BRAND_NAME} - {BRAND_TAGLINE}</b>\n"
        "Multi-service OSINT intelligence bot.\n\n")
    if has_access:
        welcome += "Active Subscription - Unlimited lookups!\n\n"
    else:
        welcome += "No active subscription - Buy a package to continue.\n\n"
    if is_admin_user:
        welcome += "Admin: Tap Admin Panel below\n\n"
    welcome += "Choose a service below:"
    await update.message.reply_text(welcome, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def help_command(update, context):
    text = (
        f"<b>{BRAND_NAME} - {BRAND_TAGLINE}</b>\n\n"
        "<b>How to Use</b>\n"
        "1. Tap Buy Plan to purchase access\n"
        "2. Or tap Redeem Code if you have a code\n"
        "3. Choose a service from the menu\n"
        "4. Enter the required input\n"
        "5. Get instant OSINT data!\n"
        "6. Tap Download PDF Report for PDF\n\n"
        "<b>Services</b>\n"
        "  IP Lookup - IP address info\n"
        "  Num Info - Phone number details\n"
        "  Name Info - Name lookup\n"
        "  Vehicle Lookup - Full vehicle info\n"
        "  M-Parivahan - Govt vehicle data\n"
        "  HotX Lookup - Deep phone lookup\n"
        "  Aadhaar Family - Family trace\n\n"
        f"Developed by {DEVELOPER}")
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def status_command(update, context):
    loading_msg = await update.message.reply_text("Checking API Health...", parse_mode="HTML")
    results = await api_client.check_api_health()
    lines = ["<b>API Health Status</b>", ""]
    for r in results:
        s, n, ms, d = r["status"], r["name"], r["ms"], r["detail"]
        if s == "ok": lines.append(f"[OK] {n} - {ms}ms")
        elif s == "blocked": lines.append(f"[BLOCKED] {n}")
        elif s == "timeout": lines.append(f"[TIMEOUT] {n}")
        else: lines.append(f"[ERR] {n} - {d}")
    ok_count = sum(1 for r in results if r["status"] == "ok")
    lines.append(f"\n{ok_count}/{len(results)} endpoints healthy")
    await loading_msg.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=main_menu_keyboard())


async def handle_ip_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip()
    if not query or len(query) < 3:
        await update.message.reply_text("Enter a valid IP.\nExample: 8.8.8.8", reply_markup=main_menu_keyboard(), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text(f"Looking up IP: <code>{query}</code>...", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(api_client.lookup_ip_info(query), timeout=20)
    except asyncio.TimeoutError:
        await loading_msg.edit_text("Request timed out.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"IP lookup error: {e}")
        await loading_msg.edit_text("Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await loading_msg.edit_text(f"No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "ip_info", query, user)


async def handle_numinfo_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip().replace(" ", "").replace("-", "").replace("+", "")
    if not query or not query.isdigit() or len(query) < 10:
        await update.message.reply_text("Enter a valid 10-digit number.\nExample: 9876543210", reply_markup=main_menu_keyboard(), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text(f"Looking up number: <code>{query}</code>...", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(api_client.lookup_numinfo(query), timeout=20)
    except asyncio.TimeoutError:
        await loading_msg.edit_text("Request timed out.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"NumInfo lookup error: {e}")
        await loading_msg.edit_text("Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await loading_msg.edit_text(f"No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "num_info", query, user)


async def handle_name_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip()
    if not query or len(query) < 2:
        await update.message.reply_text("Enter a name.\nExample: Rahul Kumar", reply_markup=main_menu_keyboard(), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text(f"Looking up name: <code>{query}</code>...", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(api_client.lookup_name_info(query), timeout=20)
    except asyncio.TimeoutError:
        await loading_msg.edit_text("Request timed out.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"Name lookup error: {e}")
        await loading_msg.edit_text("Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await loading_msg.edit_text(f"No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "name_info", query, user)


async def handle_vehicle_full_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip().upper()
    if not query or len(query) < 5:
        await update.message.reply_text("Enter a valid vehicle number.\nExample: UK06BL1506", reply_markup=main_menu_keyboard(), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text(f"Looking up vehicle: <code>{query}</code>...", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(api_client.lookup_vehicle_full(query), timeout=25)
    except asyncio.TimeoutError:
        await loading_msg.edit_text("Request timed out.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"Vehicle lookup error: {e}")
        await loading_msg.edit_text("Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await loading_msg.edit_text(f"No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "vehicle_full", query, user)


async def handle_parivahan_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip().upper()
    if not query or len(query) < 5:
        await update.message.reply_text("Enter a valid vehicle number.\nExample: MP09BH4640", reply_markup=main_menu_keyboard(), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text(f"Looking up (M-Parivahan): <code>{query}</code>...", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(api_client.lookup_vehicle_parivahan(query), timeout=25)
    except asyncio.TimeoutError:
        await loading_msg.edit_text("Request timed out.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"Parivahan lookup error: {e}")
        await loading_msg.edit_text("Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await loading_msg.edit_text(f"No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "vehicle_parivahan", query, user)


async def handle_hotx_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip().replace(" ", "").replace("-", "").replace("+", "")
    if not query or not query.isdigit() or len(query) < 10:
        await update.message.reply_text("Enter a valid 10-digit number.\nExample: 9876543210", reply_markup=main_menu_keyboard(), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text(f"Looking up (HotX): <code>{query}</code>...", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(api_client.lookup_hotx(query), timeout=20)
    except asyncio.TimeoutError:
        await loading_msg.edit_text("Request timed out.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"HotX lookup error: {e}")
        await loading_msg.edit_text("Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await loading_msg.edit_text(f"No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "hotx", query, user)


async def handle_aadhaar_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip().replace(" ", "")
    if not query or not query.isdigit() or len(query) < 12:
        await update.message.reply_text("Enter a valid 12-digit Aadhaar.\nExample: 123456789012", reply_markup=main_menu_keyboard(), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text(f"Looking up Aadhaar family: <code>{query}</code>...", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(api_client.lookup_aadhaar_family(query), timeout=20)
    except asyncio.TimeoutError:
        await loading_msg.edit_text("Request timed out.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"Aadhaar lookup error: {e}")
        await loading_msg.edit_text("Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await loading_msg.edit_text(f"No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "aadhaar_family", query, user)


async def buy_plan(update, context):
    text = (
        f"Buy Plan - Unlimited Lookups\n\n"
        f"UPI ID: <code>{UPI_ID}</code>\n"
        f"Name: {UPI_NAME}\n\n"
        "Unlimited lookups for the duration!")
    await update.message.reply_text(text, reply_markup=buy_plan_keyboard(), parse_mode="HTML")


async def handle_redeem_code(update, context):
    text = "Redeem Code\n\nEnter your code:\nExample: <code>ABC123XYZ9</code>"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(), parse_mode="HTML")
    context.user_data["awaiting_redeem_code"] = True


async def process_redeem_code(update, context):
    code = update.message.text.strip()
    user = update.effective_user
    success, message, hours = db.redeem_code(code, user.id)
    await update.message.reply_text(message, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def contact_admin(update, context):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    dev_username = DEVELOPER.replace("@", "")
    text = f"Contact Admin\n\nTelegram: {DEVELOPER}\n\nTap below to message us."
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Message {DEVELOPER}", url=f"https://t.me/{dev_username}")],
        [InlineKeyboardButton("Back", callback_data="back_main")]
    ])
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")


async def handle_callback(update, context):
    query_cb = update.callback_query
    data = query_cb.data
    if update.effective_chat.type != "private":
        await query_cb.answer()
        return
    await query_cb.answer()
    user = query_cb.from_user
    user_id = user.id

    if data == "verify_channels":
        is_member, not_joined = await check_user_channels(user_id, context.bot)
        if is_member:
            try: await query_cb.edit_message_text("Verified!", reply_markup=main_menu_button(), parse_mode="HTML")
            except BadRequest: await query_cb.message.reply_text("Verified!", reply_markup=main_menu_button())
        else:
            channel_list = "\n".join([f"  {ch}" for ch in not_joined])
            try: await query_cb.edit_message_text(f"Not verified. Join:\n{channel_list}", reply_markup=required_channels_keyboard(), parse_mode="HTML")
            except BadRequest: await query_cb.message.reply_text(f"Not verified. Join:\n{channel_list}", reply_markup=required_channels_keyboard())
        return

    if user_id not in ADMIN_IDS:
        is_member, not_joined = await check_user_channels(user_id, context.bot)
        if not is_member:
            channel_list = "\n".join([f"  {ch}" for ch in not_joined])
            try: await query_cb.edit_message_text(f"Join channels:\n{channel_list}", reply_markup=required_channels_keyboard(), parse_mode="HTML")
            except BadRequest: await query_cb.message.reply_text(f"Join channels:\n{channel_list}", reply_markup=required_channels_keyboard())
            return

    if data == "back_main":
        text = f"Hey, <b>{user.first_name}</b>!\n\nChoose a service:"
        try: await query_cb.edit_message_text(text, reply_markup=main_menu_button(), parse_mode="HTML")
        except BadRequest: await query_cb.message.reply_text(text, reply_markup=main_menu_button(), parse_mode="HTML")
        return

    if data.startswith("pdf_"):
        parts = data.split("_", 2)
        if len(parts) < 3: return
        service_name = parts[1]
        pdf_query = parts[2]
        if user_id not in ADMIN_IDS and not db.has_active_subscription(user_id):
            await query_cb.answer("No active subscription!", show_alert=True)
            return
        await query_cb.answer("Generating PDF...")
        cached = None
        try: cached = db.get_lookup_cache(user_id, pdf_query)
        except Exception: pass
        if not cached:
            last = context.user_data.get("last_lookup")
            if last: cached = {"api_data": json.dumps(last)}
        if not cached:
            await query_cb.message.reply_text("No cached data. Run lookup again.", reply_markup=main_menu_button())
            return
        try:
            from pdf_exporter import generate_service_pdf
            api_data = json.loads(cached["api_data"]) if isinstance(cached.get("api_data"), str) else cached.get("api_data", {})
            pdf_buffer = generate_service_pdf(api_data, service_name, pdf_query)
            await context.bot.send_document(
                chat_id=update.effective_chat.id, document=pdf_buffer,
                filename=f"{service_name}_{pdf_query}.pdf",
                caption=f"PDF Report for <code>{pdf_query}</code>", parse_mode="HTML")
        except Exception as e:
            logger.error(f"PDF failed: {e}")
            await query_cb.message.reply_text(f"PDF failed: {str(e)[:100]}", parse_mode="HTML")
        return

    if data.startswith("buy_"):
        package_key = data.replace("buy_", "")
        if package_key not in SUBSCRIPTION_PACKAGES:
            await query_cb.edit_message_text("Invalid.", reply_markup=main_menu_button())
            return
        pkg = SUBSCRIPTION_PACKAGES[package_key]
        import database as qr_db
        from qr_payment import generate_qr_with_text
        qr_buf, token = generate_qr_with_text(package_key, pkg["price"], pkg["label"], UPI_ID)
        qr_db.create_qr_payment(token, user_id, package_key, pkg["price"], UPI_ID)
        context.user_data["pending_qr_token"] = token
        context.user_data["pending_package"] = package_key
        text = (
            f"<b>{pkg['label']}</b>\n"
            f"Price: <b>Rs.{pkg['price']}</b>\n\n"
            f"Scan the QR below to pay.\n"
            f"UPI ID: <code>{UPI_ID}</code>\n"
            f"Amount: <b>Rs.{pkg['price']} (Exact)</b>\n\n"
            f"After payment, send the payment screenshot here.\n"
            f"QR is single-use and expires in 30 minutes.")
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=qr_buf,
            caption=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")]
            ]),
        )
        context.user_data["awaiting_qr_screenshot"] = package_key
        try:
            await query_cb.message.delete()
        except Exception:
            pass
        return

    if data.startswith("confirm_"):
        package_key = data.replace("confirm_", "")
        if package_key not in SUBSCRIPTION_PACKAGES: return
        context.user_data["awaiting_screenshot"] = package_key
        pkg = SUBSCRIPTION_PACKAGES[package_key]
        msg = f"Send payment screenshot for {pkg['label']} (Rs.{pkg['price']})\nUPI: <code>{UPI_ID}</code>"
        try: await query_cb.edit_message_text(msg, parse_mode="HTML")
        except BadRequest: await query_cb.message.reply_text(msg, parse_mode="HTML")
        return

    if data == "cancel_payment":
        context.user_data.pop("awaiting_screenshot", None)
        context.user_data.pop("awaiting_qr_screenshot", None)
        context.user_data.pop("pending_qr_token", None)
        context.user_data.pop("pending_package", None)
        try: await query_cb.edit_message_text("Payment cancelled.", reply_markup=main_menu_button())
        except BadRequest: await query_cb.message.reply_text("Payment cancelled.", reply_markup=main_menu_button())
        return

    if data.startswith("approve_"):
        if user_id not in ADMIN_IDS: return
        tx_id = int(data.replace("approve_", ""))
        db.update_transaction_status(tx_id, "approved")
        try: uds.update_payment_status(tx_id, "approved")
        except Exception: pass
        conn = db.get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
        row = c.fetchone()
        conn.close()
        if row:
            tx = dict(row)
            if tx["package"] in SUBSCRIPTION_PACKAGES:
                hours = SUBSCRIPTION_PACKAGES[tx["package"]]["duration_hours"]
                db.set_subscription(tx["user_id"], hours)
                try: await context.bot.send_message(tx["user_id"], f"Payment Approved! {tx['package'].title()} activated!", parse_mode="HTML")
                except Exception: pass
        try: await query_cb.edit_message_text(f"Transaction #{tx_id} Approved")
        except BadRequest: await query_cb.message.reply_text(f"Transaction #{tx_id} Approved")
        return

    if data.startswith("reject_"):
        if user_id not in ADMIN_IDS: return
        tx_id = int(data.replace("reject_", ""))
        db.update_transaction_status(tx_id, "rejected")
        try: await query_cb.edit_message_text(f"Transaction #{tx_id} Rejected")
        except BadRequest: await query_cb.message.reply_text(f"Transaction #{tx_id} Rejected")
        return

    if data.startswith("udpage_"):
        if user_id not in ADMIN_IDS: return
        page_num = int(data.replace("udpage_", ""))
        await _send_userdata_page(update, context, page_num)
        return

    if data == "cancel_action":
        try: await query_cb.edit_message_text("Cancelled.", reply_markup=main_menu_button())
        except Exception: pass
        return

    if data == "history":
        lookups = db.get_user_lookup_history(user_id, limit=10)
        if not lookups:
            await query_cb.edit_message_text("No lookups yet.", reply_markup=main_menu_button())
        else:
            await query_cb.edit_message_text("Tap to re-export:", reply_markup=history_list_keyboard(lookups), parse_mode="HTML")
        return

    if data.startswith("reexport_") and not data.startswith("reexportimg_"):
        lookup_id = int(data.replace("reexport_", ""))
        cached = db.get_lookup_by_id(lookup_id, user_id)
        if not cached:
            await query_cb.edit_message_text("Not found.", reply_markup=main_menu_button())
            return
        await query_cb.edit_message_text(f"Re-export for {cached['username']}", reply_markup=reexport_keyboard(lookup_id, cached["username"]), parse_mode="HTML")
        return

    if data.startswith("reexportimg_"):
        lookup_id = int(data.replace("reexportimg_", ""))
        cached = db.get_lookup_by_id(lookup_id, user_id)
        if not cached:
            await query_cb.edit_message_text("Not found.", reply_markup=main_menu_button())
            return
        await query_cb.answer("Generating...")
        try:
            lookup_data = json.loads(cached["api_data"])
            from pdf_exporter import generate_service_pdf
            pdf_buffer = generate_service_pdf(lookup_data, "generic", cached["username"])
            await context.bot.send_document(chat_id=update.effective_chat.id, document=pdf_buffer,
                filename=f"REPORT_{cached['username']}.pdf", caption=f"Report for {cached['username']}", parse_mode="HTML")
        except Exception as e:
            logger.error(f"Re-export failed: {e}")
        return


async def handle_admin_text(update, context):
    return False


async def handle_screenshot(update, context):
    user = update.effective_user
    awaiting = context.user_data.get("awaiting_screenshot")
    if not awaiting or awaiting not in SUBSCRIPTION_PACKAGES: return
    pkg = SUBSCRIPTION_PACKAGES[awaiting]
    screenshot_file_id = None
    if update.message.photo: screenshot_file_id = update.message.photo[-1].file_id
    elif update.message.document: screenshot_file_id = update.message.document.file_id
    else:
        await update.message.reply_text("Send a photo or document.", parse_mode="HTML")
        return
    tx_id = db.create_transaction(user.id, awaiting, pkg["duration_hours"], pkg["price"], screenshot_file_id)
    try: uds.save_payment(user.id, user.username or user.first_name, awaiting, pkg["price"], "pending", tx_id)
    except Exception: pass
    context.user_data.pop("awaiting_screenshot", None)
    context.user_data.pop("pending_package", None)
    await update.message.reply_text(
        f"Payment Screenshot Received!\nPackage: {pkg['label']}\nAmount: Rs.{pkg['price']}\nTX: #{tx_id}\n\nAwaiting admin verification.",
        reply_markup=main_menu_keyboard(), parse_mode="HTML")
    from keyboards import admin_approve_keyboard
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(chat_id=admin_id, photo=screenshot_file_id,
                caption=f"Payment from {user.first_name} (#{tx_id}) - {pkg['label']} Rs.{pkg['price']}",
                reply_markup=admin_approve_keyboard(tx_id), parse_mode="HTML")
        except Exception: pass


async def handle_qr_screenshot(update, context):
    user = update.effective_user
    token = context.user_data.get("pending_qr_token")
    package_key = context.user_data.get("awaiting_qr_screenshot")
    if not token or not package_key or package_key not in SUBSCRIPTION_PACKAGES:
        return
    pkg = SUBSCRIPTION_PACKAGES[package_key]
    screenshot_file_id = None
    if update.message.photo: screenshot_file_id = update.message.photo[-1].file_id
    elif update.message.document: screenshot_file_id = update.message.document.file_id
    else:
        await update.message.reply_text("Send a payment screenshot (photo or document).", parse_mode="HTML")
        return
    qr_record = db.get_qr_payment_by_token(token)
    if qr_record and qr_record["is_used"]:
        await update.message.reply_text(
            "This QR code has already been used. A new QR will be generated.",
            reply_markup=main_menu_keyboard(), parse_mode="HTML")
        context.user_data.pop("awaiting_qr_screenshot", None)
        context.user_data.pop("pending_qr_token", None)
        context.user_data.pop("pending_package", None)
        return
    db.mark_qr_used(token, user.id)
    tx_id = db.create_transaction(user.id, package_key, pkg["duration_hours"], pkg["price"], screenshot_file_id)
    try: uds.save_payment(user.id, user.username or user.first_name, package_key, pkg["price"], "pending", tx_id)
    except Exception: pass
    context.user_data.pop("awaiting_qr_screenshot", None)
    context.user_data.pop("pending_qr_token", None)
    context.user_data.pop("pending_package", None)
    await update.message.reply_text(
        f"Payment Screenshot Received!\n\n"
        f"Package: {pkg['label']}\n"
        f"Amount: Rs.{pkg['price']}\n"
        f"TX: #{tx_id}\n"
        f"QR Token: {token[:8]}...\n\n"
        f"Awaiting admin verification.",
        reply_markup=main_menu_keyboard(), parse_mode="HTML")
    from keyboards import admin_approve_keyboard
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(chat_id=admin_id, photo=screenshot_file_id,
                caption=(
                    f"QR Payment from {user.first_name}\n"
                    f"TX: #{tx_id} | {pkg['label']} Rs.{pkg['price']}\n"
                    f"Token: {token[:8]}..."),
                reply_markup=admin_approve_keyboard(tx_id), parse_mode="HTML")
        except Exception: pass


USERS_PAGE_SIZE = 10

async def _send_userdata_page(update_or_query, context, page_num):
    all_users = uds.get_all_users()
    total = len(all_users)
    total_pages = max(1, (total + USERS_PAGE_SIZE - 1) // USERS_PAGE_SIZE)
    page_num = max(0, min(page_num, total_pages - 1))
    start_idx = page_num * USERS_PAGE_SIZE
    page_users = all_users[start_idx:start_idx + USERS_PAGE_SIZE]
    lines = [f"Users (Page {page_num+1}/{total_pages})", f"Total: {total}", ""]
    for u in page_users:
        sub = u.get("subscription", {})
        st = "OK" if sub.get("status") == "active" else "!"
        lines.append(f"[{st}] {u.get('first_name', 'N/A')} (@{u.get('username', 'N/A')}) ID: {u.get('user_id')}")
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    nav_row = []
    if page_num > 0: nav_row.append(InlineKeyboardButton("Prev", callback_data=f"udpage_{page_num-1}"))
    nav_row.append(InlineKeyboardButton(f"{page_num+1}/{total_pages}", callback_data="noop"))
    if page_num < total_pages - 1: nav_row.append(InlineKeyboardButton("Next", callback_data=f"udpage_{page_num+1}"))
    kb = InlineKeyboardMarkup([nav_row, [InlineKeyboardButton("Main Menu", callback_data="back_main")]])
    text = "\n".join(lines)
    if hasattr(update_or_query, "edit_message_text"):
        try: await update_or_query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception: pass

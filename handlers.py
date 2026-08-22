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

# ─── Animated Loading ────────────────────────────────────────
SPINNERS = {
    "ip":       ["🌐", "🌍", "🌎", "🌏"],
    "num":      ["📡", "🔍", "🔎", "📡"],
    "name":     ["👤", "🔍", "🔎", "👤"],
    "vehicle":  ["🚗", "🏎", "🚙", "🚕"],
    "parivahan":["🏛", "🚗", "🏛", "🚗"],
    "hotx":     ["🔥", "📡", "🔍", "🔥"],
    "aadhaar":  ["👨‍👩‍👧", "🔍", "🔎", "👨‍👩‍👧"],
    "default":  ["⚡", "🔍", "📡", "⚡"],
}

SERVICE_LABELS = {
    "ip": "IP Lookup",
    "num": "Number Intel",
    "name": "Name Intel",
    "vehicle": "Vehicle Lookup",
    "parivahan": "M-Parivahan",
    "hotx": "HotX Deep Scan",
    "aadhaar": "Aadhaar Family",
}

SERVICE_BARS = {
    "ip":       "▓▓░░░░░░",
    "num":      "▓▓▓░░░░░",
    "name":     "▓▓▓░░░░░",
    "vehicle":  "▓▓▓▓░░░░",
    "parivahan":"▓▓▓▓░░░░",
    "hotx":     "▓▓▓▓▓░░░",
    "aadhaar":  "▓▓▓░░░░░",
}


async def _dfpay_create_order(amount: int, order_ref: str) -> dict:
    """Create a payment order via DFPAY API."""
    from config import DFPAY_API_URL, DFPAY_API_KEY, WEBHOOK_URL
    import httpx
    payload = {"amount": amount, "order_ref": order_ref}
    if WEBHOOK_URL:
        payload["webhook_url"] = WEBHOOK_URL
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{DFPAY_API_URL}/create",
                json=payload,
                headers={"X-API-Key": DFPAY_API_KEY, "Content-Type": "application/json"},
            )
            return resp.json()
    except Exception as e:
        logger.error(f"DFPAY create order error: {e}")
        return {}


async def _dfpay_check_status(order_id: str) -> dict:
    """Check payment status via DFPAY API."""
    from config import DFPAY_API_URL, DFPAY_API_KEY
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{DFPAY_API_URL}/status/{order_id}",
                headers={"X-API-Key": DFPAY_API_KEY},
            )
            return resp.json()
    except Exception as e:
        logger.error(f"DFPAY status check error: {e}")
        return {}


async def _payment_poll_job(context):
    """Poll DFPAY payment status every 15 seconds."""
    data = context.job.data
    user_id = data["user_id"]
    order_id = data["order_id"]
    package_key = data["package_key"]
    chat_id = data["chat_id"]
    attempts = data.get("attempts", 0)
    max_attempts = 120  # 30 minutes / 15 sec = 120

    if attempts >= max_attempts:
        # Timed out
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ <b>Payment Expired!</b>\n\n"
                     "Payment was not completed.\n"
                     "Tap Buy Plan again to try.",
                reply_markup=main_menu_button(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        context.user_data.pop("pending_dfpay_order", None)
        context.user_data.pop("pending_package", None)
        return

    # Check status
    status_resp = await _dfpay_check_status(order_id)
    status = status_resp.get("status", "")

    if status in ("paid", "completed", "success", "CAPTURED"):
        # Payment confirmed — activate subscription
        pkg = SUBSCRIPTION_PACKAGES.get(package_key, {})
        duration_hours = pkg.get("duration_hours", 24)
        db.set_subscription(user_id, duration_hours)
        tx_id = db.create_transaction(user_id, package_key, duration_hours, pkg.get("price", 0))
        db.update_transaction_status(tx_id, "approved")
        try:
            uds.save_payment(user_id, "user", package_key, pkg.get("price", 0), "approved", tx_id)
        except Exception:
            pass
        context.user_data.pop("pending_dfpay_order", None)
        context.user_data.pop("pending_package", None)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ <b>Payment Verified!</b>\n\n"
                     f"<b>{pkg.get('label', package_key)}</b> activated!\n"
                     f"You now have unlimited lookups for {duration_hours}h.\n\n"
                     f"Enjoy!",
                reply_markup=main_menu_button(),
                parse_mode="HTML",
            )
        except Exception:
            pass
        # Notify admin
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"💰 Payment Auto-Verified\n"
                        f"User: #{user_id}\n"
                        f"Package: {pkg.get('label', package_key)} Rs.{pkg.get('price', 0)}\n"
                        f"Order: {order_id}\n"
                        f"✅ Activated immediately"),
                    parse_mode="HTML")
            except Exception:
                pass
    else:
        # Still pending — schedule next poll
        if context.job_queue:
            context.job_queue.run_once(
                _payment_poll_job,
                when=15,
                data={**data, "attempts": attempts + 1},
                name=f"poll_{order_id}",
            )


async def _animated_loading(message, service_key, query, api_coro):
    spinner = SPINNERS.get(service_key, SPINNERS["default"])
    label = SERVICE_LABELS.get(service_key, "Lookup")
    bar = SERVICE_BARS.get(service_key, "▓▓▓░░░░░")
    done = False
    result = [None]

    async def run_api():
        try:
            result[0] = await api_coro
        except Exception as e:
            result[0] = {"success": False, "error": str(e)}
        nonlocal done
        done = True

    task = asyncio.create_task(run_api())
    i = 0
    stages = [
        f"  {spinner[0]} <b>{label}</b>\n\n"
        f"  🎯 <code>{query}</code>\n\n"
        f"  {bar}\n"
        f"  ⚡ Initializing scan...",
        f"  {spinner[1]} <b>{label}</b>\n\n"
        f"  🎯 <code>{query}</code>\n\n"
        f"  ▓▓▓▓░░░░\n"
        f"  🔎 Querying databases...",
        f"  {spinner[2]} <b>{label}</b>\n\n"
        f"  🎯 <code>{query}</code>\n\n"
        f"  ▓▓▓▓▓▓░░\n"
        f"  📡 Fetching results...",
        f"  {spinner[3]} <b>{label}</b>\n\n"
        f"  🎯 <code>{query}</code>\n\n"
        f"  ▓▓▓▓▓▓▓░\n"
        f"  ⏳ Processing data...",
    ]
    while not done:
        try:
            await message.edit_text(stages[i % len(stages)], parse_mode="HTML")
        except Exception:
            pass
        i += 1
        await asyncio.sleep(0.4)

    await task
    return result[0]


def _is_admin(user_id):
    return user_id in ADMIN_IDS


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
            reply_markup=main_menu_keyboard(is_admin=_is_admin(update.effective_user.id)), parse_mode="HTML")
        return (False, None)
    allowed, wait_secs = _check_rate_limit(user.id)
    if not allowed:
        await update.message.reply_text(
            f"Rate Limit! Wait {wait_secs}s.",
            reply_markup=main_menu_keyboard(is_admin=_is_admin(update.effective_user.id)), parse_mode="HTML")
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
    await update.message.reply_text(welcome, reply_markup=main_menu_keyboard(user_id=update.effective_user.id), parse_mode="HTML")


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
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(user_id=update.effective_user.id), parse_mode="HTML")


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
    await loading_msg.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=main_menu_keyboard(user_id=update.effective_user.id))


async def handle_ip_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip()
    if not query or len(query) < 3:
        await update.message.reply_text("Enter a valid IP.\nExample: 8.8.8.8", reply_markup=main_menu_keyboard(user_id=update.effective_user.id), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text("⚡", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(
            _animated_loading(loading_msg, "ip", query, api_client.lookup_ip_info(query)),
            timeout=20
        )
    except asyncio.TimeoutError:
        await loading_msg.edit_text("⏰ Request timed out. Try again.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"IP lookup error: {e}")
        await loading_msg.edit_text("❌ Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await update.message.reply_text(f"❌ No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "ip_info", query, user)


async def handle_numinfo_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip().replace(" ", "").replace("-", "").replace("+", "")
    if not query or not query.isdigit() or len(query) < 10:
        await update.message.reply_text("Enter a valid 10-digit number.\nExample: 9876543210", reply_markup=main_menu_keyboard(user_id=update.effective_user.id), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text("⚡", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(
            _animated_loading(loading_msg, "num", query, api_client.lookup_numinfo(query)),
            timeout=20
        )
    except asyncio.TimeoutError:
        await loading_msg.edit_text("⏰ Request timed out. Try again.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"NumInfo lookup error: {e}")
        await loading_msg.edit_text("❌ Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await update.message.reply_text(f"❌ No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "num_info", query, user)


async def handle_name_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip()
    if not query or len(query) < 2:
        await update.message.reply_text("Enter a name.\nExample: Rahul Kumar", reply_markup=main_menu_keyboard(user_id=update.effective_user.id), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text("⚡", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(
            _animated_loading(loading_msg, "name", query, api_client.lookup_name_info(query)),
            timeout=20
        )
    except asyncio.TimeoutError:
        await loading_msg.edit_text("⏰ Request timed out. Try again.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"Name lookup error: {e}")
        await loading_msg.edit_text("❌ Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await update.message.reply_text(f"❌ No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "name_info", query, user)


async def handle_vehicle_full_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip().upper()
    if not query or len(query) < 5:
        await update.message.reply_text("Enter a valid vehicle number.\nExample: UK06BL1506", reply_markup=main_menu_keyboard(user_id=update.effective_user.id), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text("⚡", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(
            _animated_loading(loading_msg, "vehicle", query, api_client.lookup_vehicle_full(query)),
            timeout=25
        )
    except asyncio.TimeoutError:
        await loading_msg.edit_text("⏰ Request timed out. Try again.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"Vehicle lookup error: {e}")
        await loading_msg.edit_text("❌ Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await update.message.reply_text(f"❌ No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "vehicle_full", query, user)


async def handle_parivahan_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip().upper()
    if not query or len(query) < 5:
        await update.message.reply_text("Enter a valid vehicle number.\nExample: MP09BH4640", reply_markup=main_menu_keyboard(user_id=update.effective_user.id), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text("⚡", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(
            _animated_loading(loading_msg, "parivahan", query, api_client.lookup_vehicle_parivahan(query)),
            timeout=25
        )
    except asyncio.TimeoutError:
        await loading_msg.edit_text("⏰ Request timed out. Try again.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"Parivahan lookup error: {e}")
        await loading_msg.edit_text("❌ Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await update.message.reply_text(f"❌ No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "vehicle_parivahan", query, user)


async def handle_hotx_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip().replace(" ", "").replace("-", "").replace("+", "")
    if not query or not query.isdigit() or len(query) < 10:
        await update.message.reply_text("Enter a valid 10-digit number.\nExample: 9876543210", reply_markup=main_menu_keyboard(user_id=update.effective_user.id), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text("⚡", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(
            _animated_loading(loading_msg, "hotx", query, api_client.lookup_hotx(query)),
            timeout=20
        )
    except asyncio.TimeoutError:
        await loading_msg.edit_text("⏰ Request timed out. Try again.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"HotX lookup error: {e}")
        await loading_msg.edit_text("❌ Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await update.message.reply_text(f"❌ No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "hotx", query, user)


async def handle_aadhaar_lookup(update, context):
    ok, user = await _pre_lookup_checks(update, context)
    if not ok: return
    query = update.message.text.strip().replace(" ", "")
    if not query or not query.isdigit() or len(query) < 12:
        await update.message.reply_text("Enter a valid 12-digit Aadhaar.\nExample: 123456789012", reply_markup=main_menu_keyboard(user_id=update.effective_user.id), parse_mode="HTML")
        return
    loading_msg = await update.message.reply_text("⚡", parse_mode="HTML")
    try:
        result = await asyncio.wait_for(
            _animated_loading(loading_msg, "aadhaar", query, api_client.lookup_aadhaar_family(query)),
            timeout=20
        )
    except asyncio.TimeoutError:
        await loading_msg.edit_text("⏰ Request timed out. Try again.", parse_mode="HTML")
        return
    except Exception as e:
        logger.error(f"Aadhaar lookup error: {e}")
        await loading_msg.edit_text("❌ Lookup failed. Try again.", parse_mode="HTML")
        return
    try: await loading_msg.delete()
    except Exception: pass
    if not result.get("success"):
        await update.message.reply_text(f"❌ No data for <code>{query}</code>\nError: {result.get('error', 'Unknown')}", parse_mode="HTML")
        return
    await _send_result(update, context, result, "aadhaar_family", query, user)


async def buy_plan(update, context):
    text = (
        f"Buy Plan - Unlimited Lookups\n\n"
        f"UPI ID: <code>{UPI_ID}</code>\n"
        f"Name: {UPI_NAME}\n\n"
        "Select a plan below to generate QR code:")
    await update.message.reply_text(text, reply_markup=buy_plan_keyboard(), parse_mode="HTML")


async def handle_redeem_code(update, context):
    text = "Redeem Code\n\nEnter your code:\nExample: <code>ABC123XYZ9</code>"
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(user_id=update.effective_user.id), parse_mode="HTML")
    context.user_data["awaiting_redeem_code"] = True


async def process_redeem_code(update, context):
    code = update.message.text.strip()
    user = update.effective_user
    success, message, hours = db.redeem_code(code, user.id)
    await update.message.reply_text(message, reply_markup=main_menu_keyboard(user_id=update.effective_user.id), parse_mode="HTML")


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
        await query_cb.answer("Creating payment...")
        # Create DFPAY order
        order_ref = f"{user_id}_{package_key}_{int(time.time())}"
        order_resp = await _dfpay_create_order(pkg["price"], order_ref)
        order_id = order_resp.get("order_id") or order_resp.get("id") or order_resp.get("data", {}).get("order_id")
        payment_url = order_resp.get("payment_url") or order_resp.get("url") or order_resp.get("data", {}).get("payment_url")
        if not order_id:
            await query_cb.edit_message_text(
                "❌ Payment gateway error.\nPlease try again later.",
                reply_markup=main_menu_button())
            return
        context.user_data["pending_dfpay_order"] = order_id
        context.user_data["pending_package"] = package_key
        # Generate QR from payment URL or UPI
        from qr_payment import generate_qr_with_text
        qr_buf, _ = generate_qr_with_text(package_key, pkg["price"], pkg["label"], UPI_ID)
        from datetime import datetime, timedelta
        qr_expiry = (datetime.now() + timedelta(minutes=30)).strftime("%I:%M %p")
        text = (
            f"<b>{pkg['label']}</b>\n"
            f"Price: <b>Rs.{pkg['price']}</b>\n\n"
            f"Scan the QR below to pay.\n"
            f"UPI ID: <code>{UPI_ID}</code>\n"
            f"Amount: <b>Rs.{pkg['price']} (Exact)</b>\n\n"
            f"⏱️ Expires at: <b>{qr_expiry}</b>\n\n"
            f"Payment will be verified automatically!")
        if payment_url:
            buttons = [
                [InlineKeyboardButton("💳 Pay Now", url=payment_url)],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")],
            ]
        else:
            buttons = [
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")],
            ]
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=qr_buf,
            caption=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        # Start polling for payment status
        if context.job_queue:
            context.job_queue.run_once(
                _payment_poll_job,
                when=15,
                data={"user_id": user_id, "order_id": order_id, "package_key": package_key, "chat_id": update.effective_chat.id, "attempts": 0},
                name=f"poll_{order_id}",
            )
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

    if data.startswith("qr_paid_"):
        # User tapped confirm — now expecting UTR
        parts = data.split("_")
        token = parts[2]
        package_key = "_".join(parts[3:])
        context.user_data["awaiting_utr"] = True
        context.user_data["pending_qr_token"] = token
        context.user_data["pending_package"] = package_key
        try:
            await query_cb.edit_message_text(
                "Send your <b>UTR / Transaction ID</b> now.\n\n"
                "It is a 12-digit number found in your UPI payment confirmation.",
                parse_mode="HTML", reply_markup=main_menu_button())
        except BadRequest:
            await query_cb.message.reply_text(
                "Send your UTR / Transaction ID now.",
                reply_markup=main_menu_button())
        return
        return

    if data == "cancel_payment":
        pending_order = context.user_data.get("pending_dfpay_order", "")
        pending_token = context.user_data.get("pending_qr_token", "")
        context.user_data.pop("awaiting_screenshot", None)
        context.user_data.pop("awaiting_utr", None)
        context.user_data.pop("pending_qr_token", None)
        context.user_data.pop("pending_dfpay_order", None)
        context.user_data.pop("pending_package", None)
        # Cancel polling and expiry jobs
        if context.job_queue:
            if pending_order:
                for job in context.job_queue.get_jobs_by_name(f"poll_{pending_order}"):
                    job.schedule_removal()
            if pending_token:
                for job in context.job_queue.get_jobs_by_name(f"qr_{pending_token}"):
                    job.schedule_removal()
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
    db.update_transaction_status(tx_id, "approved")
    db.set_subscription(user.id, pkg["duration_hours"])
    try: uds.save_payment(user.id, user.username or user.first_name, awaiting, pkg["price"], "approved", tx_id)
    except Exception: pass
    context.user_data.pop("awaiting_screenshot", None)
    context.user_data.pop("pending_package", None)
    await update.message.reply_text(
        f"Payment Screenshot Received!\n\n"
        f"Package: {pkg['label']}\n"
        f"Amount: Rs.{pkg['price']}\n"
        f"Subscription Activated!\n\n"
        f"You now have unlimited lookups!",
        reply_markup=main_menu_keyboard(is_admin=_is_admin(update.effective_user.id)), parse_mode="HTML")
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(chat_id=admin_id, photo=screenshot_file_id,
                caption=f"Payment from {user.first_name} (#{tx_id}) - {pkg['label']} Rs.{pkg['price']} - AUTO-APPROVED",
                parse_mode="HTML")
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

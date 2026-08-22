import logging
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.error import Conflict, TimedOut, NetworkError

import database as db
import api_client
from config import BOT_TOKEN, ADMIN_IDS
from handlers import (
    start,
    help_command,
    contact_admin,
    handle_redeem_code,
    process_redeem_code,
    buy_plan,
    handle_callback,
    handle_ip_lookup,
    handle_numinfo_lookup,
    handle_name_lookup,
    handle_vehicle_full_lookup,
    handle_parivahan_lookup,
    handle_hotx_lookup,
    handle_aadhaar_lookup,
    status_command,
    check_user_channels,
)
from admin import (
    admin_start,
    admin_activate_plan,
    admin_add_credits,
    admin_check_user,
    admin_create_code,
    admin_view_codes,
    admin_total_users,
    admin_lookup_history,
    admin_broadcast,
    handle_admin_text,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def _periodic_sync_job(context) -> None:
    try:
        db.periodic_sync()
    except Exception as e:
        logger.error(f"Periodic sync failed: {e}")


async def error_handler(update: object, context) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if isinstance(context.error, Conflict):
        logger.warning("Conflict detected - another instance may be running.")
        return
    if isinstance(context.error, (TimedOut, NetworkError)):
        logger.warning(f"Network error: {context.error}")
        return
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("An error occurred. Please try again.")
        except Exception:
            pass


def _strip_emojis(text):
    import re
    return re.sub(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0000FE00-\U0000FE0F\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]+', '', text).strip()


async def handle_text(update: Update, context):
    raw_text = update.message.text.strip()
    text = _strip_emojis(raw_text)

    if update.effective_user.id in ADMIN_IDS:
        handled = await handle_admin_text(update, context)
        if handled:
            return

    if context.user_data.get("awaiting_redeem_code"):
        context.user_data.pop("awaiting_redeem_code", None)
        await process_redeem_code(update, context)
        return

    if text == "IP Lookup":
        context.user_data.pop("awaiting_numinfo", None)
        context.user_data.pop("awaiting_name", None)
        context.user_data.pop("awaiting_vehicle_full", None)
        context.user_data.pop("awaiting_parivahan", None)
        context.user_data.pop("awaiting_hotx", None)
        context.user_data.pop("awaiting_aadhaar", None)
        await update.message.reply_text(
            "Enter a valid IP address:\nExample: 8.8.8.8\n\nOr tap any button to cancel.",
            parse_mode="HTML",
        )
        context.user_data["awaiting_ip"] = True
        return

    if text == "Num Info":
        context.user_data.pop("awaiting_ip", None)
        context.user_data.pop("awaiting_name", None)
        context.user_data.pop("awaiting_vehicle_full", None)
        context.user_data.pop("awaiting_parivahan", None)
        context.user_data.pop("awaiting_hotx", None)
        context.user_data.pop("awaiting_aadhaar", None)
        await update.message.reply_text(
            "Enter a 10-digit phone number:\nExample: 9876543210\n\nOr tap any button to cancel.",
            parse_mode="HTML",
        )
        context.user_data["awaiting_numinfo"] = True
        return

    if text == "Name Info":
        context.user_data.pop("awaiting_ip", None)
        context.user_data.pop("awaiting_numinfo", None)
        context.user_data.pop("awaiting_vehicle_full", None)
        context.user_data.pop("awaiting_parivahan", None)
        context.user_data.pop("awaiting_hotx", None)
        context.user_data.pop("awaiting_aadhaar", None)
        await update.message.reply_text(
            "Enter a name to lookup:\nExample: Rahul Kumar\n\nOr tap any button to cancel.",
            parse_mode="HTML",
        )
        context.user_data["awaiting_name"] = True
        return

    if text == "Vehicle Lookup":
        context.user_data.pop("awaiting_ip", None)
        context.user_data.pop("awaiting_numinfo", None)
        context.user_data.pop("awaiting_name", None)
        context.user_data.pop("awaiting_parivahan", None)
        context.user_data.pop("awaiting_hotx", None)
        context.user_data.pop("awaiting_aadhaar", None)
        await update.message.reply_text(
            "Enter vehicle registration number:\nExample: UK06BL1506\n\nOr tap any button to cancel.",
            parse_mode="HTML",
        )
        context.user_data["awaiting_vehicle_full"] = True
        return

    if text == "M-Parivahan":
        context.user_data.pop("awaiting_ip", None)
        context.user_data.pop("awaiting_numinfo", None)
        context.user_data.pop("awaiting_name", None)
        context.user_data.pop("awaiting_vehicle_full", None)
        context.user_data.pop("awaiting_hotx", None)
        context.user_data.pop("awaiting_aadhaar", None)
        await update.message.reply_text(
            "Enter vehicle registration number:\nExample: MP09BH4640\n\nOr tap any button to cancel.",
            parse_mode="HTML",
        )
        context.user_data["awaiting_parivahan"] = True
        return

    if text == "HotX Lookup":
        context.user_data.pop("awaiting_ip", None)
        context.user_data.pop("awaiting_numinfo", None)
        context.user_data.pop("awaiting_name", None)
        context.user_data.pop("awaiting_vehicle_full", None)
        context.user_data.pop("awaiting_parivahan", None)
        context.user_data.pop("awaiting_aadhaar", None)
        await update.message.reply_text(
            "Enter a 10-digit phone number:\nExample: 9876543210\n\nOr tap any button to cancel.",
            parse_mode="HTML",
        )
        context.user_data["awaiting_hotx"] = True
        return

    if text == "Aadhaar Family":
        context.user_data.pop("awaiting_ip", None)
        context.user_data.pop("awaiting_numinfo", None)
        context.user_data.pop("awaiting_name", None)
        context.user_data.pop("awaiting_vehicle_full", None)
        context.user_data.pop("awaiting_parivahan", None)
        context.user_data.pop("awaiting_hotx", None)
        await update.message.reply_text(
            "Enter a 12-digit Aadhaar number:\nExample: 123456789012\n\nOr tap any button to cancel.",
            parse_mode="HTML",
        )
        context.user_data["awaiting_aadhaar"] = True
        return

    routes = {
        "Buy Plan": "buy",
        "Redeem Code": "redeem",
        "Help": "help",
        "Contact Admin": "contact",
        "Admin Panel": "admin",
    }

    if text in routes:
        context.user_data.pop("awaiting_ip", None)
        context.user_data.pop("awaiting_numinfo", None)
        context.user_data.pop("awaiting_name", None)
        context.user_data.pop("awaiting_vehicle_full", None)
        context.user_data.pop("awaiting_parivahan", None)
        context.user_data.pop("awaiting_hotx", None)
        context.user_data.pop("awaiting_aadhaar", None)
        route = routes[text]
        if route == "buy":
            await buy_plan(update, context)
        elif route == "redeem":
            await handle_redeem_code(update, context)
        elif route == "help":
            await help_command(update, context)
        elif route == "contact":
            await contact_admin(update, context)
        elif route == "admin":
            await admin_start(update, context)
        return

    admin_routes = {
        "Total Users": admin_total_users,
        "Lookup History": admin_lookup_history,
        "Activate Plan": admin_activate_plan,
        "Add Credits": admin_add_credits,
        "Check User": admin_check_user,
        "Create Code": admin_create_code,
        "View All Codes": admin_view_codes,
        "Broadcast": admin_broadcast,
        "API Health": status_command,
        "Main Menu": admin_start,
    }

    if text in admin_routes and update.effective_user.id in ADMIN_IDS:
        context.user_data.pop("awaiting_ip", None)
        context.user_data.pop("awaiting_numinfo", None)
        context.user_data.pop("awaiting_name", None)
        context.user_data.pop("awaiting_vehicle_full", None)
        context.user_data.pop("awaiting_parivahan", None)
        context.user_data.pop("awaiting_hotx", None)
        context.user_data.pop("awaiting_aadhaar", None)
        await admin_routes[text](update, context)
        return

    if update.effective_user.id not in ADMIN_IDS:
        is_member, not_joined = await check_user_channels(update.effective_user.id, context.bot)
        if not is_member:
            channel_list = "\n".join([f"  {ch}" for ch in not_joined])
            join_text = (
                f"Join Required Channels!\n\n{channel_list}\n\nJoin then tap verify."
            )
            await update.message.reply_text(
                join_text,
                reply_markup=required_channels_keyboard(),
                parse_mode="HTML",
            )
            return

    if context.user_data.get("awaiting_ip"):
        context.user_data.pop("awaiting_ip", None)
        await handle_ip_lookup(update, context)
        return

    if context.user_data.get("awaiting_numinfo"):
        context.user_data.pop("awaiting_numinfo", None)
        await handle_numinfo_lookup(update, context)
        return

    if context.user_data.get("awaiting_name"):
        context.user_data.pop("awaiting_name", None)
        await handle_name_lookup(update, context)
        return

    if context.user_data.get("awaiting_vehicle_full"):
        context.user_data.pop("awaiting_vehicle_full", None)
        await handle_vehicle_full_lookup(update, context)
        return

    if context.user_data.get("awaiting_parivahan"):
        context.user_data.pop("awaiting_parivahan", None)
        await handle_parivahan_lookup(update, context)
        return

    if context.user_data.get("awaiting_hotx"):
        context.user_data.pop("awaiting_hotx", None)
        await handle_hotx_lookup(update, context)
        return

    if context.user_data.get("awaiting_aadhaar"):
        context.user_data.pop("awaiting_aadhaar", None)
        await handle_aadhaar_lookup(update, context)
        return

    await start(update, context)


async def handle_photo(update: Update, context):
    if context.user_data.get("awaiting_screenshot"):
        await handle_screenshot(update, context)


async def handle_document(update: Update, context):
    if context.user_data.get("awaiting_screenshot"):
        await handle_screenshot(update, context)


def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("Error: Set your BOT_TOKEN in .env file!")
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    db.init_db()
    print("Database initialized")

    db.sync_from_json()

    app = ApplicationBuilder().token(BOT_TOKEN).get_updates_read_timeout(10).get_updates_connect_timeout(10).build()

    private_filter = filters.ChatType.PRIVATE

    app.add_handler(CommandHandler("start", start, filters=private_filter))
    app.add_handler(CommandHandler("help", help_command, filters=private_filter))
    app.add_handler(CommandHandler("admin", admin_start, filters=private_filter))
    app.add_handler(CommandHandler("status", status_command, filters=private_filter))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & private_filter, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO & private_filter, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL & private_filter, handle_document))
    app.add_error_handler(error_handler)

    print("HathixShadow OSINT Bot starting...")
    print(f"Admin IDs: {ADMIN_IDS}")

    if app.job_queue:
        api_client.start_health_monitor(app.job_queue, bot=app.bot)
        app.job_queue.run_repeating(
            _periodic_sync_job,
            interval=300,
            first=60,
            name="periodic_data_sync",
        )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=2.0,
    )


if __name__ == "__main__":
    main()

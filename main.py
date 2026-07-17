import logging
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
from config import BOT_TOKEN, ADMIN_IDS, API_RELAY_URL
from handlers import (
    start,
    help_command,
    contact_admin,
    handle_redeem_code,
    process_redeem_code,
    buy_plan,
    handle_callback,
    handle_lookup,
    handle_screenshot,
    demo_result,
    demo_upi,
    demo_vehicle,
    handle_approve_command,
    handle_reject_command,
    check_user_channels,
    handle_upi_lookup,
    handle_vehicle_lookup,
)
from keyboards import required_channels_keyboard
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


async def error_handler(update: object, context) -> None:
    """Handle errors gracefully."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    if isinstance(context.error, Conflict):
        logger.warning("Conflict detected - another instance may be running. Retrying...")
        return
    
    if isinstance(context.error, (TimedOut, NetworkError)):
        logger.warning(f"Network error: {context.error}")
        return

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An error occurred. Please try again."
            )
        except Exception:
            pass


async def handle_text(update: Update, context):
    """Route text messages to the correct handler."""
    text = update.message.text.strip()

    # Admin text handler first
    if update.effective_user.id in ADMIN_IDS:
        handled = await handle_admin_text(update, context)
        if handled:
            return

    # Check if awaiting screenshot - allow without channel check
    if context.user_data.get("awaiting_screenshot"):
        await update.message.reply_text(
            "📸 Please send a <b>photo</b> or <b>document</b> as the payment screenshot.",
            parse_mode="HTML",
        )
        return

    # Check if awaiting redeem code
    if context.user_data.get("awaiting_redeem_code"):
        context.user_data.pop("awaiting_redeem_code", None)
        await process_redeem_code(update, context)
        return

    # Route by button text FIRST (before awaiting_number check)
    # This prevents button presses from being treated as phone number input
    if text == "📱 Phone Lookup":
        # Clear any previous awaiting state
        context.user_data.pop("awaiting_number", None)
        context.user_data.pop("awaiting_upi", None)
        context.user_data.pop("awaiting_vehicle", None)
        await update.message.reply_text(
            "🔍 <b>Enter Phone Number:</b>\n\n"
            "Type the 10-digit phone number:\n"
            "Example: <code>9876543210</code>\n\n"
            "Returns name, address, SIM details, leak data & more.\n\n"
            "💡 Or tap any button to cancel.",
            parse_mode="HTML",
        )
        context.user_data["awaiting_number"] = True
        return

    if text == "💳 UPI Lookup":
        context.user_data.pop("awaiting_number", None)
        context.user_data.pop("awaiting_vehicle", None)
        await update.message.reply_text(
            "💳 <b>Enter Phone Number for UPI Lookup:</b>\n\n"
            "Type the 10-digit phone number:\n"
            "Example: <code>9876543210</code>\n\n"
            "💡 Or tap any button to cancel.",
            parse_mode="HTML",
        )
        context.user_data["awaiting_upi"] = True
        return

    if text == "🚗 Vehicle Lookup":
        context.user_data.pop("awaiting_number", None)
        context.user_data.pop("awaiting_upi", None)
        await update.message.reply_text(
            "🚗 <b>Enter Vehicle Registration Number:</b>\n\n"
            "Type the plate number:\n"
            "Example: <code>MH12AB1234</code>\n\n"
            "💡 Or tap any button to cancel.",
            parse_mode="HTML",
        )
        context.user_data["awaiting_vehicle"] = True
        return

    routes = {
        "💰 Buy Plan": "buy",
        "🎁 Redeem Code": "redeem",
        "❓ Help Guide": "help",
        "🤳 Contact Admin": "contact",
        "🔧 Admin Panel": "admin",
    }

    if text in routes:
        # Clear all awaiting states when other buttons are pressed
        context.user_data.pop("awaiting_number", None)
        context.user_data.pop("awaiting_upi", None)
        context.user_data.pop("awaiting_vehicle", None)
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

    # Admin panel buttons
    admin_routes = {
        "👥 Total Users": admin_total_users,
        "🔍 Lookup History": admin_lookup_history,
        "✅ Activate Plan": admin_activate_plan,
        "💳 Add Credits": admin_add_credits,
        "👤 Check User": admin_check_user,
        "🎁 Create Code": admin_create_code,
        "📋 View All Codes": admin_view_codes,
        "📢 Broadcast": admin_broadcast,
        "🏠 Main Menu": admin_start,
    }

    if text in admin_routes and update.effective_user.id in ADMIN_IDS:
        context.user_data.pop("awaiting_number", None)
        context.user_data.pop("awaiting_upi", None)
        context.user_data.pop("awaiting_vehicle", None)
        await admin_routes[text](update, context)
        return

    # Enforce channel join for non-admins on all user routes
    if update.effective_user.id not in ADMIN_IDS:
        is_member, not_joined = await check_user_channels(update.effective_user.id, context.bot)
        if not is_member:
            channel_list = "\n".join([f"• {ch}" for ch in not_joined])
            join_text = (
                "🔴 <b>Join Required Channels!</b>\n\n"
                "You must join the following channels before using this bot:\n\n"
                f"{channel_list}\n\n"
                "After joining, tap the button below to verify."
            )
            await update.message.reply_text(
                join_text,
                reply_markup=required_channels_keyboard(),
                parse_mode="HTML",
            )
            return

    # If awaiting number for lookup - NOW process it (after button routing)
    if context.user_data.get("awaiting_number"):
        context.user_data.pop("awaiting_number", None)
        # Channel check happens inside handle_lookup
        await handle_lookup(update, context)
        return

    # If awaiting number for UPI lookup
    if context.user_data.get("awaiting_upi"):
        context.user_data.pop("awaiting_upi", None)
        context.args = [text]
        await handle_upi_lookup(update, context)
        return

    # If awaiting vehicle plate for vehicle lookup
    if context.user_data.get("awaiting_vehicle"):
        context.user_data.pop("awaiting_vehicle", None)
        context.args = [text]
        await handle_vehicle_lookup(update, context)
        return

    # Default: show main menu
    await start(update, context)


async def handle_photo(update: Update, context):
    """Handle photo uploads (payment screenshots)."""
    if context.user_data.get("awaiting_screenshot"):
        await handle_screenshot(update, context)


async def handle_document(update: Update, context):
    """Handle document uploads (payment screenshots)."""
    if context.user_data.get("awaiting_screenshot"):
        await handle_screenshot(update, context)


def main():
    """Start the bot."""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Error: Set your BOT_TOKEN in .env file or environment variables!")
        print("Create a .env file with: BOT_TOKEN=your_token_here")
        return

    db.init_db()
    print("✅ Database initialized")

    app = ApplicationBuilder().token(BOT_TOKEN).read_timeout(10).connect_timeout(10).build()

    # Only respond in private chats (DMs) - ignore all group messages/commands
    private_filter = filters.ChatType.PRIVATE

    # Command handlers (DM only)
    app.add_handler(CommandHandler("start", start, filters=private_filter))
    app.add_handler(CommandHandler("help", help_command, filters=private_filter))
    app.add_handler(CommandHandler("admin", admin_start, filters=private_filter))
    app.add_handler(CommandHandler("demo", demo_result, filters=private_filter))
    app.add_handler(CommandHandler("demo_upi", demo_upi, filters=private_filter))
    app.add_handler(CommandHandler("demo_vehicle", demo_vehicle, filters=private_filter))
    app.add_handler(CommandHandler("approve", handle_approve_command, filters=private_filter))
    app.add_handler(CommandHandler("reject", handle_reject_command, filters=private_filter))
    app.add_handler(CommandHandler("upi", handle_upi_lookup, filters=private_filter))
    app.add_handler(CommandHandler("vehicle", handle_vehicle_lookup, filters=private_filter))

    # Callback handler (inline buttons)
    # Note: CallbackQueryHandler in v21.0 does not support `filters`.
    # Private-chat filtering is done inside handle_callback itself.
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Text message handler (DM only)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & private_filter, handle_text))

    # Photo/document handler (payment screenshots) - DM only
    app.add_handler(MessageHandler(filters.PHOTO & private_filter, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL & private_filter, handle_document))

    # Add error handler
    app.add_error_handler(error_handler)

    print("🚀 Phone OSINT Bot is starting...")
    print(f"👤 Admin IDs: {ADMIN_IDS}")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=2.0,
    )


if __name__ == "__main__":
    main()

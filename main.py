import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

import database as db
from config import BOT_TOKEN, ADMIN_IDS
from handlers import (
    start,
    help_command,
    profile,
    balance,
    history,
    buy_credits,
    handle_callback,
    handle_lookup,
    handle_screenshot,
)
from admin import (
    admin_start,
    admin_stats,
    admin_pending,
    admin_add_credits,
    admin_ban,
    admin_unban,
    admin_user_lookup,
    handle_admin_text,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def handle_text(update: Update, context):
    """Route text messages to the correct handler."""
    text = update.message.text.strip()

    # Admin text handler first
    if update.effective_user.id in ADMIN_IDS:
        handled = await handle_admin_text(update, context)
        if handled:
            return

    # Check if awaiting screenshot
    if context.user_data.get("awaiting_screenshot"):
        await update.message.reply_text(
            "\U0001f4f8 Please send a <b>photo</b> or <b>document</b> as the payment screenshot.",
            parse_mode="HTML",
        )
        return

    # Route by button text
    routes = {
        "\U0001f50d Phone Lookup": "lookup",
        "\U0001f4b0 My Balance": "balance",
        "\U0001f4b3 Buy Credits": "buy",
        "\U0001f4cb My History": "history",
        "\U0001f4dd Help": "help",
        "\U0001f464 Profile": "profile",
    }

    if text in routes:
        route = routes[text]
        if route == "lookup":
            await update.message.reply_text(
                "\U0001f50d <b>Enter Phone Number:</b>\n\n"
                "Type the 10-digit phone number:\n"
                "Example: <code>9876543210</code>",
                parse_mode="HTML",
            )
            context.user_data["awaiting_number"] = True
        elif route == "balance":
            await balance(update, context)
        elif route == "buy":
            await buy_credits(update, context)
        elif route == "history":
            await history(update, context)
        elif route == "help":
            await help_command(update, context)
        elif route == "profile":
            await profile(update, context)
        return

    # Admin buttons
    admin_routes = {
        "\U0001f4ca Stats": admin_stats,
        "\U0001f4e6 Pending Payments": admin_pending,
        "\U0001f4b0 Add Credits": admin_add_credits,
        "\U0001f6ab Ban User": admin_ban,
        "\U0001f6ab Unban User": admin_unban,
        "\U0001f464 User Lookup": admin_user_lookup,
        "\U0001f519 Main Menu": admin_start,
    }

    if text in admin_routes and update.effective_user.id in ADMIN_IDS:
        await admin_routes[text](update, context)
        return

    # If awaiting number for lookup
    if context.user_data.get("awaiting_number"):
        context.user_data.pop("awaiting_number", None)
        await handle_lookup(update, context)
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
        print("\u274c Error: Set your BOT_TOKEN in .env file or environment variables!")
        print("Create a .env file with: BOT_TOKEN=your_token_here")
        return

    # Initialize database
    db.init_db()
    print("\u2705 Database initialized")

    # Build application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_start))

    # Callback handler (inline buttons)
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Text message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Photo/document handler (payment screenshots)
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("\U0001f680 Phone OSINT Bot is starting...")
    print(f"\U0001f464 Admin IDs: {ADMIN_IDS}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

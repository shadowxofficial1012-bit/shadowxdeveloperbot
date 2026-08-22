"""
DFPAY Webhook Server
Receives payment confirmation webhooks and activates user subscriptions.
Runs alongside the Telegram bot.
"""

import os
import json
import logging
import threading
from flask import Flask, request, jsonify

import database as db
import user_data_store as uds
from config import SUBSCRIPTION_PACKAGES, ADMIN_IDS

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Store bot instance for sending notifications
_bot = None
_loop = None


def set_bot_instance(bot, loop):
    """Set the bot instance for sending notifications."""
    global _bot, _loop
    _bot = bot
    _loop = loop


@app.route("/webhook/dfpay", methods=["POST"])
def dfpay_webhook():
    """Handle DFPAY payment confirmation webhook."""
    try:
        data = request.get_json(force=True)
        logger.info(f"DFPAY webhook received: {json.dumps(data)}")

        # Extract order info (adapt to DFPAY's actual webhook format)
        order_id = (
            data.get("order_id")
            or data.get("id")
            or data.get("data", {}).get("order_id")
            or data.get("data", {}).get("id")
        )
        status = (
            data.get("status")
            or data.get("data", {}).get("status")
        )
        order_ref = (
            data.get("order_ref")
            or data.get("reference")
            or data.get("data", {}).get("order_ref")
        )

        if not order_id:
            logger.warning("DFPAY webhook: missing order_id")
            return jsonify({"error": "missing order_id"}), 400

        # Check if payment is successful
        success_statuses = ("paid", "completed", "success", "CAPTURED", "captured")
        if status not in success_statuses:
            logger.info(f"DFPAY webhook: order {order_id} status={status} (not success)")
            return jsonify({"status": "ignored"}), 200

        # Parse order_ref to get user_id and package_key
        # Format: {user_id}_{package_key}_{timestamp}
        if not order_ref:
            logger.warning(f"DFPAY webhook: order {order_id} missing order_ref")
            return jsonify({"error": "missing order_ref"}), 400

        parts = order_ref.split("_")
        if len(parts) < 2:
            logger.warning(f"DFPAY webhook: invalid order_ref format: {order_ref}")
            return jsonify({"error": "invalid order_ref"}), 400

        try:
            user_id = int(parts[0])
            package_key = parts[1]
        except (ValueError, IndexError):
            logger.warning(f"DFPAY webhook: cannot parse order_ref: {order_ref}")
            return jsonify({"error": "invalid order_ref"}), 400

        if package_key not in SUBSCRIPTION_PACKAGES:
            logger.warning(f"DFPAY webhook: unknown package: {package_key}")
            return jsonify({"error": "unknown package"}), 400

        pkg = SUBSCRIPTION_PACKAGES[package_key]
        duration_hours = pkg["duration_hours"]

        # Check if already activated (idempotent)
        if db.has_active_subscription(user_id):
            logger.info(f"DFPAY webhook: user {user_id} already has active subscription")
            return jsonify({"status": "already_activated"}), 200

        # Activate subscription
        db.set_subscription(user_id, duration_hours)
        tx_id = db.create_transaction(user_id, package_key, duration_hours, pkg["price"])
        db.update_transaction_status(tx_id, "approved")

        try:
            uds.save_payment(user_id, f"user_{user_id}", package_key, pkg["price"], "approved", tx_id)
        except Exception:
            pass

        logger.info(f"DFPAY webhook: user {user_id} subscription activated ({duration_hours}h)")

        # Notify user
        if _bot and _loop:
            import asyncio
            asyncio.run_coroutine_threadsafe(
                _notify_user(user_id, package_key, pkg, duration_hours),
                _loop,
            )

        # Notify admins
        if _bot and _loop:
            import asyncio
            asyncio.run_coroutine_threadsafe(
                _notify_admins(user_id, package_key, pkg, order_id),
                _loop,
            )

        return jsonify({"status": "activated", "user_id": user_id, "hours": duration_hours}), 200

    except Exception as e:
        logger.error(f"DFPAY webhook error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/webhook/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


async def _notify_user(user_id, package_key, pkg, duration_hours):
    """Send activation notification to user."""
    try:
        await _bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ <b>Payment Verified!</b>\n\n"
                f"<b>{pkg['label']}</b> activated!\n"
                f"You now have unlimited lookups for {duration_hours}h.\n\n"
                f"Enjoy!"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")


async def _notify_admins(user_id, package_key, pkg, order_id):
    """Notify all admins about the payment."""
    for admin_id in ADMIN_IDS:
        try:
            await _bot.send_message(
                chat_id=admin_id,
                text=(
                    f"💰 Payment Auto-Verified (Webhook)\n"
                    f"User: #{user_id}\n"
                    f"Package: {pkg['label']} Rs.{pkg['price']}\n"
                    f"Order: {order_id}\n"
                    f"✅ Activated immediately"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass


def start_webhook_server(bot, loop, port=5000):
    """Start the webhook server in a background thread."""
    set_bot_instance(bot, loop)
    thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    thread.start()
    logger.info(f"DFPAY webhook server started on port {port}")
    return thread

import os
import sqlite3
import secrets
import string
import logging
from datetime import datetime
from datetime import datetime, timedelta
from config import DB_PATH, FREE_TRIAL_HOURS, SUBSCRIPTION_PACKAGES

logger = logging.getLogger(__name__)


def get_db():
    # Ensure the database directory exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sync_from_json():
    """Restore subscriptions and user data from user_data.json into SQLite.
    Called on startup to ensure data survives redeployments.
    """
    try:
        import user_data_store as uds
        data = uds._load_data()
        users = data.get("users", {})
        if not users:
            return

        synced = 0
        conn = get_db()
        c = conn.cursor()

        for user_key, user_data in users.items():
            user_id = user_data.get("user_id")
            if not user_id:
                continue

            # Check if user exists in SQLite
            c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            existing = c.fetchone()

            sub = user_data.get("subscription", {})
            sub_expiry = sub.get("expiry") if sub else None
            sub_status = sub.get("status") if sub else None

            if existing:
                # User exists in SQLite — update subscription if JSON has a later expiry
                current_expiry = existing["subscription_expiry"]
                if sub_expiry and sub_status == "active":
                    if not current_expiry:
                        # No expiry in SQLite, restore from JSON
                        c.execute("UPDATE users SET subscription_expiry = ? WHERE user_id = ?",
                                  (sub_expiry, user_id))
                        synced += 1
                    else:
                        # Both have expiry — keep the later one
                        try:
                            json_dt = datetime.fromisoformat(sub_expiry)
                            db_dt = datetime.fromisoformat(current_expiry)
                            if json_dt > db_dt:
                                c.execute("UPDATE users SET subscription_expiry = ? WHERE user_id = ?",
                                          (sub_expiry, user_id))
                                synced += 1
                        except (ValueError, TypeError):
                            pass
            else:
                # User doesn't exist in SQLite — create from JSON
                username = user_data.get("username")
                first_name = user_data.get("first_name")
                total_lookups = user_data.get("total_lookups", 0)
                c.execute(
                    "INSERT INTO users (user_id, username, first_name, total_lookups, subscription_expiry) VALUES (?, ?, ?, ?, ?)",
                    (user_id, username, first_name, total_lookups, sub_expiry or ""),
                )
                synced += 1

        # Also sync ban status from JSON → SQLite
            if user_data.get("is_banned") and not (existing and existing["is_banned"]):
                c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
                synced += 1

        # Also restore transactions from JSON
        payments = data.get("payments", [])
        for payment in payments:
            if payment.get("status") == "approved":
                tx_id_db = payment.get("tx_id")
                if tx_id_db:
                    # Check if transaction already exists in SQLite
                    c.execute("SELECT id FROM transactions WHERE id = ?", (tx_id_db,))
                    if not c.fetchone():
                        c.execute(
                            "INSERT INTO transactions (id, user_id, package, duration_hours, amount, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (tx_id_db, payment.get("user_id"), payment.get("package"),
                             SUBSCRIPTION_PACKAGES.get(payment.get("package", ""), {}).get("duration_hours", 24),
                             payment.get("amount", 0), "approved",
                             payment.get("timestamp", datetime.now().isoformat())),
                        )
                        synced += 1

        conn.commit()
        conn.close()
        if synced > 0:
            logger.info(f"Synced {synced} records from user_data.json to database")
        else:
            logger.debug("No new data to sync from user_data.json")

    except Exception as e:
        logger.warning(f"Sync from JSON failed: {e}")


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            credits INTEGER DEFAULT 0,
            total_lookups INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            subscription_expiry TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add subscription_expiry column if missing (for existing DB migration)
    try:
        c.execute("ALTER TABLE users ADD COLUMN subscription_expiry TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            package TEXT,
            duration_hours INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            screenshot_file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Migration: rename credits_added to duration_hours if old column exists
    try:
        c.execute("ALTER TABLE transactions RENAME COLUMN credits_added TO duration_hours")
    except sqlite3.OperationalError:
        pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS lookup_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            success INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS lookup_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            api_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # Redeem codes table
    c.execute("""
        CREATE TABLE IF NOT EXISTS redeem_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            hours INTEGER NOT NULL DEFAULT 24,
            is_used INTEGER DEFAULT 0,
            used_by INTEGER,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used_at TIMESTAMP
        )
    """)

    # QR Payment tokens table
    c.execute("""
        CREATE TABLE IF NOT EXISTS qr_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            package TEXT,
            amount INTEGER,
            upi_id TEXT,
            is_used INTEGER DEFAULT 0,
            used_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    # UTR tracking table
    c.execute("""
        CREATE TABLE IF NOT EXISTS utr_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            utr TEXT UNIQUE NOT NULL,
            user_id INTEGER,
            is_used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    conn.commit()
    conn.close()


def get_or_create_user(user_id, username=None, first_name=None):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()

    if user is None:
        c.execute(
            "INSERT INTO users (user_id, username, first_name, credits, subscription_expiry) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, first_name, 0, ""),
        )
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
    else:
        updates = []
        params = []
        if username:
            updates.append("username = ?")
            params.append(username)
        if first_name:
            updates.append("first_name = ?")
            params.append(first_name)
        updates.append("last_active = CURRENT_TIMESTAMP")
        params.append(user_id)

        if updates:
            c.execute(f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?", params)
            conn.commit()
            c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = c.fetchone()

    conn.close()
    return dict(user) if user else None


def has_active_subscription(user_id):
    """Check if a user has an active (non-expired) subscription."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT subscription_expiry FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row or not row["subscription_expiry"]:
        return False
    try:
        expiry = datetime.fromisoformat(row["subscription_expiry"])
        return datetime.now() < expiry
    except (ValueError, TypeError):
        return False


def get_subscription_expiry(user_id):
    """Get the subscription expiry date string for a user."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT subscription_expiry FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["subscription_expiry"] if row and row["subscription_expiry"] else ""


def set_subscription(user_id, duration_hours):
    """Set/extend a user's subscription. Extends from current expiry or now."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT subscription_expiry FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    
    now = datetime.now()
    if row and row["subscription_expiry"]:
        try:
            current_expiry = datetime.fromisoformat(row["subscription_expiry"])
            if current_expiry > now:
                new_expiry = current_expiry + timedelta(hours=duration_hours)
            else:
                new_expiry = now + timedelta(hours=duration_hours)
        except (ValueError, TypeError):
            new_expiry = now + timedelta(hours=duration_hours)
    else:
        new_expiry = now + timedelta(hours=duration_hours)
    
    expiry_str = new_expiry.isoformat()
    c.execute("UPDATE users SET subscription_expiry = ? WHERE user_id = ?", (expiry_str, user_id))
    conn.commit()
    conn.close()
    return expiry_str


def record_lookup(user_id):
    """Increment the total_lookups counter for a user."""
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET total_lookups = total_lookups + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def create_transaction(user_id, package, duration_hours, amount, screenshot_file_id=None):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO transactions (user_id, package, duration_hours, amount, screenshot_file_id) VALUES (?, ?, ?, ?, ?)",
        (user_id, package, duration_hours, amount, screenshot_file_id),
    )
    tx_id = c.lastrowid
    conn.commit()
    conn.close()
    return tx_id


def update_transaction_status(tx_id, status):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE transactions SET status = ?, processed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, tx_id),
    )
    conn.commit()
    conn.close()


def get_pending_transactions():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE status = 'pending' ORDER BY created_at DESC")
    txs = [dict(row) for row in c.fetchall()]
    conn.close()
    return txs


def get_user_transactions(user_id, limit=10):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    txs = [dict(row) for row in c.fetchall()]
    conn.close()
    return txs


def log_lookup(user_id, username, success):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO lookup_log (user_id, username, success) VALUES (?, ?, ?)",
        (user_id, username, int(success)),
    )
    conn.commit()
    conn.close()


def save_lookup_result(user_id, username, api_data_json: str):
    """Save full API response for re-export without using credits."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO lookup_cache (user_id, username, api_data) VALUES (?, ?, ?)",
        (user_id, username, api_data_json),
    )
    conn.commit()
    conn.close()


def get_lookup_cache(user_id, query):
    """Get the most recent cached lookup for a user by query."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM lookup_cache WHERE user_id = ? AND username = ? ORDER BY created_at DESC LIMIT 1",
        (user_id, query),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_lookup_history(user_id, limit=10):
    """Get recent lookups for a user."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id, username, created_at FROM lookup_cache WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    )
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_lookup_by_id(lookup_id: int, user_id: int):
    """Get a specific cached lookup by ID (must belong to user)."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM lookup_cache WHERE id = ? AND user_id = ?",
        (lookup_id, user_id),
    )
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def set_credits(user_id, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET credits = ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users ORDER BY created_at DESC")
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return users


def get_recent_lookups(limit=15):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, success, created_at FROM lookup_log ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_user_count():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as count FROM users")
    count = c.fetchone()["count"]
    conn.close()
    return count


def ban_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def unban_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def is_banned(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["is_banned"] == 1 if row else False


def get_stats():
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) as total_users FROM users")
    total_users = c.fetchone()["total_users"]

    c.execute("SELECT COALESCE(SUM(total_lookups), 0) as total_lookups FROM users")
    total_lookups = c.fetchone()["total_lookups"]

    c.execute("SELECT COALESCE(SUM(amount), 0) as total_revenue FROM transactions WHERE status = 'approved'")
    total_revenue = c.fetchone()["total_revenue"]

    c.execute("SELECT COUNT(*) as pending FROM transactions WHERE status = 'pending'")
    pending = c.fetchone()["pending"]

    c.execute("SELECT COALESCE(SUM(duration_hours), 0) as total_hours FROM transactions WHERE status = 'approved'")
    total_hours_issued = c.fetchone()["total_hours"]

    conn.close()
    return {
        "total_users": total_users,
        "total_lookups": total_lookups,
        "total_revenue": total_revenue,
        "pending_transactions": pending,
        "total_hours_issued": total_hours_issued,
    }


# ==================== REDEEM CODE FUNCTIONS ====================

def generate_redeem_code(hours=24, created_by=None):
    """Generate a new redeem code."""
    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(10))
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO redeem_codes (code, hours, created_by) VALUES (?, ?, ?)",
        (code, hours, created_by),
    )
    conn.commit()
    conn.close()
    return code


def generate_bulk_codes(count=5, hours=24, created_by=None):
    """Generate multiple redeem codes."""
    codes = []
    for _ in range(count):
        code = generate_redeem_code(hours, created_by)
        codes.append(code)
    return codes


def redeem_code(code, user_id):
    """Redeem a code for a user. Returns (success, message, hours)."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM redeem_codes WHERE code = ?", (code.upper().strip(),))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return False, "❌ Invalid redeem code!", 0
    
    code_data = dict(row)
    
    if code_data["is_used"]:
        conn.close()
        return False, "❌ This code has already been used!", 0
    
    # Mark as used
    c.execute(
        "UPDATE redeem_codes SET is_used = 1, used_by = ?, used_at = CURRENT_TIMESTAMP WHERE code = ?",
        (user_id, code_data["code"]),
    )
    conn.commit()
    conn.close()
    
    # Activate subscription
    hours = code_data["hours"]
    expiry = set_subscription(user_id, hours)
    
    return True, f"✅ Code redeemed! {hours}h subscription activated.\nExpires: {expiry[:16]}", hours


def get_all_redeem_codes(limit=50):
    """Get all redeem codes (admin view)."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM redeem_codes ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_redeem_code_stats():
    """Get redeem code statistics."""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) as total FROM redeem_codes")
    total = c.fetchone()["total"]
    
    c.execute("SELECT COUNT(*) as used FROM redeem_codes WHERE is_used = 1")
    used = c.fetchone()["used"]
    
    c.execute("SELECT COUNT(*) as unused FROM redeem_codes WHERE is_used = 0")
    unused = c.fetchone()["unused"]
    
    conn.close()
    return {"total": total, "used": used, "unused": unused}


# ==================== QR PAYMENT FUNCTIONS ====================

def create_qr_payment(token, user_id, package, amount, upi_id):
    """Create a new QR payment record."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO qr_payments (token, user_id, package, amount, upi_id) VALUES (?, ?, ?, ?, ?)",
        (token, user_id, package, amount, upi_id),
    )
    conn.commit()
    conn.close()


def get_qr_payment_by_token(token):
    """Get a QR payment record by token."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM qr_payments WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def mark_qr_used(token, user_id):
    """Mark a QR payment token as used."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "UPDATE qr_payments SET is_used = 1, used_by = ?, used_at = CURRENT_TIMESTAMP WHERE token = ?",
        (user_id, token),
    )
    conn.commit()
    conn.close()


def get_pending_qr_payments():
    """Get all pending QR payments (unused tokens in last 30 min)."""
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """SELECT * FROM qr_payments 
           WHERE is_used = 0 
           AND datetime(created_at) > datetime('now', '-30 minutes')
           ORDER BY created_at DESC"""
    )
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


# ==================== UTR FUNCTIONS ====================

def is_utr_used(utr: str) -> bool:
    """Check if a UTR has already been submitted."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM utr_records WHERE utr = ?", (utr,))
    row = c.fetchone()
    conn.close()
    return row is not None


def mark_utr_used(utr: str, user_id: int):
    """Mark a UTR as used."""
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO utr_records (utr, user_id, is_used) VALUES (?, ?, 1)",
            (utr, user_id),
        )
    except sqlite3.IntegrityError:
        pass  # UTR already exists
    conn.commit()
    conn.close()


# ==================== BIDIRECTIONAL SYNC ====================

_last_sync_time = None

def sync_to_json():
    """Sync data FROM SQLite TO user_data.json.
    Updates lookup counts, ban status, and subscription expiry in JSON.
    """
    try:
        import user_data_store as uds

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT user_id, username, first_name, total_lookups, is_banned, subscription_expiry FROM users")
        sqlite_users = {row["user_id"]: dict(row) for row in c.fetchall()}
        conn.close()

        data = uds._load_data()
        users = data.get("users", {})
        updated = 0

        for user_key, user_data in users.items():
            user_id = user_data.get("user_id")
            if not user_id or user_id not in sqlite_users:
                continue

            sq = sqlite_users[user_id]

            # Sync lookup count (use higher of the two)
            json_lookups = user_data.get("total_lookups", 0)
            sq_lookups = sq.get("total_lookups", 0)
            if sq_lookups > json_lookups:
                user_data["total_lookups"] = sq_lookups
                updated += 1

            # Sync ban status from SQLite → JSON
            if sq.get("is_banned") and not user_data.get("is_banned"):
                user_data["is_banned"] = True
                updated += 1
            elif not sq.get("is_banned") and user_data.get("is_banned"):
                user_data["is_banned"] = False
                updated += 1

            # Sync subscription expiry (use the later one)
            sq_expiry = sq.get("subscription_expiry")
            sub = user_data.get("subscription", {})
            json_expiry = sub.get("expiry") if sub else None

            if sq_expiry:
                if not json_expiry:
                    # SQLite has expiry but JSON doesn't — restore it
                    sub["expiry"] = sq_expiry
                    if sub.get("status") != "active":
                        sub["status"] = "active"
                    updated += 1
                else:
                    # Both have expiry — keep the later one
                    try:
                        sq_dt = datetime.fromisoformat(sq_expiry)
                        json_dt = datetime.fromisoformat(json_expiry)
                        if sq_dt > json_dt:
                            sub["expiry"] = sq_expiry
                            updated += 1
                    except (ValueError, TypeError):
                        pass

        if updated > 0:
            uds._save_data(data)
            logger.info(f"Synced {updated} fields from SQLite to user_data.json")
        else:
            logger.debug("SQLite → JSON: no changes needed")

    except Exception as e:
        logger.warning(f"Sync to JSON failed: {e}")


def periodic_sync():
    """Run bidirectional sync: JSON → SQLite then SQLite → JSON.
    Called periodically by the JobQueue.
    """
    global _last_sync_time
    try:
        sync_from_json()
        sync_to_json()
        _last_sync_time = datetime.now().isoformat()
        logger.info("Periodic SQLite ↔ JSON sync completed")
    except Exception as e:
        logger.warning(f"Periodic sync failed: {e}")


def get_last_sync_time():
    """Return the last successful sync timestamp."""
    return _last_sync_time

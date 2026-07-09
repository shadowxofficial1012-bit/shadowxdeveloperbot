import os
import sqlite3
from datetime import datetime
from config import DB_PATH, FREE_CREDITS


def get_db():
    # Ensure the database directory exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            package TEXT,
            credits_added INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            screenshot_file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

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

    conn.commit()
    conn.close()


def get_or_create_user(user_id, username=None, first_name=None):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()

    if user is None:
        c.execute(
            "INSERT INTO users (user_id, username, first_name, credits) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, FREE_CREDITS),
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


def get_credits(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["credits"] if row else 0


def use_credit(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits - 1, total_lookups = total_lookups + 1 WHERE user_id = ? AND credits > 0", (user_id,))
    changed = c.rowcount
    conn.commit()
    conn.close()
    return changed > 0


def add_credits(user_id, amount):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def create_transaction(user_id, package, credits, amount, screenshot_file_id=None):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO transactions (user_id, package, credits_added, amount, screenshot_file_id) VALUES (?, ?, ?, ?, ?)",
        (user_id, package, credits, amount, screenshot_file_id),
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

    c.execute("SELECT COALESCE(SUM(credits_added), 0) as total_credits FROM transactions WHERE status = 'approved'")
    total_credits_issued = c.fetchone()["total_credits"]

    conn.close()
    return {
        "total_users": total_users,
        "total_lookups": total_lookups,
        "total_revenue": total_revenue,
        "pending_transactions": pending,
        "total_credits_issued": total_credits_issued,
    }

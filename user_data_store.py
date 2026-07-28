"""
User Data Store - Single JSON file storing ALL user data:
- User profile info
- Subscription status & history
- Payment/transaction records
- Lookup history & usage stats

This file persists across bot restarts and gives you a complete overview
of every user's activity and payments in one place.
"""

import json
import os
from datetime import datetime
from typing import Optional

# Default path for the unified data store
USER_DATA_FILE = os.getenv("USER_DATA_FILE", "user_data.json")


def _load_data() -> dict:
    """Load data from JSON file."""
    if not os.path.exists(USER_DATA_FILE):
        return {
            "users": {},
            "lookups": [],
            "payments": [],
            "metadata": {
                "created": datetime.now().isoformat(),
                "version": "2.0",
                "total_users": 0,
                "total_lookups": 0,
                "total_payments": 0,
                "total_revenue": 0,
            },
        }
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {
            "users": {},
            "lookups": [],
            "payments": [],
            "metadata": {
                "created": datetime.now().isoformat(),
                "version": "2.0",
            },
        }


def _save_data(data: dict) -> None:
    """Save data to JSON file with updated metadata."""
    # Update metadata stats
    users = data.get("users", {})
    payments = data.get("payments", [])
    lookups = data.get("lookups", [])

    total_revenue = sum(
        p.get("amount", 0) for p in payments if p.get("status") == "approved"
    )

    data["metadata"]["last_updated"] = datetime.now().isoformat()
    data["metadata"]["total_users"] = len(users)
    data["metadata"]["total_lookups"] = len(lookups)
    data["metadata"]["total_payments"] = len(payments)
    data["metadata"]["total_revenue"] = total_revenue

    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"[UserStore] Error saving data: {e}")


# ==================== USER PROFILE ====================


def save_user(user_id: int, username: str = None, first_name: str = None) -> None:
    """Save or update user profile information."""
    data = _load_data()
    user_key = str(user_id)

    if user_key not in data["users"]:
        data["users"][user_key] = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "first_seen": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "is_banned": False,
            "total_lookups": 0,
            "subscription": {
                "status": "inactive",
                "package": None,
                "expiry": None,
                "activated_at": None,
            },
            "total_spent": 0,
            "transactions": [],
            "lookup_history": [],
        }
    else:
        user = data["users"][user_key]
        if username:
            user["username"] = username
        if first_name:
            user["first_name"] = first_name
        user["last_active"] = datetime.now().isoformat()

    _save_data(data)


# ==================== SUBSCRIPTION ====================


def save_subscription(user_id: int, package: str, amount: int, expiry: str) -> None:
    """Save subscription activation for a user."""
    data = _load_data()
    user_key = str(user_id)

    # Ensure user exists
    if user_key not in data["users"]:
        data["users"][user_key] = {
            "user_id": user_id,
            "username": None,
            "first_name": None,
            "first_seen": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "is_banned": False,
            "total_lookups": 0,
            "total_spent": 0,
            "transactions": [],
            "lookup_history": [],
        }

    user = data["users"][user_key]
    user["subscription"] = {
        "status": "active",
        "package": package,
        "expiry": expiry,
        "activated_at": datetime.now().isoformat(),
        "amount_paid": amount,
    }
    user["last_active"] = datetime.now().isoformat()

    _save_data(data)


def get_subscription_info(user_id: int) -> Optional[dict]:
    """Get subscription info for a user."""
    data = _load_data()
    user_key = str(user_id)
    user = data["users"].get(user_key)
    if user:
        return user.get("subscription")
    return None


# ==================== PAYMENTS / TRANSACTIONS ====================


def save_payment(
    user_id: int,
    username: str,
    package: str,
    amount: int,
    status: str = "pending",
    tx_id: int = None,
) -> None:
    """Save a payment/transaction record."""
    data = _load_data()
    user_key = str(user_id)

    payment_entry = {
        "id": len(data.get("payments", [])) + 1,
        "user_id": user_id,
        "username": username,
        "package": package,
        "amount": amount,
        "status": status,  # pending, approved, rejected
        "tx_id": tx_id,
        "timestamp": datetime.now().isoformat(),
    }

    data["payments"].append(payment_entry)

    # Also add to user's transaction list
    if user_key in data["users"]:
        user = data["users"][user_key]
        if "transactions" not in user:
            user["transactions"] = []
        user["transactions"].append({
            "id": payment_entry["id"],
            "package": package,
            "amount": amount,
            "status": status,
            "timestamp": payment_entry["timestamp"],
        })
        # Keep last 50 transactions per user
        user["transactions"] = user["transactions"][-50:]

    # Cap payments list (keep last 2000)
    if len(data.get("payments", [])) > 2000:
        data["payments"] = data["payments"][-2000:]

    _save_data(data)


def update_payment_status(payment_id: int, status: str) -> None:
    """Update payment status (approved/rejected)."""
    data = _load_data()

    # Update in global payments list
    for payment in data.get("payments", []):
        if payment.get("id") == payment_id:
            payment["status"] = status
            payment["processed_at"] = datetime.now().isoformat()
            break

    # Update in user's transaction list
    for user in data["users"].values():
        for tx in user.get("transactions", []):
            if tx.get("id") == payment_id:
                tx["status"] = status
                break

    # Update user's total_spent if approved
    if status == "approved":
        for payment in data.get("payments", []):
            if payment.get("id") == payment_id:
                user_key = str(payment["user_id"])
                if user_key in data["users"]:
                    data["users"][user_key]["total_spent"] = (
                        data["users"][user_key].get("total_spent", 0)
                        + payment.get("amount", 0)
                    )
                break

    _save_data(data)


def get_user_payments(user_id: int) -> list:
    """Get all payments for a user."""
    data = _load_data()
    return [
        p for p in data.get("payments", [])
        if p.get("user_id") == user_id
    ]


def get_all_payments(limit: int = 50) -> list:
    """Get all recent payments."""
    data = _load_data()
    return data.get("payments", [])[-limit:]


# ==================== LOOKUPS / USAGE ====================


def save_lookup(
    user_id: int,
    username: str,
    lookup_type: str,
    query: str,
    result: dict,
    success: bool = True,
) -> None:
    """Save a lookup result associated with a user."""
    data = _load_data()
    user_key = str(user_id)

    # Update user lookup count
    if user_key in data["users"]:
        data["users"][user_key]["total_lookups"] = (
            data["users"][user_key].get("total_lookups", 0) + 1
        )
        data["users"][user_key]["last_active"] = datetime.now().isoformat()

    # Create lookup entry
    lookup_entry = {
        "id": len(data.get("lookups", [])) + 1,
        "user_id": user_id,
        "username": username,
        "lookup_type": lookup_type,
        "query": query,
        "result": result,
        "success": success,
        "timestamp": datetime.now().isoformat(),
    }

    data["lookups"].append(lookup_entry)

    # Add to user's lookup history (keep last 50)
    if user_key in data["users"]:
        if "lookup_history" not in data["users"][user_key]:
            data["users"][user_key]["lookup_history"] = []
        data["users"][user_key]["lookup_history"].append({
            "id": lookup_entry["id"],
            "lookup_type": lookup_type,
            "query": query,
            "success": success,
            "timestamp": lookup_entry["timestamp"],
        })
        data["users"][user_key]["lookup_history"] = data["users"][user_key]["lookup_history"][-50:]

    # Cap lookups list (keep last 1000)
    if len(data.get("lookups", [])) > 1000:
        data["lookups"] = data["lookups"][-1000:]

    _save_data(data)


def get_user_lookups(user_id: int, limit: int = 10) -> list:
    """Get lookup history for a specific user."""
    data = _load_data()
    return [
        l for l in data.get("lookups", [])
        if l.get("user_id") == user_id
    ][-limit:]


# ==================== FULL USER DATA ====================


def get_user_full_data(user_id: int) -> Optional[dict]:
    """Get ALL data for a user — profile, subscription, payments, lookups."""
    data = _load_data()
    user_key = str(user_id)
    user = data["users"].get(user_key)
    if not user:
        return None

    # Enrich with payment and lookup data
    user_payments = [
        p for p in data.get("payments", [])
        if p.get("user_id") == user_id
    ]
    user_lookups = [
        l for l in data.get("lookups", [])
        if l.get("user_id") == user_id
    ]

    return {
        **user,
        "all_payments": user_payments,
        "all_lookups": user_lookups,
        "total_paid": sum(
            p.get("amount", 0) for p in user_payments if p.get("status") == "approved"
        ),
    }


def get_all_users() -> list:
    """Get all stored users."""
    data = _load_data()
    return list(data["users"].values())


def get_all_lookups(limit: int = 50) -> list:
    """Get recent lookups across all users."""
    data = _load_data()
    return data.get("lookups", [])[-limit:]


# ==================== BAN ====================


def set_ban(user_id: int, banned: bool = True) -> None:
    """Ban or unban a user."""
    data = _load_data()
    user_key = str(user_id)
    if user_key in data["users"]:
        data["users"][user_key]["is_banned"] = banned
        _save_data(data)


def is_banned(user_id: int) -> bool:
    """Check if a user is banned."""
    data = _load_data()
    user_key = str(user_id)
    user = data["users"].get(user_key)
    return user.get("is_banned", False) if user else False


# ==================== SEARCH ====================


def search_users(query: str) -> list:
    """Search users by username, first_name, or user_id."""
    data = _load_data()
    query_lower = query.lower()
    return [
        u for u in data["users"].values()
        if query_lower in str(u.get("username", "")).lower()
        or query_lower in str(u.get("first_name", "")).lower()
        or query_lower in str(u.get("user_id", "")).lower()
    ]


# ==================== STATS ====================


def get_stats() -> dict:
    """Get comprehensive statistics."""
    data = _load_data()
    users = data.get("users", {})
    payments = data.get("payments", [])
    lookups = data.get("lookups", [])

    approved_payments = [p for p in payments if p.get("status") == "approved"]
    pending_payments = [p for p in payments if p.get("status") == "pending"]
    total_revenue = sum(p.get("amount", 0) for p in approved_payments)

    # Lookup type breakdown
    lookup_types = {}
    for l in lookups:
        lt = l.get("lookup_type", "unknown")
        lookup_types[lt] = lookup_types.get(lt, 0) + 1

    # Active subscriptions
    active_subs = sum(
        1 for u in users.values()
        if u.get("subscription", {}).get("status") == "active"
    )

    return {
        "total_users": len(users),
        "active_subscriptions": active_subs,
        "total_lookups": len(lookups),
        "lookup_types": lookup_types,
        "total_payments": len(payments),
        "approved_payments": len(approved_payments),
        "pending_payments": len(pending_payments),
        "total_revenue": total_revenue,
        "created": data.get("metadata", {}).get("created"),
        "last_updated": data.get("metadata", {}).get("last_updated"),
    }

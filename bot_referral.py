#!/usr/bin/env python3
"""
VITAMAN — Referral System

Manages referral codes, tracking, and rewards.

How it works:
1. Each customer gets a unique referral code after purchase
2. When a friend uses the code, both get a discount
3. Referral data is stored in data/referrals.json

Integration with bot_new.py:
    from bot_referral import create_referral_code, validate_referral, apply_referral_reward
"""

import json
import logging
import os
import secrets
import string
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REFERRALS_FILE = os.path.join(DATA_DIR, "referrals.json")
COUPONS_FILE = os.path.join(DATA_DIR, "coupons.json")

# Config
REFERRAL_REWARD_PERCENT = 15  # Referrer gets 15% off next order
FRIEND_DISCOUNT_PERCENT = 10  # Friend gets 10% off first order
REFERRAL_CODE_PREFIX = "REF"


def _load_referrals() -> Dict[str, Any]:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(REFERRALS_FILE):
        return {"referrals": {}, "uses": []}
    try:
        with open(REFERRALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"referrals": {}, "uses": []}


def _save_referrals(data: Dict[str, Any]) -> None:
    import tempfile
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, REFERRALS_FILE)
    except Exception:
        with open(REFERRALS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _load_coupons() -> Dict[str, Any]:
    if not os.path.exists(COUPONS_FILE):
        return {"codes": {}}
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"codes": {}}


def _save_coupons(data: Dict[str, Any]) -> None:
    import tempfile
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, COUPONS_FILE)
    except Exception:
        with open(COUPONS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def _generate_code() -> str:
    """Generate a unique referral code like REF-A3K9 using cryptographic randomness."""
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(4))
    return f"{REFERRAL_CODE_PREFIX}-{suffix}"


# ─── Public API ──────────────────────────────────────────────

def create_referral_code(user_id: int, username: Optional[str] = None) -> str:
    """Create a referral code for a customer. Returns the code."""
    db = _load_referrals()
    referrals = db.setdefault("referrals", {})

    # Check if user already has a code
    for code, info in referrals.items():
        if info.get("user_id") == user_id:
            return code

    # Generate unique code
    code = _generate_code()
    while code in referrals:
        code = _generate_code()

    referrals[code] = {
        "user_id": user_id,
        "username": username,
        "created_at": datetime.now().isoformat(),
        "total_referrals": 0,
        "total_earnings": 0,
    }

    db["referrals"] = referrals
    _save_referrals(db)

    logger.info("Created referral code %s for user %s", code, user_id)
    return code


def get_user_referral_code(user_id: int) -> Optional[str]:
    """Get existing referral code for user, if any."""
    db = _load_referrals()
    for code, info in db.get("referrals", {}).items():
        if info.get("user_id") == user_id:
            return code
    return None


def validate_referral(code: str, friend_user_id: int) -> Tuple[bool, str]:
    """
    Validate a referral code.
    Returns (is_valid, message).
    """
    code = code.strip().upper()
    db = _load_referrals()
    referrals = db.get("referrals", {})

    if code not in referrals:
        return False, "קוד הפניה לא תקין."

    referrer = referrals[code]

    # Can't refer yourself
    if referrer.get("user_id") == friend_user_id:
        return False, "לא ניתן להשתמש בקוד הפניה שלך."

    # Check if friend already used a referral
    uses = db.get("uses", [])
    already_used = any(u.get("friend_id") == friend_user_id for u in uses)
    if already_used:
        return False, "כבר השתמשת בקוד הפניה בעבר."

    return True, f"קוד תקין! תקבל {FRIEND_DISCOUNT_PERCENT}% הנחה על ההזמנה."


def apply_referral_reward(code: str, friend_user_id: int, order_total: int) -> Dict[str, Any]:
    """
    Apply referral: record the use, create reward coupon for referrer.
    Returns info about the rewards.
    """
    code = code.strip().upper()
    db = _load_referrals()
    referrals = db.get("referrals", {})
    uses = db.setdefault("uses", [])

    if code not in referrals:
        return {"success": False, "error": "Invalid code"}

    referrer = referrals[code]

    # Record the use
    uses.append({
        "code": code,
        "friend_id": friend_user_id,
        "referrer_id": referrer["user_id"],
        "order_total": order_total,
        "used_at": datetime.now().isoformat(),
    })

    # Update referrer stats
    referrer["total_referrals"] = referrer.get("total_referrals", 0) + 1
    referrer["total_earnings"] = referrer.get("total_earnings", 0) + REFERRAL_REWARD_PERCENT

    db["referrals"] = referrals
    db["uses"] = uses
    _save_referrals(db)

    # Create reward coupon for the referrer
    reward_code = f"REWARD-{referrer['user_id']}-{referrer['total_referrals']}"
    coupons = _load_coupons()
    coupons.setdefault("codes", {})[reward_code] = {
        "type": "percent",
        "value": REFERRAL_REWARD_PERCENT,
        "single_use": True,
        "created_for": referrer["user_id"],
        "created_at": datetime.now().isoformat(),
    }
    _save_coupons(coupons)

    return {
        "success": True,
        "friend_discount": FRIEND_DISCOUNT_PERCENT,
        "referrer_user_id": referrer["user_id"],
        "referrer_reward_code": reward_code,
        "referrer_reward_percent": REFERRAL_REWARD_PERCENT,
    }


def get_referral_stats(user_id: int) -> Dict[str, Any]:
    """Get referral stats for a user."""
    db = _load_referrals()
    code = get_user_referral_code(user_id)
    if not code:
        return {"has_code": False}

    info = db["referrals"].get(code, {})
    return {
        "has_code": True,
        "code": code,
        "total_referrals": info.get("total_referrals", 0),
        "total_earnings": info.get("total_earnings", 0),
    }


def get_referral_leaderboard(top_n: int = 10) -> List[Dict[str, Any]]:
    """Top referrers."""
    db = _load_referrals()
    referrals = db.get("referrals", {})

    leaderboard = []
    for code, info in referrals.items():
        if info.get("total_referrals", 0) > 0:
            leaderboard.append({
                "code": code,
                "username": info.get("username", "Unknown"),
                "referrals": info["total_referrals"],
            })

    leaderboard.sort(key=lambda x: x["referrals"], reverse=True)
    return leaderboard[:top_n]


# ─── Bot Message Templates ──────────────────────────────────

def referral_welcome_message(code: str) -> str:
    return (
        f"🎁 *תוכנית הפניות של VITAMAN*\n\n"
        f"הקוד האישי שלך: `{code}`\n\n"
        f"📤 שלח את הקוד לחבר — הוא יקבל *{FRIEND_DISCOUNT_PERCENT}% הנחה*\n"
        f"💰 ואתה תקבל קופון *{REFERRAL_REWARD_PERCENT}% הנחה* על ההזמנה הבאה!\n\n"
        f"כל חבר שמזמין = עוד קופון הנחה בשבילך 🔥"
    )


def referral_success_message_friend(discount: int) -> str:
    return f"✅ קוד ההפניה אושר! תקבל *{discount}% הנחה* על ההזמנה."


def referral_success_message_referrer(friend_name: str, reward_code: str, reward_percent: int) -> str:
    return (
        f"🎉 *יש לך הפניה חדשה!*\n\n"
        f"החבר {friend_name} ביצע הזמנה דרך הקוד שלך.\n\n"
        f"💰 קופון ההנחה שלך: `{reward_code}`\n"
        f"שווי: *{reward_percent}% הנחה* על ההזמנה הבאה!\n\n"
        f"המשך להפנות חברים ולצבור הנחות 💪"
    )

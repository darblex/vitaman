"""
Facebook Conversions API (CAPI) — server-side event tracking.

Sends purchase, add-to-cart, and view-content events directly from
the Telegram bot to Facebook, bypassing browser limitations.

Usage:
    from facebook.pixel import send_event
    send_event("Purchase", user_id=123, value=169, currency="ILS")
"""

import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

try:
    from config import cfg
    PIXEL_ID = cfg.FB_PIXEL_ID
    CAPI_TOKEN = cfg.FB_CAPI_TOKEN
except ImportError:
    PIXEL_ID = os.environ.get("FB_PIXEL_ID", "")
    CAPI_TOKEN = os.environ.get("FB_CAPI_TOKEN", "")

GRAPH_API = "https://graph.facebook.com/v21.0"


def _hash_sha256(value: str) -> str:
    """Hash PII for Facebook matching (required by CAPI)."""
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def _build_user_data(
    user_id: Optional[int] = None,
    phone: Optional[str] = None,
    first_name: Optional[str] = None,
    city: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the user_data object with hashed PII."""
    ud: Dict[str, Any] = {
        "client_user_agent": "TelegramBot/1.0",
        "country": [_hash_sha256("il")],
    }
    if user_id is not None:
        ud["external_id"] = [_hash_sha256(str(user_id))]
    if phone is not None:
        clean = phone.replace("-", "").replace(" ", "")
        if not clean.startswith("+"):
            clean = "+972" + clean.lstrip("0")
        ud["ph"] = [_hash_sha256(clean)]
    if first_name is not None:
        ud["fn"] = [_hash_sha256(first_name)]
    if city is not None:
        ud["ct"] = [_hash_sha256(city)]
    return ud


def send_event(
    event_name: str,
    user_id: Optional[int] = None,
    phone: Optional[str] = None,
    first_name: Optional[str] = None,
    city: Optional[str] = None,
    value: Optional[float] = None,
    currency: str = "ILS",
    content_name: Optional[str] = None,
    content_ids: Optional[List[str]] = None,
    order_id: Optional[str] = None,
    custom_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Send a single event to Facebook Conversions API.

    Supported events:
        - ViewContent  (user views a product)
        - AddToCart     (user adds to cart)
        - InitiateCheckout (user starts checkout)
        - Purchase      (order confirmed)
        - Lead          (user contacts seller)

    Returns True on success, False on failure.
    """
    if not PIXEL_ID or not CAPI_TOKEN:
        logger.warning("FB Pixel/CAPI not configured — skipping event %s", event_name)
        return False

    user_data = _build_user_data(user_id, phone, first_name, city)

    event: Dict[str, Any] = {
        "event_name": event_name,
        "event_time": int(time.time()),
        "action_source": "other",  # Telegram bot = "other"
        "user_data": user_data,
    }

    cd: Dict[str, Any] = custom_data.copy() if custom_data else {}
    if value is not None:
        cd["value"] = value
        cd["currency"] = currency
    if content_name:
        cd["content_name"] = content_name
    if content_ids:
        cd["content_ids"] = content_ids
        cd["content_type"] = "product"
    if order_id:
        cd["order_id"] = order_id
    if cd:
        event["custom_data"] = cd

    payload = {
        "data": json.dumps([event]),
        "access_token": CAPI_TOKEN,
    }

    url = f"{GRAPH_API}/{PIXEL_ID}/events"
    for attempt in range(3):
        try:
            resp = requests.post(url, data=payload, timeout=10)
            result = resp.json()
            if "error" in result:
                logger.error("CAPI error for %s: %s", event_name, result["error"])
                return False
            logger.info(
                "CAPI event sent: %s (events_received=%s)",
                event_name,
                result.get("events_received", "?"),
            )
            return True
        except requests.RequestException as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            logger.error("CAPI request failed for %s after 3 attempts: %s", event_name, e)
            return False


# ─── Convenience wrappers ────────────────────────────────────────

def track_view_content(user_id: int, product_key: str, product_name: str, price: float):
    return send_event(
        "ViewContent",
        user_id=user_id,
        value=price,
        content_name=product_name,
        content_ids=[product_key],
    )


def track_add_to_cart(user_id: int, product_key: str, product_name: str, price: float, qty: int = 1):
    return send_event(
        "AddToCart",
        user_id=user_id,
        value=price * qty,
        content_name=product_name,
        content_ids=[product_key],
        custom_data={"num_items": qty},
    )


def track_initiate_checkout(user_id: int, total: float, num_items: int):
    return send_event(
        "InitiateCheckout",
        user_id=user_id,
        value=total,
        custom_data={"num_items": num_items},
    )


def track_purchase(
    user_id: int,
    order_id: str,
    total: float,
    phone: Optional[str] = None,
    first_name: Optional[str] = None,
    city: Optional[str] = None,
    content_ids: Optional[List[str]] = None,
):
    return send_event(
        "Purchase",
        user_id=user_id,
        phone=phone,
        first_name=first_name,
        city=city,
        value=total,
        order_id=order_id,
        content_ids=content_ids,
    )


def track_lead(user_id: int, source: str = "telegram"):
    return send_event(
        "Lead",
        user_id=user_id,
        custom_data={"lead_source": source},
    )

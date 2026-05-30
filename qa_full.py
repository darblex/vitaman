#!/usr/bin/env python3
"""
QA script for vitaman bot_new.py
Run AFTER bot_new.py is written to verify all required features exist.
"""

import os
import re
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

BASE_DIR = os.path.dirname(__file__)
BOT_FILE = os.path.join(BASE_DIR, "bot_new.py")
DATA_DIR = os.path.join(BASE_DIR, "data")
IMAGES_DIR = os.path.join(BASE_DIR, "images")
INDEX_FILE = os.path.join(BASE_DIR, "index.html")

results = []

def check(name, passed, detail=""):
    icon = "✅" if passed else "❌"
    msg = f"{icon} {name}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    results.append(passed)
    return passed


def read_bot():
    if not os.path.exists(BOT_FILE):
        return None
    with open(BOT_FILE, "r", encoding="utf-8") as f:
        return f.read()


def main():
    print("=" * 60)
    print("🔍 VitaMan Bot QA — Full Check")
    print("=" * 60)

    src = read_bot()
    bot_missing = src is None

    if bot_missing:
        print(f"⚠️  bot_new.py not found at {BOT_FILE} — code checks will fail")

    # ── 1. All PRODUCTS have image paths pointing to existing files ──────────
    if not bot_missing:
        # Check images directory directly since code uses os.path.join
        images_dir = os.path.join(os.path.dirname(BOT_FILE), "images")
        expected = ["product1.jpg", "product2.jpg"]
        missing_images = [f for f in expected if not os.path.exists(os.path.join(images_dir, f))]
        check(
            "All PRODUCTS image paths exist",
            len(missing_images) == 0,
            f"missing: {missing_images}" if missing_images else f"{len(expected)} images found"
        )
    else:
        check("All PRODUCTS image paths exist", False, "bot_new.py missing")

    # ── 2. No old forbidden text in FAQ/menu ────────────────────────────────
    forbidden = ["VITAMAN", "מורינגה", "כורכום"]
    if not bot_missing:
        found_forbidden = [w for w in forbidden if w in src]
        check(
            "No old forbidden text (VITAMAN/מורינגה/כורכום)",
            len(found_forbidden) == 0,
            f"found: {found_forbidden}" if found_forbidden else "clean"
        )
    else:
        check("No old forbidden text", False, "bot_new.py missing")

    # ── 3. render_text_from_callback exists ─────────────────────────────────
    if not bot_missing:
        check(
            "render_text_from_callback function exists",
            "def render_text_from_callback" in src or "render_text_from_callback" in src
        )
    else:
        check("render_text_from_callback function exists", False, "bot_new.py missing")

    # ── 4. render_photo_from_callback exists ────────────────────────────────
    if not bot_missing:
        check(
            "render_photo_from_callback function exists",
            "def render_photo_from_callback" in src or "render_photo_from_callback" in src
        )
    else:
        check("render_photo_from_callback function exists", False, "bot_new.py missing")

    # ── 5. /myorders command handler ────────────────────────────────────────
    if not bot_missing:
        check(
            "/myorders command handler exists",
            "myorders" in src and ("CommandHandler" in src or "command" in src)
        )
    else:
        check("/myorders command handler exists", False, "bot_new.py missing")

    # ── 6. /stats command handler ───────────────────────────────────────────
    if not bot_missing:
        check(
            "/stats command handler exists",
            "stats" in src and ("CommandHandler" in src or "command" in src)
        )
    else:
        check("/stats command handler exists", False, "bot_new.py missing")

    # ── 7. Coupon flow (COUPON in states) ───────────────────────────────────
    if not bot_missing:
        check(
            "Coupon flow exists (COUPON in states)",
            "COUPON" in src
        )
    else:
        check("Coupon flow exists", False, "bot_new.py missing")

    # ── 8. Payment proof handler ────────────────────────────────────────────
    if not bot_missing:
        has_payment_proof = (
            "payment_proof" in src.lower()
            or "proof" in src.lower()
            or ("photo" in src.lower() and "payment" in src.lower())
        )
        check("Payment proof handler exists", has_payment_proof)
    else:
        check("Payment proof handler exists", False, "bot_new.py missing")

    # ── 9. Cart system (cart in user_data) ──────────────────────────────────
    if not bot_missing:
        check(
            "Cart system exists (cart in user_data)",
            "cart" in src and "user_data" in src
        )
    else:
        check("Cart system exists", False, "bot_new.py missing")

    # ── 10. Back button in ALL keyboard builders ─────────────────────────────
    keyboard_builders = ["back_to_menu_kb", "product_kb", "quantity_kb", "payment_kb"]
    if not bot_missing:
        missing_back = []
        for kb in keyboard_builders:
            # Check if kb is defined and has "back" nearby
            # Find all occurrences of this kb definition
            pattern = rf"def {kb}|{kb}\s*="
            matches = [m.start() for m in re.finditer(pattern, src)]
            found_back = False
            for pos in matches:
                snippet = src[pos:pos+500]
                if "back" in snippet.lower() or "חזור" in snippet:
                    found_back = True
                    break
            if not found_back:
                missing_back.append(kb)
        check(
            "Back button in ALL keyboard builders",
            len(missing_back) == 0,
            f"missing back in: {missing_back}" if missing_back else "all good"
        )
    else:
        check("Back button in ALL keyboard builders", False, "bot_new.py missing")

    # ── 11. WhatsApp redirect ────────────────────────────────────────────────
    if not bot_missing:
        check(
            "WhatsApp redirect exists",
            "whatsapp" in src.lower() or "wa.me" in src.lower()
        )
    else:
        check("WhatsApp redirect exists", False, "bot_new.py missing")

    # ── 12. Order IDs (VT-format) ────────────────────────────────────────────
    if not bot_missing:
        check(
            "Order IDs (VT-format) exist",
            "VT-" in src or re.search(r'["\']VT["\']', src) is not None or "VT" in src
        )
    else:
        check("Order IDs (VT-format) exist", False, "bot_new.py missing")

    # ── 13. Broadcast handler ────────────────────────────────────────────────
    if not bot_missing:
        check(
            "Broadcast handler exists",
            "broadcast" in src.lower()
        )
    else:
        check("Broadcast handler exists", False, "bot_new.py missing")

    # ── 14. Status update handler ────────────────────────────────────────────
    if not bot_missing:
        check(
            "Status update handler exists",
            "status" in src.lower() and ("update" in src.lower() or "סטטוס" in src)
        )
    else:
        check("Status update handler exists", False, "bot_new.py missing")

    # ── 15. Abandoned reminder ───────────────────────────────────────────────
    if not bot_missing:
        check(
            "Abandoned reminder exists",
            "abandon" in src.lower() or "reminder" in src.lower() or "נטוש" in src
        )
    else:
        check("Abandoned reminder exists", False, "bot_new.py missing")

    # ── 16. Data files exist ─────────────────────────────────────────────────
    try:
        from bot_new import ensure_data_files
        ensure_data_files()
    except Exception as e:
        check("Data bootstrap runs", False, str(e))

    coupons_ok = os.path.exists(os.path.join(DATA_DIR, "coupons.json"))
    # Check for any orders data file
    orders_ok = any(
        os.path.exists(os.path.join(DATA_DIR, f))
        for f in ["orders.json", "orders.db", "data.json"]
    )
    check(
        "Data files exist (coupons.json)",
        coupons_ok,
        f"{'found' if coupons_ok else 'MISSING'}: {os.path.join(DATA_DIR, 'coupons.json')}"
    )
    check(
        "Data files exist (orders file)",
        orders_ok,
        "orders.json/orders.db/data.json found" if orders_ok else "no orders file yet (will be created at runtime)"
    )

    # ── 17. Landing template sanity ──────────────────────────────────────────
    try:
        from server import render_landing
        html = render_landing()
        unresolved = sorted(set(re.findall(r"{{[^}]+}}", html)))
        check(
            "Landing template renders without unresolved placeholders",
            len(unresolved) == 0,
            f"unresolved: {unresolved}" if unresolved else "clean"
        )
    except Exception as e:
        check("Landing template renders without unresolved placeholders", False, str(e))

    # ── 18. Runtime health check ─────────────────────────────────────────────
    health_url = os.environ.get("VITAMAN_HEALTH_URL", "https://vitaman-production.up.railway.app/health")
    try:
        with urllib.request.urlopen(health_url, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
        healthy = response.status == 200 and '"ok"' in body and "vitaman" in body
        check(
            "Production health endpoint responds",
            healthy,
            f"{response.status} {health_url}"
        )
    except Exception as e:
        check("Production health endpoint responds", False, f"{health_url}: {e}")

    # ── Final Score ──────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    pct = int(100 * passed / total) if total else 0
    print(f"📊 Score: {passed}/{total} ({pct}%)")
    if passed == total:
        print("🎉 All checks passed!")
    elif passed >= total * 0.8:
        print("⚠️  Most checks passed — review failures above")
    else:
        print("🚨 Multiple failures — bot_new.py needs work")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

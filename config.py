"""Shared runtime config — all secrets from environment."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SELLER_CHAT_ID = int(os.environ.get("SELLER_CHAT_ID", "400023112"))
SELLER_USERNAME = os.environ.get("SELLER_USERNAME", "Darblex")
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "972523288147")

REMINDER_DELAY_SECONDS = int(os.environ.get("REMINDER_DELAY_SECONDS", "3600"))
MAX_QTY = int(os.environ.get("MAX_QTY", "5"))
DISCOUNT_THRESHOLD = int(os.environ.get("DISCOUNT_THRESHOLD", "3"))
DISCOUNT_PCT = int(os.environ.get("DISCOUNT_PCT", "10"))

FB_PIXEL_ID = os.environ.get("FB_PIXEL_ID", "")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "DrViagrashop_Bot")
LANDING_PAGE_URL = os.environ.get(
    "LANDING_PAGE_URL", "https://vitaman-production.up.railway.app"
)
SHOP_NAME = os.environ.get("SHOP_NAME", "DrViagra Shop")
PORT = int(os.environ.get("PORT", "8080"))

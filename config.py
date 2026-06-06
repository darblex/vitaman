"""Shared runtime config — all secrets from environment."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SELLER_CHAT_ID = int(os.environ.get("SELLER_CHAT_ID", "400023112"))
SELLER_USERNAME = os.environ.get("SELLER_USERNAME", "LILNONO0")

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

USE_POLLING = os.environ.get("USE_POLLING", "0") == "1"
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH", "/telegram/webhook")
WEBHOOK_BASE = os.environ.get("WEBHOOK_BASE", LANDING_PAGE_URL.rstrip("/"))

# Marketing automation
AUTO_POST_ENABLED = os.environ.get("AUTO_POST_ENABLED", "0") == "1"
AUTO_POST_CHANNEL_ID = os.environ.get("AUTO_POST_CHANNEL_ID", "")
AUTO_POST_TIMES = [
    x.strip() for x in os.environ.get("AUTO_POST_TIMES", "10:00,14:00,20:00").split(",") if x.strip()
]
AUTO_POST_TIMEZONE = os.environ.get("AUTO_POST_TIMEZONE", "Asia/Jerusalem")
AUTO_POST_SOURCE_TAG = os.environ.get("AUTO_POST_SOURCE_TAG", "auto")
AUTO_POSTS_FILE = os.environ.get("AUTO_POSTS_FILE", os.path.join(BASE_DIR, "marketing_posts.json"))

AUTO_REPORT_ENABLED = os.environ.get("AUTO_REPORT_ENABLED", "1") == "1"
AUTO_REPORT_CHAT_ID = int(os.environ.get("AUTO_REPORT_CHAT_ID", str(SELLER_CHAT_ID)))
AUTO_REPORT_TIME = os.environ.get("AUTO_REPORT_TIME", "22:00")
AUTO_REPORT_TIMEZONE = os.environ.get("AUTO_REPORT_TIMEZONE", "Asia/Jerusalem")

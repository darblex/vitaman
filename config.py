"""
Centralized config loader — reads .env and provides typed settings.
Usage:
    from config import cfg
    print(cfg.BOT_TOKEN)
"""

import os
from dataclasses import dataclass, field
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed — rely on real env vars


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int = 0) -> int:
    val = os.environ.get(key, "")
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


@dataclass(frozen=True)
class Config:
    # Telegram
    BOT_TOKEN: str = field(default_factory=lambda: _env("BOT_TOKEN"))
    SELLER_CHAT_ID: int = field(default_factory=lambda: _env_int("SELLER_CHAT_ID"))
    SELLER_USERNAME: str = field(default_factory=lambda: _env("SELLER_USERNAME"))
    WHATSAPP_NUMBER: str = field(default_factory=lambda: _env("WHATSAPP_NUMBER"))

    # Facebook Marketing
    FB_PAGE_ACCESS_TOKEN: str = field(default_factory=lambda: _env("FB_PAGE_ACCESS_TOKEN"))
    FB_PAGE_ID: str = field(default_factory=lambda: _env("FB_PAGE_ID"))
    FB_AD_ACCOUNT_ID: str = field(default_factory=lambda: _env("FB_AD_ACCOUNT_ID"))
    FB_APP_ID: str = field(default_factory=lambda: _env("FB_APP_ID"))
    FB_APP_SECRET: str = field(default_factory=lambda: _env("FB_APP_SECRET"))

    # Facebook Pixel / CAPI
    FB_PIXEL_ID: str = field(default_factory=lambda: _env("FB_PIXEL_ID"))
    FB_CAPI_TOKEN: str = field(default_factory=lambda: _env("FB_CAPI_TOKEN"))

    # Bot settings
    REMINDER_DELAY_SECONDS: int = field(default_factory=lambda: _env_int("REMINDER_DELAY_SECONDS", 3600))
    MAX_QTY: int = field(default_factory=lambda: _env_int("MAX_QTY", 5))
    DISCOUNT_THRESHOLD: int = field(default_factory=lambda: _env_int("DISCOUNT_THRESHOLD", 3))
    DISCOUNT_PCT: int = field(default_factory=lambda: _env_int("DISCOUNT_PCT", 10))

    # URLs
    LANDING_PAGE_URL: str = field(default_factory=lambda: _env("LANDING_PAGE_URL", "https://your-domain.com"))
    TELEGRAM_BOT_URL: str = field(default_factory=lambda: _env("TELEGRAM_BOT_URL", "https://t.me/your_bot"))

    def __post_init__(self):
        missing = []
        if not self.BOT_TOKEN:
            missing.append("BOT_TOKEN")
        if not self.SELLER_CHAT_ID:
            missing.append("SELLER_CHAT_ID")
        if missing:
            import warnings
            warnings.warn(
                f"Missing required config: {', '.join(missing)}. "
                "Set them in .env or environment variables.",
                stacklevel=2,
            )


cfg = Config()

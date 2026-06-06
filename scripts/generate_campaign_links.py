#!/usr/bin/env python3
"""Generate tracked Telegram deep links for campaigns."""

from __future__ import annotations

BOT_USERNAME = "DrViagrashop_Bot"

SOURCES = [
    "channel_bio",
    "channel_p1",
    "channel_p2",
    "channel_offer1",
    "channel_urgent1",
    "ad_a1",
    "ad_a2",
    "ad_retarget1",
    "collab_c1",
    "collab_c2",
    "group_g1",
    "group_g2",
]


def main() -> None:
    base = f"https://t.me/{BOT_USERNAME}?start="
    print("Tracked campaign links:\n")
    for src in SOURCES:
        print(f"{src:16} {base}{src}")


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""Generate product placeholder images for Telegram bot."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "images"
OUT.mkdir(parents=True, exist_ok=True)

PRODUCTS = [
    ("product1.jpg", "#1a2744", "Kamagra\nOral Jelly", "100mg"),
    ("product2.jpg", "#2d1a44", "Vidalista\n40mg", "Tadalafil"),
]


def main() -> None:
    for filename, bg, title, subtitle in PRODUCTS:
        img = Image.new("RGB", (900, 900), bg)
        draw = ImageDraw.Draw(img)
        draw.rectangle([(40, 40), (860, 860)], outline="#d4af37", width=6)
        try:
            font_l = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
            font_s = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
        except OSError:
            font_l = ImageFont.load_default()
            font_s = ImageFont.load_default()
        draw.multiline_text((450, 360), title, fill="#f7f3ea", font=font_l, anchor="mm", align="center")
        draw.text((450, 520), subtitle, fill="#d4af37", font=font_s, anchor="mm")
        draw.text((450, 760), "DrViagra Shop", fill="#b8ad96", font=font_s, anchor="mm")
        img.save(OUT / filename, quality=92)
        print("wrote", OUT / filename)


if __name__ == "__main__":
    main()

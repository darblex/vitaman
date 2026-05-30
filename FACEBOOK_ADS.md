# Facebook / Meta Ads Notes

## Current positioning

DrViagra Shop is positioned as a discreet Telegram ordering funnel for men, with fast human follow-up and simple checkout.

## Tracking

Landing page uses Meta Pixel placeholder `{{FB_PIXEL_ID}}`, rendered from Railway env `FB_PIXEL_ID`.

Events currently fired:
- `PageView`
- `Lead` on Telegram CTA clicks
- `Contact` on WhatsApp CTA clicks

## Deep links

Use product-specific links so the bot opens the right screen:

```text
https://t.me/DrViagrashop_Bot?start=fb_kamagra
https://t.me/DrViagrashop_Bot?start=fb_vidalista
https://t.me/DrViagrashop_Bot?start=fb_bundle
https://t.me/DrViagrashop_Bot?start=fb_hero
```

## Safer ad copy direction

Avoid strong medical claims and guaranteed outcomes. Keep copy around:
- discreet ordering
- simple process
- fast human response
- clear prices
- private packaging

Example:

```text
הזמנה דיסקרטית לגברים דרך טלגרם.
בוחרים מוצר, משאירים פרטים, ונציג חוזר אליך לסגירה מהירה.
משלוח דיסקרטי, תהליך קצר וברור.
```

## Operational KPI

- Landing CTR to Telegram
- Telegram `/start` count
- Product page clicks
- Cart starts
- Checkout completions
- WhatsApp handoff rate
- Closed orders by seller

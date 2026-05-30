# Telegram Store Blueprint — Current Version

## Funnel

```text
Landing / Ads → Telegram deep link → Bot splash → Store → Product → Cart → Checkout → Human closing
```

## Live links

- Landing: https://vitaman-production.up.railway.app
- Bot: https://t.me/DrViagrashop_Bot

## Main menu

- Kamagra Oral Jelly
- Vidalista
- Bundle
- Cart
- FAQ
- Contact

## Checkout fields

1. Name
2. City
3. Phone
4. Delivery method
5. Coupon
6. Payment method
7. Optional payment proof screenshot/document for non-cash payments

## Admin closeout

After checkout, the bot sends a structured order to `SELLER_CHAT_ID` with:
- Order ID
- Customer Telegram details
- Cart lines
- Delivery choice
- Payment choice
- Customer contact details
- Total price

The customer also gets a WhatsApp CTA to continue with the seller.

## Discount logic

- Automatic discount: `DISCOUNT_PCT` when quantity reaches `DISCOUNT_THRESHOLD`
- Coupons from `data/coupons.json` / `/data/coupons.json`

Default coupons:
- `SAVE10` — 10%
- `VIP20` — 20%

## Copy notes

Keep the bot direct and conversion-focused, but avoid risky medical promises:
- do not promise treatment/cure
- do not guarantee outcome
- do not invent medical authority
- use “מומלץ להתייעץ עם רופא/רוקח” when relevant

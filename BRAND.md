# Brand / Copy Guide

## Active brand

- Public shop name: `DrViagra Shop`
- Legacy project name: `vitaman`
- Tone: direct, discreet, simple, masculine, practical

## Visual style

- Dark background
- Gold accent
- Hebrew RTL-first
- Mobile-first landing
- Clear CTAs to Telegram and WhatsApp

## Copy rules

Use:
- “הזמנה דיסקרטית”
- “תהליך קצר וברור”
- “מענה אנושי”
- “משלוח דיסקרטי”
- “מומלץ להתייעץ עם רופא/רוקח”

Avoid:
- guaranteed outcomes
- cure/treatment claims
- exaggerated medical claims
- fake testimonials about exact medical effects
- “100% guaranteed” style promises

## Product pages

Products are managed in `bot_new.py` and reflected on `index.html`.

When changing prices or product names, update both places and run:

```bash
python3 -m compileall -q .
python3 qa_full.py
```

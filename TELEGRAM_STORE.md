# VITAMAN — Telegram Store Blueprint

## Best Structure
**Facebook Ads → Landing Page or Direct Telegram → Telegram Bot/Menu → Human Seller**

## Recommended Telegram Setup
### Option A — Fastest (recommended now)
1. Create a **Telegram channel** named: `VITAMAN | חנות טבעית לגברים`
2. Create a **Telegram bot** via @BotFather
3. Put the bot link in the Facebook ad and landing page
4. Bot shows menu and forwards buyer to your sales contact

---

## Bot Menu Flow
### Welcome message
שלום וברוך הבא ל-**VITAMAN** 💪

כאן תוכל לבחור את המוצר שמתאים לך:

1. מורינגה — ₪89
2. כורכום — ₪89
3. חבילת כוח — ₪149
4. שאלות נפוצות
5. דבר עם נציג

---

## Button Copy
### Main buttons
- מורינגה
- כורכום
- חבילת כוח
- שאלות נפוצות
- דבר עם נציג

### Product: מורינגה
**VITAMAN מורינגה**

תוסף טבעי לגברים שמחפשים יותר חיוניות, אנרגיה ושגרה חזקה יותר.

מחיר: **₪89**

לביצוע הזמנה לחץ למטה.

Buttons:
- הזמן עכשיו
- חזור לתפריט

### Product: כורכום
**VITAMAN כורכום**

תוסף טבעי לגברים שמחפשים תמיכה יומיומית ותחושת יציבות בשגרה.

מחיר: **₪89**

Buttons:
- הזמן עכשיו
- חזור לתפריט

### Product: חבילת כוח
**חבילת הכוח של VITAMAN**

מורינגה + כורכום במחיר משתלם.

מחיר: **₪149**

Buttons:
- הזמן עכשיו
- חזור לתפריט

---

## Cash / Manual Payment Flow
If you want manual closing instead of instant payment:

### Button: הזמן עכשיו
Message to buyer:
מעולה. כדי להשלים את ההזמנה, שלח עכשיו את הפרטים הבאים:

- שם מלא
- עיר
- טלפון
- המוצר שבחרת
- אמצעי תשלום מועדף: מזומן / ביט / פייבוקס / העברה

לאחר מכן נציג יחזור אליך לסגירה.

### Forward to seller
Route all orders to Telegram only:
- Representative username: `@lilnano0`

---

## FAQ Section
### שאלות נפוצות
**מה זה?**
תוספי תזונה טבעיים לגברים.

**איך מזמינים?**
בוחרים מוצר, משאירים פרטים, ונציג חוזר אליך.

**יש משלוח?**
כן / איסוף / בהתאם למה שתקבע.

**איך משלמים?**
מזומן, ביט, פייבוקס או בתיאום מול הנציג.

---

## What you still need to replace
- Bot username (if changed)
- Delivery wording
- Final prices if different

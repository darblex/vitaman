# VITAMAN Telegram Bot — Setup Guide

## מה הבוט עושה
תפריט כפתורים אינטראקטיבי מלא:

```
/start →
  🌿 מורינגה — ₪89
  🔥 כורכום — ₪89
  💪 חבילת כוח — ₪149
  ❓ שאלות נפוצות
  📞 דבר עם נציג
```

כל מוצר → תיאור + מחיר + כפתור **הזמן עכשיו**

הזמנה אוספת: שם → עיר → טלפון → אמצעי תשלום (כפתורים)

סיכום הזמנה מגיע ללקוח + נשלח אליך כהודעה.

---

## הקמה — 5 דקות

### שלב 1: צור בוט
1. פתח @BotFather בטלגרם
2. שלח `/newbot`
3. בחר שם: `VITAMAN Store`
4. בחר יוזר: `vitaman_store_bot` (או כל שם פנוי)
5. תקבל **API Token** — שמור אותו

### שלב 2: עדכן את הקוד
פתח `bot.py` ושנה:

```python
BOT_TOKEN = "123456:ABCdefGHIjklMNO..."   # ← הטוקן שקיבלת
SELLER_CHAT_ID = 123456789                  # ← ה-ID שלך בטלגרם
SELLER_USERNAME = "your_username"           # ← היוזר שלך
WHATSAPP_NUMBER = "972501234567"            # ← המספר שלך
```

💡 כדי למצוא את ה-Chat ID שלך: שלח הודעה ל-@userinfobot

### שלב 3: התקן והרץ
```bash
pip install python-telegram-bot==21.*
python3 bot.py
```

### שלב 4 (אופציונלי): הרצה קבועה
```bash
# עם screen
screen -S vitaman
python3 bot.py
# Ctrl+A, D לניתוק

# או עם systemd
sudo nano /etc/systemd/system/vitaman-bot.service
```

---

## התאמה אישית
- שנה מחירים ב-`PRODUCTS` dict
- שנה תיאורים
- הוסף מוצרים חדשים
- שנה שאלות נפוצות ב-`FAQ_TEXT`

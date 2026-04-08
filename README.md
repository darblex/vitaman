# VITAMAN — Full Marketing & Sales Platform

## מה זה?
פלטפורמת מכירות מלאה: בוט טלגרם + דף נחיתה + שיווק אוטומטי בפייסבוק.

## מבנה הפרויקט

### 🤖 בוט טלגרם
| קובץ | תפקיד |
|---|---|
| `bot_new.py` | בוט מלא — עגלה, קופונים, הזמנות, תשלום, Pixel, הפניות |
| `bot.py` | גרסה קודמת (גיבוי) |
| `bot_analytics.py` | אנליטיקס — משפך המרה, דוחות, שימור |
| `bot_referral.py` | מערכת הפניות — הבא חבר, קבל הנחה |
| `config.py` | קונפיגורציה מרכזית (קורא מ-.env) |
| `data_store.py` | שכבת נתונים בטוחה — נעילת קבצים, כתיבה אטומית, גיבויים |

### 📱 שיווק בפייסבוק
| קובץ | תפקיד |
|---|---|
| `fb_campaign_manager.py` | ניהול קמפיינים — יצירה, A/B, דוחות |
| `fb_auto_reporter.py` | דוחות אוטומטיים יומיים/שבועיים לטלגרם |
| `fb_content_calendar.py` | לוח תוכן — פוסטים אורגניים מתוזמנים |
| `facebook/client.py` | API client לפייסבוק |
| `facebook/pixel.py` | Facebook Conversions API (CAPI) |

### 🌐 דף נחיתה
| קובץ | תפקיד |
|---|---|
| `index.html` | דף נחיתה עם Pixel, SEO, social proof, exit popup |

### 📊 כלים
| קובץ | תפקיד |
|---|---|
| `dashboard.py` | דשבורד אדמין — כל המטריקות במקום אחד |
| `qa_full.py` | בדיקות QA לבוט |

---

## 🚀 התקנה מהירה

### שלב 1: הגדרות
```bash
cp .env.example .env
# ערוך את .env עם הטוקנים שלך
```

### שלב 2: התקנת חבילות
```bash
pip install -r requirements.txt
```

### שלב 3: הרצת הבוט
```bash
python bot_new.py
```

### שלב 4: שיווק בפייסבוק
```bash
# צור קמפיין מלא עם A/B testing
python fb_campaign_manager.py create-full --budget 50

# צפה בדוח ביצועים
python fb_campaign_manager.py report

# צור שבוע של פוסטים
python fb_content_calendar.py generate-week

# דשבורד מלא
python dashboard.py
```

---

## 📊 פקודות שימושיות

### Facebook Campaign Manager
```bash
python fb_campaign_manager.py create-full --budget 100 --targeting broad_men_30_55
python fb_campaign_manager.py report --period last_30d
python fb_campaign_manager.py list
python fb_campaign_manager.py create-audience --source bot_users
python fb_campaign_manager.py post --message "מבצע!" --link https://t.me/bot
```

### Content Calendar
```bash
python fb_content_calendar.py generate-week    # צור שבוע פוסטים
python fb_content_calendar.py list             # רשימת פוסטים
python fb_content_calendar.py post-next        # פרסם את הבא בתור
```

### Auto Reporter
```bash
python fb_auto_reporter.py --period daily      # דוח יומי
python fb_auto_reporter.py --period weekly     # דוח שבועי
python fb_auto_reporter.py --print-only        # הדפס בלי לשלוח
```

### Dashboard
```bash
python dashboard.py                            # דשבורד מלא
python dashboard.py --quick                    # סיכום קצר
```

---

## 🔧 מה צריך לעדכן ב-.env
- `BOT_TOKEN` — טוקן מ-@BotFather
- `SELLER_CHAT_ID` — ה-ID שלך בטלגרם
- `FB_PAGE_ACCESS_TOKEN` — טוקן עמוד פייסבוק
- `FB_AD_ACCOUNT_ID` — חשבון פרסום (act_XXX)
- `FB_PIXEL_ID` — מזהה פיקסל
- `YOUR_PIXEL_ID` ב-index.html — אותו פיקסל

---

## 🤖 פקודות בוט

### למשתמשים
| פקודה | תפקיד |
|---|---|
| `/start` | פתיחת התפריט הראשי |
| `/help` | עזרה |
| `/faq` | שאלות נפוצות |
| `/contact` | יצירת קשר עם נציג |
| `/myorders` | ההזמנות האחרונות שלי |
| `/referral` | קוד הפניה — חבר מביא חבר |

### לאדמין
| פקודה | תפקיד |
|---|---|
| `/orders` | צפייה בהזמנות אחרונות |
| `/stats` | סטטיסטיקות + אנליטיקס מורחב |
| `/broadcast` | שליחה לכל המשתמשים |
| `/statusupdate` | עדכון סטטוס הזמנה |

---

## 🔒 אבטחה
- כל הטוקנים נטענים מ-`.env` (לא בקוד!)
- ולידציה על כל שדה שהמשתמש מזין (שם, טלפון, עיר)
- כתיבה אטומית לקבצי JSON (מניעת השחתת נתונים)
- גיבויים אוטומטיים לפני כל שמירה (`data/backups/`)
- קודי הפניה עם `secrets.choice()` (קריפטוגרפי)
- Facebook Pixel CAPI עם הצפנת SHA-256 של PII

## Funnel
```
Facebook Ad → Landing Page → Telegram Bot → Cart → Order → Follow-up
     ↑                              ↓
  Retarget ← ── CAPI Events ← ── Pixel
```

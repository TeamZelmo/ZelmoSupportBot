# 🎧 Telegram Customer Support Bot

Customer bot पर message भेजता है → message partner group में पहुँचता है → 3 partners में से कोई **🎯 Take Chat** दबाकर chat ले लेता है → वही partner customer को reply करता है।

Stack: Python 3.11+, python-telegram-bot 22.5, SQLite, python-dotenv.

## ✨ Features

- Customer `/start` → welcome message, फिर कोई भी text message support team तक
- Partner group में **📩 NEW CUSTOMER MESSAGE** + 🎯 Take Chat button
- एक customer एक समय में सिर्फ एक partner को assigned (atomic DB check, race-safe)
- Partner `/panel` से 🟢 Available / 🟡 Busy / 🔴 Offline
- Partner private chat में 💬 Reply / ❌ Close Chat
- सारे customer और partner messages `data/bot.db` में save
- सब partners Offline / Busy होने पर customer को सही message
- Unauthorized users partner functions use नहीं कर सकते

## 📁 Structure

```
telegram_support_bot/
├── main.py              # entry point
├── config.py            # .env loading + validate_config()
├── database.py          # SQLite layer
├── keyboards.py         # inline keyboards
├── messages.py          # सारे user-facing texts
├── partner_manager.py   # partner auth / status logic
├── customer_manager.py  # customer / chat logic
├── handlers.py          # Telegram handlers
├── requirements.txt
├── .env.example
└── data/                # bot.db यहाँ बनेगा
```

## 🚀 Setup (Beginner friendly)

**Step 1 – Python install करें**
[python.org](https://www.python.org/downloads/) से Python 3.11 या नया version।

**Step 2 – Project folder खोलें**
```bash
cd telegram_support_bot
```

**Step 3 – Virtual environment**
```bash
python -m venv venv
```
Windows:
```bash
venv\Scripts\activate
```
Linux / Mac:
```bash
source venv/bin/activate
```

**Step 4 – Dependencies**
```bash
pip install -r requirements.txt
```

**Step 5 – `.env` बनाएँ**
`.env.example` को copy करके `.env` नाम दें।
```bash
cp .env.example .env        # Windows: copy .env.example .env
```

**Step 6 – BOT_TOKEN**
Telegram में [@BotFather](https://t.me/BotFather) → `/newbot` → token `.env` में `BOT_TOKEN=` के आगे डालें।

**Step 7 – तीनों Partner IDs**
हर partner [@userinfobot](https://t.me/userinfobot) को message करके अपना numeric ID ले, और `PARTNER1_ID`, `PARTNER2_ID`, `PARTNER3_ID` में डालें।

**Step 8 – Private support group**
1. Telegram में private group बनाएँ और तीनों partners + आपका bot add करें।
2. Group का Chat ID निकालें (जैसे `-1001234567890`), उदाहरण: group में [@RawDataBot](https://t.me/RawDataBot) add करके `chat.id` देखें, फिर उसे हटा दें।
3. `.env` में `PARTNER_GROUP_ID=` के आगे डालें।

**Step 9 – Bot चलाएँ**
```bash
python main.py
```

## ⚠️ ज़रूरी बातें

1. **हर partner को पहले bot को private में खोलकर `/start` भेजना होगा।** Telegram bot को तब तक private message नहीं भेजने देता। नहीं करेंगे तो Take Chat पर यही चेतावनी दिखेगी।
2. Partners का शुरुआती status **Offline** होता है। `/panel` से 🟢 Available करें, वरना customers को "team offline" दिखेगा।
3. **Busy** partner भी Take Chat कर सकता है; सिर्फ **Offline** नहीं कर सकता।
4. Bot को partner group में message भेजने और अपने messages edit करने की permission चाहिए।

## 🔄 Flow

1. Customer → `/start` → message भेजे।
2. कोई partner Available है → group में notification + 🎯 Take Chat; customer को "message पहुँच गया।"
3. सब Offline → "team offline"; Available नहीं पर Busy हैं → "सब busy"।
4. Partner Take Chat दबाए → chat उसे assign, group message "CHAT TAKEN" में बदले, customer को सूचना, partner को private में history + 💬 Reply / ❌ Close Chat।
5. 💬 Reply → partner अगला text लिखे → customer को `👨‍💼 Support Team:` के साथ जाए। `/cancel` से रद्द।
6. Customer का आगे का हर message उसी partner को जाता है।
7. ❌ Close Chat → assignment हटे, group message "CHAT CLOSED", customer को सूचना।

## 🧰 Commands

| Command | Kaun | Kaam |
|---|---|---|
| `/start` | सब | Customer: welcome. Partner: verify |
| `/panel` | Partner | Status बदलें |
| `/pending` | Partner | Waiting customers की list |
| `/cancel` | Partner | Reply mode रद्द करें |

## 🗄️ Database (`data/bot.db`)

`customers`, `partners`, `messages` और chat state के लिए `chats` table। Bot पहली बार चलने पर अपने आप बनाता है। यहाँ `customer_id` का मतलब customer का Telegram ID है।

## 🔒 Security

- Token और IDs सिर्फ `.env` में; `.env` `.gitignore` में है।
- हर partner action पर configured partner IDs से check होता है।
- Partner सिर्फ अपनी assigned chat को reply / close कर सकता है।
- Callback data regex और code, दोनों जगह validate होता है।

## 🛠️ Troubleshooting

- **Configuration error**: `.env` में सारी values असली भरें।
- **Take Chat पर "पहले /start भेजें"**: उस partner ने bot को private में start नहीं किया।
- **Group में notification नहीं आ रही**: Group ID सही है (supergroup में `-100...`) और bot group में है?

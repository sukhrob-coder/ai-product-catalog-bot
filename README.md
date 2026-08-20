# STAR_ELECT kanal boti

PostgreSQL katalogi bilan ishlaydigan Telegram do'kon, kanal boti va FastAPI backend.

Arxitektura tafsilotlari: `ARCHITECTURE.md`.

## Qanday ishlaydi

1. PostgreSQL `products` va `categories` jadvallarini saqlaydi.
2. Admin `/import` bilan EasyTrade Excel faylini DB'ga kiritadi yoki botga
   `.xlsx` fayl yuboradi.
3. Mijoz matn yoki rasm yuborsa, Gemini qidiruv mezonini ajratadi; bot mos
   mahsulotlarni, shu kategoriyadagi o'xshash mahsulotlarni va qoldiqni ko'rsatadi.

## 1-qadam: Botni Telegram'da yaratish

1. Telegram'da **@BotFather** ga yozing.
2. `/newbot` buyrug'ini yuboring, botga nom va username bering.
3. Sizga token beriladi (masalan `123456789:AAH...`) — uni saqlab qo'ying.

## 2-qadam: Botni kanalga admin qilib qo'shish

1. STAR_ELECT kanalingizga o'ting -> **Administratorlar** -> **Admin qo'shish**.
2. Yangi yaratgan botingizni toping va qo'shing.
3. Botga kamida **"Xabar yuborish"** (Post messages) huquqini bering.

## 3-qadam: Kompyuterda o'rnatish

```bash
# 1) Loyihani ochib, papkaga kiring
cd star_elect_bot

# 2) Virtual muhit yaratish (tavsiya etiladi)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3) Kutubxonalarni o'rnatish
pip install -r requirements.txt

# 4) .env faylini sozlash
cp .env.example .env
# .env faylini oching va BOT_TOKEN, CHANNEL_ID, ADMIN_CHAT_IDS qiymatlarini kiriting

# PostgreSQL va botni ishga tushirish
docker compose up -d --build

# API: http://localhost:8000/docs
```

## 4-qadam: Mahsulotlar faylini tayyorlash

1. EasyTrade dasturida: **Hisobotlar -> Tovarlar qoldig'i** (yoki shunga
   o'xshash) bo'limiga kiring.
2. **Excel'ga eksport** qiling.
3. Faylni loyihadagi `data/mahsulotlar.xlsx` manziliga saqlang
   (yoki `.env` dagi `EXCEL_PATH` ni o'zingiz xohlagan joyga ko'rsating).
4. Excel'dagi ustun nomlari `config.py` dagi `COLUMN_NAME`, `COLUMN_PRICE`
   va h.k. bilan mos kelishi kerak. Agar EasyTrade'dagi ustun nomlari
   boshqacha bo'lsa (masalan "Наименование" bo'lsa), `config.py` dagi
   yoki `.env` dagi mos qiymatni o'zgartiring.

**Rasm qo'shmoqchi bo'lsangiz:** `data/images/` papkasiga mahsulot
rasmlarini joylang, Excel'da esa shu fayl nomini ko'rsatadigan ustun
qo'shing (masalan "Rasm" ustuniga `stabilizator1.jpg` deb yozing).

## 5-qadam: Botni ishga tushirish

```bash
python main.py
```

Bot doimiy ishlab turishi kerak bo'lsa (server yoki kompyuter doim yoniq
bo'lishi kerak), quyidagilardan birini ishlating:

- **Linux server**: `systemd` service yoki `screen`/`tmux` orqali orqa fonda
  ishga tushirish, yoki `pm2` / `supervisor`.
- **Windows**: Task Scheduler orqali kompyuter yonganda avtomatik ishga
  tushirish, yoki botni doim ochiq turadigan oyna sifatida qoldirish.

Eng ishonchli yo'l — arzon VPS (masalan Ubuntu server)da doim ishlab
turishi. Sizda Linux/Ubuntu server tajribangiz bor ekan, shu yerda
`systemd` orqali servis qilib qo'yish eng qulay variant:

```ini
# /etc/systemd/system/star-elect-bot.service
[Unit]
Description=STAR_ELECT Telegram bot
After=network.target

[Service]
WorkingDirectory=/home/USER/star_elect_bot
ExecStart=/home/USER/star_elect_bot/venv/bin/python main.py
Restart=always
User=USER

[Install]
WantedBy=multi-user.target
```

So'ng:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now star-elect-bot
sudo systemctl status star-elect-bot
```

## Buyruqlar

- `/start` — admin yoki mijoz rejimi
- `/post` — kanalga bitta mahsulot postlash (faqat admin chatlar)
- `/holat` — katalog holati (faqat admin chatlar)
- `/import` — Excel'dan PostgreSQL'ga import

`.env` dagi `ADMIN_CHAT_IDS` ga admin bilan yozishiladigan Telegram chat ID'sini
kiriting. Bo'sh bo'lsa bot xavfsizlik sabab ishga tushmaydi.

## Sozlamalarni o'zgartirish

Barcha asosiy sozlamalar `config.py` faylida:

| Sozlama | Vazifasi |
|---|---|
| `POST_TIMES` | Kuniga qaysi vaqtlarda post chiqarilishi |
| `POSTS_PER_RUN` | Bir safarda nechta mahsulot joylanishi |
| `ONLY_IN_STOCK` | Faqat omborda bor mahsulotlarni joylash |
| `COLUMN_*` | Excel ustun nomlari |

## Gemini AI orqali Post Yaratish (Rasm yuborish)

1. `.env` fayliga `GEMINI_API_KEY` ni kiriting (API kalitni [Google AI Studio](https://aistudio.google.com/) orqali olasiz).
2. Botga (shaxsiy chatda) mahsulot rasmini yuboring (rasm ostiga narxi yoki izohini ham yozishingiz mumkin).
3. **Gemini AI** rasmni tahlil qilib, Telegram kanali uchun jozibali, professional reklama matnini yaratadi.
4. Bot sizga postni ko'rsatadi:
   - 🚀 **Kanalga joylash** — bitta bosishda kanalga chiqaradi.
   - 🔄 **Qayta yozish** — matn yoqmasa, Gemini boshqa variant taklif qiladi.
   - ❌ **Bekor qilish** — postni bekor qiladi.

## Fayl tuzilishi

```
star_elect_bot/
├── main.py           # ishga tushirish, rasm qabul qilish va callbacklar
├── ai_helper.py      # Gemini AI integratsiyasi va promptlar
├── config.py         # barcha sozlamalar
├── database.py       # PostgreSQL model va qidiruv
├── catalog.py        # Excel import
├── data_source.py     # Excel'dan mahsulot o'qish
├── poster.py          # DB mahsulotlarini kanalga yuborish
├── state.py            # joylangan mahsulotlarni eslab qolish
├── requirements.txt
├── .env.example
└── data/
    ├── mahsulotlar.xlsx   # (siz qo'yasiz)
    ├── images/            # (ixtiyoriy, rasm fayllar)
    └── posted_state.json  # (avtomatik yaratiladi)
```

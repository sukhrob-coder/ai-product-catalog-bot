# Telegram Shop Manager

Bu dastur Telegram orqali mahsulotlarni izlash va boshqarish uchun yaratilgan. Mijoz mahsulot nomi yoki rasmini yuboradi, bot bazadan mos ma’lumotni topib beradi. Admin yangi mahsulot qo‘shadi, Excel fayl yuklaydi va kerak bo‘lsa mahsulot postini kanalga chiqaradi. Barcha mahsulotlar PostgreSQL’da saqlanadi.

## Asosiy imkoniyatlar

- Mahsulot nomi bo‘yicha PostgreSQL’dan qidirish.
- `rezitka`, `naushnik`, `zaryadka` kabi yozilish variantlarini tushunish.
- Mahsulot rasmini Gemini AI orqali tahlil qilish.
- Gemini ishlamasa ham nom bo‘yicha lokal katalog qidiruvi davom etishi.
- Katalogdagi bir xil yoki o‘xshash rasmni AI’siz image-hash orqali topish.
- Mijozga mahsulot nomi, kategoriya va mavjud sonini ko‘rsatish.
- Faqat topilgan mahsulotga o‘xshash mahsulotlarni chiqarish.
- Admin uchun mahsulotni rasm + nom bilan qo‘shish.
- Mahsulot bazada bo‘lsa, sonini oshirishdan oldin tasdiq tugmasini chiqarish.
- Excel fayl orqali mahsulotlarni import qilish yoki yangilash.
- Alohida `/post` rejimida rasmni kanalga joylash uchun preview tayyorlash (ixtiyoriy).
- FastAPI orqali katalog va health-check API.

## Ishlash tartibi

Mijoz `/start` bosadi va mahsulot nomini yozadi yoki rasm yuboradi. Bot avval katalogdan qidiradi. Rasm bo‘yicha aniq aniqlash kerak bo‘lsa Gemini ishlaydi. Natijada mahsulot nomi, kategoriya va mavjud soni ko‘rsatiladi. Narx mijoz javoblarida ko‘rsatilmaydi.

Adminning rasm yuborishi o‘z-o‘zidan bazaga mahsulot qo‘shmaydi. Avval `/add`, `/post` yoki `/import` buyrug‘i tanlanadi.

## O‘rnatish va ishga tushirish

### 1. `.env` yaratish

```bash
cp .env.example .env
```

`.env` ichida kamida quyidagilarni to‘ldiring:

```env
BOT_TOKEN=Telegram_BotFather_token
ADMIN_CHAT_IDS=Telegram_admin_chat_id
GEMINI_API_KEY=Google_AI_Studio_key
CHANNEL_ID=@kanal_username
```

`GEMINI_API_KEY` rasm tahlili va AI post yaratish uchun kerak. Nom bo‘yicha PostgreSQL qidiruvi Gemini’siz ham ishlaydi.

### 2. Docker bilan ishga tushirish

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f bot
```

Servislar:

- PostgreSQL — mahsulotlar bazasi.
- Bot — Telegram polling va admin/mijoz oqimlari.
- API — `http://localhost:8000`.
- Swagger — `http://localhost:8000/docs`.

To‘xtatish:

```bash
docker compose down
```

### 3. Docker’siz lokal ishga tushirish

PostgreSQL ishlayotgan bo‘lishi va `DATABASE_URL` localhost bazasiga ko‘rsatilishi kerak.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

FastAPI’ni alohida ishga tushirish:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

## Telegram buyruqlari

### Mijoz

- `/start` — do‘kon bilan tanishish.
- Oddiy matn — mahsulot nomi bo‘yicha qidirish.
- Rasm — mahsulotni rasm orqali qidirish.

### Admin

- `/start` — admin menyusi.
- `/add` — rasm yuborish va caption’da mahsulot nomini ko‘rsatib bazaga qo‘shish.
- `/import` — Excel faylni PostgreSQL’ga import qilish.
- `/post` — rasm yuborib kanal posti preview’ini olish. Caption ixtiyoriy: bo‘sh bo‘lsa Gemini matn yaratadi, caption bo‘lsa Gemini chaqirilmaydi.
- `/avtopost` — PostgreSQL’dan navbatdagi mahsulotni kanalga chiqarish.

`ADMIN_CHAT_IDS` ichiga adminning Telegram chat ID’sini yozing. Admin rejimidan tashqarida yuborilgan rasm bazaga qo‘shilmaydi.

## Excel import

Excel faylni yuborishdan oldin `/import` buyrug‘ini bosing. Standart ustunlar:

- `Nomi`
- `Narxi`
- `Qoldiq`
- `Guruh`
- `Rasm`
- `Shtrix-kod`

Ustun nomlari boshqacha bo‘lsa `.env` ichidagi `COLUMN_NAME`, `COLUMN_QTY`, `COLUMN_CATEGORY` va boshqa `COLUMN_*` sozlamalarini o‘zgartiring.

## API

- `GET /health` — servis va baza holati.
- `GET /api/v1/products` — mahsulotlar ro‘yxati.
- `GET /api/v1/products/search?q=rezitka` — katalog qidiruvi.
- `POST /api/v1/admin/import` — API kalit bilan Excel import.

## Loyiha tuzilishi

```text
telegram_shop_bot/
├── main.py             # Telegram bot, mijoz va admin oqimlari
├── ai_helper.py        # Gemini rasm tahlili va post generatori
├── retrieval.py        # lokal fuzzy/RAG qidiruv va image-hash
├── database.py         # PostgreSQL modellar va CRUD
├── catalog.py          # Excel import
├── poster.py           # kanalga avtomatik postlash
├── api.py              # FastAPI endpointlar
├── config.py           # .env sozlamalari
├── docker-compose.yml  # PostgreSQL, bot va API
└── requirements.txt
```

## Tekshirish

```bash
python3 -m py_compile main.py ai_helper.py database.py retrieval.py api.py
docker compose ps
docker compose logs --tail=50 bot
```

Bot tokeni, Gemini kaliti va PostgreSQL parolini git’ga qo‘shmang. `.env` fayli `.gitignore` orqali chiqarib tashlangan.

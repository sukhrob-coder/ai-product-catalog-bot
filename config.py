"""
STAR_ELECT kanal boti — sozlamalar

Bu yerdagi qiymatlarni .env faylida yoki muhit o'zgaruvchilarida
ko'rsatish tavsiya etiladi (parol/token kabi maxfiy narsalarni
to'g'ridan-to'g'ri kodga yozmang!).
"""
import os
from dotenv import load_dotenv

load_dotenv()  # .env faylini o'qiydi (agar mavjud bo'lsa)

# --- Telegram sozlamalari ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
# Kanal username (masalan "@star_elect_shop") yoki kanal ID (masalan -1001234567890)
CHANNEL_ID = os.getenv("CHANNEL_ID", "")

# --- Gemini AI sozlamalari ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "60"))

# --- PostgreSQL ---
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://star_elect:star_elect@postgres:5432/star_elect",
)

# Kanal posting huquqiga ega adminlarning Telegram chat ID'lari.
ADMIN_CHAT_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_CHAT_IDS", os.getenv("ADMIN_IDS", "")).split(",")
    if value.strip().lstrip("-").isdigit()
}

# --- Do'kon ma'lumotlari (postlar tagida chiqishi uchun) ---
SHOP_NAME = os.getenv("SHOP_NAME", "STAR_ELECT")
SHOP_PHONE = os.getenv("SHOP_PHONE", "")
SHOP_LOCATION = os.getenv("SHOP_LOCATION", "")
SHOP_ADMIN_USERNAME = os.getenv("SHOP_ADMIN_USERNAME", "")

# --- EasyTrade eksport fayli ---
# EasyTrade dasturida: Hisobotlar -> Tovarlar ro'yxati -> Excel formatida yuklab olish
# Faylni shu yo'lga saqlab turing (masalan: doim ustidan yozilib turadigan joy)
EXCEL_PATH = os.getenv("EXCEL_PATH", "data/mahsulotlar.xlsx")

# Excel fayldagi ustun nomlari (o'z faylingizga qarab moslashtiring)
COLUMN_NAME = os.getenv("COLUMN_NAME", "Nomi")
COLUMN_PRICE = os.getenv("COLUMN_PRICE", "Narxi")
COLUMN_QTY = os.getenv("COLUMN_QTY", "Qoldiq")
COLUMN_CATEGORY = os.getenv("COLUMN_CATEGORY", "Guruh")
COLUMN_IMAGE = os.getenv("COLUMN_IMAGE", "Rasm")  # rasm fayl yo'li (ixtiyoriy, ustun bo'lmasa "" qoldiring)
COLUMN_BARCODE = os.getenv("COLUMN_BARCODE", "Shtrix-kod")

# Rasm fayllari saqlanadigan papka (agar Excel'da faqat fayl nomi bo'lsa)
IMAGES_DIR = os.getenv("IMAGES_DIR", "data/images")

# --- Joylash jadvali (kuniga necha marta va qaysi vaqtlarda) ---
# 24 soatlik format, Tashkent vaqti bo'yicha
POST_TIMES = ["10:00", "14:00", "18:00"]

# Bir joylashda nechta mahsulot posti chiqarilsin
POSTS_PER_RUN = 1

# Faqat qoldig'i > 0 bo'lgan mahsulotlarni joylash
ONLY_IN_STOCK = True

# Vaqt zonasi
TIMEZONE = "Asia/Tashkent"

# Eski state.py bilan orqaga moslik; posting holati endi DB'da saqlanadi.
STATE_FILE = os.getenv("STATE_FILE", "data/posted_state.json")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

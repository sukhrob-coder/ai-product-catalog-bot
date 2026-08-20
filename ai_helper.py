"""
Gemini AI yordamida mahsulot rasmi va ma'lumotlaridan Telegram posti yaratish.
"""
import io
import asyncio
import json
import logging
from typing import Optional

from google import genai
from google.genai import types

import config

logger = logging.getLogger(__name__)


def _get_client() -> Optional[genai.Client]:
    if not config.GEMINI_API_KEY:
        return None
    return genai.Client(api_key=config.GEMINI_API_KEY)


def get_footer_text() -> str:
    """Post oxiridagi kontakt va do'kon ma'lumotlari."""
    lines = ["", f"📍 <b>{config.SHOP_NAME}</b> — elektronika va elektr jihozlari do'koni"]
    if config.SHOP_PHONE:
        lines.append(f"📞 Aloqa: <b>{config.SHOP_PHONE}</b>")
    if config.SHOP_ADMIN_USERNAME:
        lines.append(f"👨‍💻 Buyurtma: {config.SHOP_ADMIN_USERNAME}")
    if config.SHOP_LOCATION:
        lines.append(f"🏢 Manzil: {config.SHOP_LOCATION}")
    lines.append("🚚 O'zbekiston bo'ylab yetkazib berish mavjud!")
    return "\n".join(lines)


async def generate_post_from_image(image_bytes: bytes | list[bytes], mime_type: str = "image/jpeg", user_note: str = "") -> str:
    """
    Mahsulot rasmini Gemini AI ga yuborib, Telegram kanal uchun chiroyli post yaratadi.
    user_note: Foydalanuvchi rasm bilan birga yuborgan qo'shimcha ma'lumot.
    """
    client = _get_client()
    if not client:
        caption = "⚡️ <b>Yangi mahsulot!</b>\n\n"
        if user_note:
            caption += f"📝 {user_note}\n\n"
        caption += get_footer_text()
        return caption

    prompt = f"""
Siz "{config.SHOP_NAME}" elektronika va elektr jihozlari do'koni uchun tajribali SMM/Kopiraytersiz.
Ushbu mahsulot rasmini tahlil qilib, Telegram kanali uchun jozibali, professional va xaridorgir reklama posti matnini o'zbek tilida yozing.

Foydalanuvchi kiritgan qo'shimcha ma'lumot: "{user_note}"

Qoidalar:
1. Telegram HTML formatidan foydalaning (faqat <b>, <i>, <code> teglari). Hech qanday Markdown (**, ##, *) ishlatmang!
2. Tuzilishi:
   - ⚡️ Boshida mahsulot nomi (<b>nomi</b>)
   - 💡 2-4 ta asosiy afzalligi / xususiyati (punktlar bilan, mos emojilar bilan)
   - Narx, valyuta yoki chegirma haqida hech narsa yozmang — rasmda ko'rinsa ham e'tiborsiz qoldiring.
3. Oxiriga do'kon ma'lumotlarini qo'shmang (biz uni avtomatik qo'shamiz).
4. Matn qisqa, aniq, o'qilishi oson va qiziqtiruvchi bo'lsin.
5. Faqat tayyor post matnini qaytaring, ortiqcha salom-alik yoki izoh yozmang.
"""

    try:
        images = image_bytes if isinstance(image_bytes, list) else [image_bytes]
        image_parts = [types.Part.from_bytes(data=image, mime_type=mime_type) for image in images]
        response = await asyncio.wait_for(
            asyncio.to_thread(client.models.generate_content, model=config.GEMINI_MODEL, contents=image_parts + [prompt]),
            timeout=config.GEMINI_TIMEOUT_SECONDS,
        )
        post_text = (response.text or "").strip()
        # HTML teglarni tozalash / tartibga solish
        if post_text.startswith("```html"):
            post_text = post_text.removeprefix("```html").removesuffix("```").strip()
        elif post_text.startswith("```"):
            post_text = post_text.removeprefix("```").removesuffix("```").strip()

        return f"{post_text}\n{get_footer_text()}"
    except Exception as e:
        logger.exception("Gemini orqali rasm tahlil qilishda xatolik: %s", e)
        # Gemini ishlamasa ham bot ishlashda davom etadi.
        caption = "⚡️ <b>Yangi mahsulot!</b>\n\n"
        if user_note:
            caption += f"📝 {user_note}\n\n"
        caption += get_footer_text()
        return caption


async def generate_caption_for_product(name: str, price: float, category: str = "", qty: float = 0) -> str:
    """
    Excel'dagi mahsulot uchun Gemini orqali qisqa tavsif yaratish.
    """
    client = _get_client()
    if not client:
        return ""

    prompt = f"""
"{config.SHOP_NAME}" do'koni uchun Telegram post matni yozing:
Mahsulot: {name}
Kategoriya: {category}
Narxni ishlatmang: bu kanal postida narx ko'rsatilmaydi.

Qoidalar:
- 1-2 jumladan iborat qisqa, jozibali tavsif bo'lsin.
- Telegram HTML (<b>, <i>) teglari bilan. Markdown (**) ishlatmang.
- Narx, valyuta va chegirma yozmang.
- Faqat tavsif matnini qaytaring.
"""
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(client.models.generate_content, model=config.GEMINI_MODEL, contents=prompt),
            timeout=config.GEMINI_TIMEOUT_SECONDS,
        )
        text = (response.text or "").strip()
        if text.startswith("```"):
            text = text.replace("```html", "").replace("```", "").strip()
        return text
    except Exception:
        logger.exception("Gemini caption yaratishda xatolik: %s", name)
        return ""


async def analyze_product_query(image_bytes: bytes | None = None, mime_type: str = "image/jpeg", user_text: str = "", catalog_names: list[str] | None = None) -> dict:
    """Rasm yoki matndan katalog qidiruvi uchun nom, kategoriya va kalit so'zlarni ajratadi."""
    client = _get_client()
    fallback = {"name": user_text, "category": "", "keywords": user_text}
    if not client:
        return fallback
    catalog_text = "\n".join(f"- {name}" for name in (catalog_names or []))
    prompt = f"""
Siz STAR_ELECTRONICS katalogi uchun juda qat'iy mahsulot identifikatorisiz.
Rasmda nima borligini avval aniqlang. Pultni lampa, kabelni adapter yoki boshqa
mahsulot deb taxmin qilmang. Faqat quyidagi katalogda aynan ko'rinib turgan
mahsulot bo'lsa matched_name ga yozing; aks holda matched_name bo'sh bo'lsin.
Katalogda yo'q mahsulot uchun mos nom o'ylab topmang. Kategoriya faqat aniq
identifikatsiya qilinganda yozilsin. Faqat JSON qaytaring:
{{"matched_name":"", "name":"", "category":"", "keywords":"", "confidence":0}}

KATALOG:
{catalog_text}
Foydalanuvchi matni: {user_text}
"""
    try:
        parts = []
        if image_bytes:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
        parts.append(prompt)
        response = await asyncio.wait_for(
            asyncio.to_thread(client.models.generate_content, model=config.GEMINI_MODEL, contents=parts),
            timeout=config.GEMINI_TIMEOUT_SECONDS,
        )
        raw = (response.text or "").strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        return {
            "matched_name": str(result.get("matched_name", "")),
            "name": str(result.get("name", "")),
            "category": str(result.get("category", "")),
            "keywords": str(result.get("keywords", "")),
            "confidence": float(result.get("confidence", 0) or 0),
        }
    except Exception:
        logger.exception("Gemini katalog qidiruvini tahlil qila olmadi")
        return fallback


async def analyze_catalog_product(image_bytes: bytes, mime_type: str = "image/jpeg", user_text: str = "") -> dict:
    """Admin yuborgan mahsulot rasmini yangi katalog yozuviga aylantiradi."""
    client = _get_client()
    fallback = {"name": user_text or "Yangi mahsulot", "category": "Elektronika", "price": 0, "quantity": 1}
    if not client:
        return fallback
    prompt = f"""
Siz STAR_ELECTRONICS do'konining katalog operatorisiz. Rasmni tahlil qilib,
mahsulot nomi va eng mos kategoriyani aniqlang. Pultni lampa deb yozmang,
rasmda ko'rinmagan xususiyatni o'ylab topmang. Narx yoki son rasmda/captionda
aniq ko'rinsa oling, aks holda price=0 va quantity=1 qaytaring.
Faqat JSON qaytaring:
{{"name":"", "category":"", "price":0, "quantity":1}}
Caption: {user_text}
"""
    try:
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        response = await asyncio.wait_for(
            asyncio.to_thread(client.models.generate_content, model=config.GEMINI_MODEL, contents=[image_part, prompt]),
            timeout=config.GEMINI_TIMEOUT_SECONDS,
        )
        raw = (response.text or "").strip().replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        return {
            "name": str(result.get("name") or fallback["name"]).strip(),
            "category": str(result.get("category") or fallback["category"]).strip(),
            "price": float(result.get("price") or 0),
            "quantity": float(result.get("quantity") or 1),
        }
    except Exception:
        logger.exception("Katalog mahsulotini Gemini bilan tahlil qilib bo'lmadi")
        return fallback

"""
Mahsulot postini formatlab, Telegram kanaliga yuborish.
"""
import logging
import random
from typing import List

from telegram import Bot
from telegram.constants import ParseMode

import config
import state
from database import CatalogProduct, list_products

logger = logging.getLogger(__name__)


from ai_helper import get_footer_text


def format_caption(p: CatalogProduct) -> str:
    lines = [f"🔌 <b>{p.name}</b>"]
    if p.category:
        lines.append(f"📂 Kategoriya: {p.category}")
    if p.qty > 0:
        lines.append(f"✅ Mavjud: {int(p.qty)} dona")
    lines.append(get_footer_text())
    return "\n".join(lines)


def pick_products_to_post(all_products: List[CatalogProduct], count: int) -> List[CatalogProduct]:
    """Hali joylanmagan mahsulotlardan tasodifiy tanlaydi.
    Agar hammasi joylangan bo'lsa, holatni tozalab, qaytadan boshlaydi."""
    posted_ids = state.load_posted_ids()
    remaining = [p for p in all_products if p.id not in posted_ids]

    if not remaining:
        logger.info("Barcha mahsulotlar bir marta joylandi — holat tozalanmoqda, tsikl qaytadan boshlanadi.")
        state.reset_state()
        remaining = all_products

    random.shuffle(remaining)
    return remaining[:count]


async def post_products(bot: Bot, products: List[CatalogProduct]) -> None:
    for p in products:
        caption = format_caption(p)
        try:
            if p.image_path:
                with open(p.image_path, "rb") as photo:
                    await bot.send_photo(
                        chat_id=config.CHANNEL_ID,
                        photo=photo,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                    )
            else:
                await bot.send_message(
                    chat_id=config.CHANNEL_ID,
                    text=caption,
                    parse_mode=ParseMode.HTML,
                )
            state.mark_posted(p.id)
            logger.info("Joylandi: %s", p.name)
        except Exception:
            logger.exception("Post yuborishda xatolik: %s", p.name)


async def run_posting_job(bot: Bot) -> None:
    """Bitta joylash sikli: Excel'ni o'qib, tanlab, kanalga yuboradi."""
    try:
        products = list_products(only_in_stock=config.ONLY_IN_STOCK)
    except Exception:
        logger.exception("Mahsulotlarni o'qib bo'lmadi.")
        return

    if not products:
        logger.warning("Joylash uchun mahsulot topilmadi (ombor bo'sh yoki filtr juda qattiq).")
        return

    chosen = pick_products_to_post(products, config.POSTS_PER_RUN)
    await post_products(bot, chosen)

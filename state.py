"""
Qaysi mahsulotlar allaqachon kanalga joylanganini eslab qolish.

Bu bo'lmasa, bot har safar bitta mahsulotni qayta-qayta post qilib
yuborishi mumkin. Barcha mahsulotlar bir marta joylangandan keyin,
tsikl boshidan qaytadan boshlanadi (yangi partiya kelganda ham shu
tarzda ishlayveradi).
"""
import json
import os
from typing import List, Set

import config


def load_posted_ids() -> Set[str]:
    if not os.path.exists(config.STATE_FILE):
        return set()
    try:
        with open(config.STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("posted_ids", []))
    except (json.JSONDecodeError, OSError):
        return set()


def save_posted_ids(posted_ids: Set[str]) -> None:
    os.makedirs(os.path.dirname(config.STATE_FILE) or ".", exist_ok=True)
    with open(config.STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"posted_ids": sorted(posted_ids)}, f, ensure_ascii=False, indent=2)


def mark_posted(product_id: str) -> None:
    posted = load_posted_ids()
    posted.add(product_id)
    save_posted_ids(posted)


def reset_state() -> None:
    """Barcha mahsulotlar tugaganda tsiklni boshidan boshlash uchun."""
    save_posted_ids(set())

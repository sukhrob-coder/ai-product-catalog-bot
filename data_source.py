"""
EasyTrade dan eksport qilingan Excel fayldan mahsulotlar ro'yxatini o'qish.

EasyTrade'da: Hisobotlar -> Tovarlar qoldig'i / Tovarlar ro'yxati ->
"Excel'ga yuklash" tugmasi orqali .xlsx fayl olinadi.
"""
import os
import logging
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

import config

logger = logging.getLogger(__name__)


@dataclass
class Product:
    id: str            # noyob identifikator (shtrix-kod yoki nom+narx asosida)
    name: str
    price: float
    qty: float
    category: str
    image_path: Optional[str]


def _make_id(barcode: str, name: str, price: float) -> str:
    """Har bir mahsulot uchun barqaror (doim bir xil) ID hosil qiladi."""
    if barcode and str(barcode).strip() and str(barcode).lower() != "nan":
        return f"bc:{str(barcode).strip()}"
    return f"np:{name.strip().lower()}:{price}"


def load_products(only_in_stock: bool | None = None) -> List[Product]:
    """Excel faylni o'qib, Product obyektlari ro'yxatini qaytaradi."""
    if not os.path.exists(config.EXCEL_PATH):
        raise FileNotFoundError(
            f"Excel fayl topilmadi: {config.EXCEL_PATH}\n"
            f"EasyTrade'dan mahsulotlar ro'yxatini shu manzilga eksport qiling."
        )

    df = pd.read_excel(config.EXCEL_PATH)
    df.columns = [str(c).strip() for c in df.columns]

    required = [config.COLUMN_NAME, config.COLUMN_PRICE]
    for col in required:
        if col not in df.columns:
            raise ValueError(
                f"Excel faylda '{col}' ustuni topilmadi. "
                f"Mavjud ustunlar: {list(df.columns)}\n"
                f"config.py dagi COLUMN_* qiymatlarini to'g'rilang."
            )

    products = []
    for _, row in df.iterrows():
        name = str(row.get(config.COLUMN_NAME, "")).strip()
        if not name or name.lower() == "nan":
            continue

        try:
            price = float(row.get(config.COLUMN_PRICE, 0) or 0)
        except (ValueError, TypeError):
            price = 0.0

        try:
            qty = float(row.get(config.COLUMN_QTY, 0) or 0)
        except (ValueError, TypeError):
            qty = 0.0

        if (config.ONLY_IN_STOCK if only_in_stock is None else only_in_stock) and qty <= 0:
            continue

        category = str(row.get(config.COLUMN_CATEGORY, "")).strip()
        if category.lower() == "nan":
            category = ""

        barcode = str(row.get(config.COLUMN_BARCODE, "")).strip()

        image_val = None
        if config.COLUMN_IMAGE and config.COLUMN_IMAGE in df.columns:
            raw_img = str(row.get(config.COLUMN_IMAGE, "")).strip()
            if raw_img and raw_img.lower() != "nan":
                candidate = raw_img
                if not os.path.isabs(candidate):
                    candidate = os.path.join(config.IMAGES_DIR, raw_img)
                if os.path.exists(candidate):
                    image_val = candidate
                else:
                    logger.warning("Rasm topilmadi: %s (mahsulot: %s)", candidate, name)

        pid = _make_id(barcode, name, price)
        products.append(
            Product(id=pid, name=name, price=price, qty=qty, category=category, image_path=image_val)
        )

    logger.info("Excel'dan %d ta mahsulot o'qildi (ombordagilar).", len(products))
    return products

"""Collapse repeated category-level demo photos to one file per category."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import select

import config
from database import Product, session_scope

KEEP_NAMES = {
    "Kabellar": "USB Type-C kabel STAR 02",
    "Adapterlar": "USB adapter STAR 01",
    "Yoritish": "LED lampa STAR 01",
    "Elektr jihozlari": "Rozetka STAR 01",
    "Aksessuarlar": "Quloqchin STAR 04",
}


def main() -> None:
    image_dir = Path(config.IMAGES_DIR)
    keep_paths: set[str] = set()
    with session_scope() as session:
        products = session.scalars(select(Product).where(Product.image_path.is_not(None))).all()
        by_category = {}
        for product in products:
            by_category.setdefault(product.category.name if product.category else "", []).append(product)
        for category, rows in by_category.items():
            preferred = next((row for row in rows if row.name == KEEP_NAMES.get(category)), rows[0])
            keeper = preferred.image_path
            keep_paths.add(keeper)
            for row in rows:
                row.image_path = keeper

    removed = 0
    for path in image_dir.glob("web_*.jpg"):
        if str(path) not in keep_paths:
            path.unlink()
            removed += 1
    print(f"{len(keep_paths)} ta representative rasm qoldi, {removed} ta duplicate rasm o'chirildi")


if __name__ == "__main__":
    main()

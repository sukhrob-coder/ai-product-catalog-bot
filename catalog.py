"""EasyTrade Excel import."""
from __future__ import annotations

import os
from pathlib import Path

import config
from database import init_db, upsert_products


def import_excel(excel_path: str | None = None) -> int:
    from data_source import load_products

    rows = []
    if excel_path:
        old_path = config.EXCEL_PATH
        config.EXCEL_PATH = excel_path
    else:
        old_path = None
    try:
        source = load_products(only_in_stock=False)
    finally:
        if old_path is not None:
            config.EXCEL_PATH = old_path
    for item in source:
        rows.append({"name": item.name, "price": item.price, "quantity": item.qty,
                     "category": item.category, "image_path": item.image_path})
    return upsert_products(rows)


if __name__ == "__main__":
    init_db()

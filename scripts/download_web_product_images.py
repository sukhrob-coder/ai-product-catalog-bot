"""Download category-appropriate Unsplash photos and attach variants to catalog rows."""
from __future__ import annotations

import io
import os
import urllib.request
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

import config
from database import list_products, upsert_products

SOURCES = {
    "Kabellar": "https://images.unsplash.com/photo-1492107376256-4026437926cd?auto=format&fit=crop&w=1400&q=85",
    "Adapterlar": "https://images.unsplash.com/photo-1586254116951-5263e2cdb44c?auto=format&fit=crop&w=1400&q=85",
    "Yoritish": "https://images.unsplash.com/photo-1532007271951-c487760934ae?auto=format&fit=crop&w=1400&q=85",
    "Elektr jihozlari": "https://images.unsplash.com/photo-1529111316-da2e2a1e625d?auto=format&fit=crop&w=1400&q=85",
    "Aksessuarlar": "https://images.unsplash.com/photo-1693895592595-9171d91a0f22?auto=format&fit=crop&w=1400&q=85",
}


def main() -> None:
    output_dir = Path(config.IMAGES_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_cache: dict[str, Image.Image] = {}
    products = list_products(only_in_stock=False)
    rows = []
    for index, product in enumerate(products, 1):
        url = SOURCES.get(product.category)
        if not url:
            continue
        if url not in source_cache:
            with urllib.request.urlopen(url, timeout=30) as response:
                source_cache[url] = Image.open(io.BytesIO(response.read())).convert("RGB")
        source = source_cache[url]
        # Har bir mahsulotda alohida fayl va biroz boshqa crop/yorqinlik bo'ladi.
        width, height = source.size
        crop_width = int(width * (0.82 + (index % 5) * 0.03))
        crop_height = int(height * (0.82 + (index % 4) * 0.03))
        left = max(0, (width - crop_width) * ((index * 17) % 100) // 100)
        top = max(0, (height - crop_height) * ((index * 23) % 100) // 100)
        image = source.crop((left, top, left + crop_width, top + crop_height))
        image = ImageOps.fit(image, (1000, 700), method=Image.Resampling.LANCZOS)
        image = ImageEnhance.Brightness(image).enhance(0.94 + (index % 4) * 0.04)
        path = output_dir / f"web_{index:02d}.jpg"
        image.save(path, quality=90, optimize=True)
        rows.append({"name": product.name, "category": product.category, "price": product.price,
                     "quantity": product.qty, "image_path": str(path)})
    upsert_products(rows)
    print(f"{len(rows)} ta mahsulot rasmi Unsplash manbalaridan yangilandi")


if __name__ == "__main__":
    main()

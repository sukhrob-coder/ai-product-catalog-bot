"""Catalog RAG retrieval: typo/synonym tolerant candidate selection."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from io import BytesIO

from PIL import Image

from database import CatalogProduct, list_products

ALIASES = {
    "rezitka": "rozetka", "rozetka": "rozetka", "vilka": "vilka",
    "naushnik": "quloqchin", "quloqchin": "quloqchin", "quloqchinlar": "quloqchin",
    "sim": "kabel", "shnur": "kabel", "zaryadka": "zaryadlovchi",
    "adaptercha": "adapter", "fonar": "fonari",
}


def _tokens(value: str) -> set[str]:
    words = {word for word in re.findall(r"[\w-]+", value.lower()) if len(word) > 2 and word != "star" and not word.isdigit()}
    return {ALIASES.get(word, word) for word in words}


def _score(query_words: set[str], product: CatalogProduct) -> float:
    name_words = _tokens(product.name)
    if not query_words or not name_words:
        return 0
    exact = len(query_words & name_words)
    fuzzy = sum(max(SequenceMatcher(None, q, n).ratio() for n in name_words) >= 0.72 for q in query_words)
    return (exact * 2 + fuzzy) / (len(query_words) * 3)


def retrieve(query: str, category: str = "", limit: int = 5) -> tuple[list[CatalogProduct], list[CatalogProduct]]:
    query_words = _tokens(query)
    candidates = list_products(only_in_stock=True)
    scored = [(round(_score(query_words, product), 4), product) for product in candidates]
    scored = [(score, product) for score, product in scored if score >= 0.25]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if category:
        category_words = _tokens(category)
        scored = [(score, product) for score, product in scored if category.lower() in product.category.lower() or category_words & _tokens(product.category)]
    if not scored:
        return [], []
    exact = [product for score, product in scored if score >= 0.75][:limit]
    exact_ids = {product.id for product in exact}
    similar = [product for score, product in scored if product.id not in exact_ids][:limit]
    return exact, similar


def _average_hash(image_bytes: bytes) -> int:
    image = Image.open(BytesIO(image_bytes)).convert("L").resize((16, 16))
    pixels = list(image.getdata())
    average = sum(pixels) / len(pixels)
    value = 0
    for pixel in pixels:
        value = (value << 1) | int(pixel >= average)
    return value


def match_image(image_bytes: bytes, limit: int = 5) -> list[CatalogProduct]:
    """AI'siz katalog rasmi bilan o'xshashlikni topadi (duplicate/resize uchun)."""
    try:
        target = _average_hash(image_bytes)
    except Exception:
        return []
    matches = []
    for product in list_products(only_in_stock=True):
        if not product.image_path:
            continue
        try:
            with open(product.image_path, "rb") as image_file:
                candidate = _average_hash(image_file.read())
            distance = (target ^ candidate).bit_count()
            if distance <= 8:
                matches.append((distance, product))
        except (OSError, ValueError):
            continue
    matches.sort(key=lambda item: item[0])
    return [product for _, product in matches[:limit]]

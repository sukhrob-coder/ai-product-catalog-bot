"""Keep one file for identical generated/catalog images without deleting products."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
from PIL import Image
from sqlalchemy import select

import config
from database import Product, session_scope


def main() -> None:
    image_dir = Path(config.IMAGES_DIR)
    files = sorted(image_dir.glob("web_*.jpg"))
    by_hash: dict[str, tuple[Path, np.ndarray]] = {}
    removed = 0
    with session_scope() as session:
        for path in files:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            current_hash = np.asarray(Image.open(path).convert("L").resize((16, 16)))
            current_hash = current_hash > current_hash.mean()
            keeper = by_hash.get(digest)
            if keeper is None:
                keeper = next((value for value in by_hash.values()
                               if np.count_nonzero(current_hash != value[1]) == 0), None)
            if keeper is None:
                by_hash[digest] = (path, current_hash)
                continue
            session.query(Product).filter(Product.image_path == str(path)).update({"image_path": str(keeper[0])})
            path.unlink()
            removed += 1

    for path in image_dir.glob("demo_*.png"):
        path.unlink()
        removed += 1
    print(f"{removed} ta duplicate/ishlatilmayotgan rasm olib tashlandi")


if __name__ == "__main__":
    main()

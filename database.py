"""PostgreSQL modeli va mahsulot katalogi operatsiyalari."""
from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, func, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

import config


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    products: Mapped[list["Product"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    normalized_name: Mapped[str] = mapped_column(String(255), index=True)
    price: Mapped[float] = mapped_column(Float, default=0)
    quantity: Mapped[float] = mapped_column(Float, default=0)
    barcode: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
    created_at: Mapped[object] = mapped_column(DateTime, server_default=func.now())
    category: Mapped[Category | None] = relationship(back_populates="products")


engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    Base.metadata.create_all(engine)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().strip())


def _meaningful_words(value: str) -> set[str]:
    return {
        word for word in re.findall(r"[\w-]+", normalize(value))
        if len(word) > 2 and word != "star" and not word.isdigit()
    }


@dataclass
class CatalogProduct:
    id: str
    name: str
    price: float
    qty: float
    category: str
    image_path: str | None


def _dto(product: Product) -> CatalogProduct:
    return CatalogProduct(
        id=str(product.id), name=product.name, price=product.price, qty=product.quantity,
        category=product.category.name if product.category else "", image_path=product.image_path,
    )


def list_products(only_in_stock: bool = True) -> list[CatalogProduct]:
    with session_scope() as session:
        stmt = select(Product).where(Product.is_active.is_(True))
        if only_in_stock:
            stmt = stmt.where(Product.quantity > 0)
        return [_dto(item) for item in session.scalars(stmt).all()]


def search_products(query: str, category: str = "", limit: int = 5) -> tuple[list[CatalogProduct], list[CatalogProduct]]:
    """Nom mosligi va nom tokenlari o'xshashligi bo'yicha qidiradi.

    Kategoriya faqat aniq topilgan mahsulotlar ichidan o'xshash nomlarni
    cheklash uchun ishlatiladi; kategoriyadagi barcha mahsulotlar qaytmaydi.
    """
    words = _meaningful_words(query)
    with session_scope() as session:
        base = select(Product).where(Product.is_active.is_(True), Product.quantity > 0)
        exact_name = normalize(query)
        exact_stmt = base.where(Product.normalized_name == exact_name)
        if category:
            exact_stmt = exact_stmt.where(Product.category.has(Category.name.ilike(f"%{category}%")))
        exact = list(session.scalars(exact_stmt.limit(limit)).all())

        name_conditions = [Product.normalized_name.ilike(f"%{word}%") for word in words]
        if name_conditions and not exact:
            token_stmt = base.where(or_(*name_conditions))
            if category:
                token_stmt = token_stmt.where(Product.category.has(Category.name.ilike(f"%{category}%")))
            token_matches = session.scalars(token_stmt.limit(limit * 2)).all()
            seen = {item.id for item in exact}
            exact.extend(item for item in token_matches if item.id not in seen)
            exact = exact[:limit]
        elif category:
            exact_stmt = base.where(Product.category.has(Category.name.ilike(f"%{category}%")))
            exact = list(session.scalars(exact_stmt.limit(limit)).all())

        category_names = {item.category.name for item in exact if item.category}
        similar: list[Product] = []
        if category_names:
            similar_stmt = base.where(Product.category.has(Category.name.in_(category_names)), Product.id.not_in([item.id for item in exact]))
            candidates = session.scalars(similar_stmt).all()
            target_words = words or set().union(*(_meaningful_words(item.name) for item in exact))
            ranked = []
            for candidate in candidates:
                overlap = len(target_words & _meaningful_words(candidate.name))
                if overlap:
                    ranked.append((overlap, candidate))
            ranked.sort(key=lambda item: item[0], reverse=True)
            similar = [item for _, item in ranked[:limit]]
        return [_dto(item) for item in exact], [_dto(item) for item in similar]


def upsert_products(rows: Iterable[dict]) -> int:
    count = 0
    with session_scope() as session:
        for row in rows:
            name = str(row["name"]).strip()
            category_name = str(row.get("category") or "Boshqa").strip() or "Boshqa"
            category = session.scalar(select(Category).where(Category.name.ilike(category_name)))
            if not category:
                category = Category(name=category_name)
                session.add(category)
                session.flush()
            barcode = str(row.get("barcode") or "").strip() or None
            product = session.scalar(select(Product).where(Product.barcode == barcode)) if barcode else None
            if not product:
                product = session.scalar(select(Product).where(Product.name == name, Product.category_id == category.id))
            if not product:
                product = Product(name=name, normalized_name=normalize(name), category=category)
                session.add(product)
            product.name = name
            product.normalized_name = normalize(name)
            product.price = float(row.get("price") or 0)
            product.quantity = float(row.get("quantity") or 0)
            product.barcode = barcode
            product.image_path = row.get("image_path") or None
            product.is_active = True
            count += 1
    return count


def find_product_by_name(name: str, category: str = "") -> CatalogProduct | None:
    """Yangi qo'shishdan oldin ayni nomdagi faol mahsulotni topadi."""
    normalized = normalize(name)
    with session_scope() as session:
        stmt = select(Product).where(Product.is_active.is_(True), Product.normalized_name == normalized)
        if category:
            stmt = stmt.where(Product.category.has(Category.name.ilike(category)))
        product = session.scalar(stmt)
        return _dto(product) if product else None


def increase_product_quantity(product_id: str, amount: float = 1) -> CatalogProduct:
    with session_scope() as session:
        product = session.get(Product, int(product_id))
        if not product:
            raise ValueError("Mahsulot topilmadi")
        product.quantity += float(amount)
        return _dto(product)

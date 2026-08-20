"""FastAPI HTTP API for the PostgreSQL catalog."""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict

import config
from catalog import import_excel
from database import init_db, list_products, search_products
from retrieval import retrieve

app = FastAPI(title="Telegram Shop Manager API", version="1.0.0")


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    qty: float
    category: str
    image_path: str | None = None


class SearchResponse(BaseModel):
    exact: list[ProductResponse]
    similar: list[ProductResponse]


def require_admin(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if not config.INTERNAL_API_KEY or x_api_key != config.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Admin API key required")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/products", response_model=list[ProductResponse])
def products(in_stock: bool = True) -> list[ProductResponse]:
    return list_products(only_in_stock=in_stock)


@app.get("/api/v1/products/search", response_model=SearchResponse)
def search(q: str = Query(min_length=1), category: str = "") -> SearchResponse:
    exact, similar = retrieve(q, category=category)
    return SearchResponse(exact=exact, similar=similar)


@app.post("/api/v1/admin/import", dependencies=[Depends(require_admin)])
async def import_catalog(file: UploadFile = File(...)) -> dict[str, int]:
    path = os.path.join("/tmp", "star_elect_import.xlsx")
    with open(path, "wb") as output:
        output.write(await file.read())
    import config as app_config
    old_path = app_config.EXCEL_PATH
    app_config.EXCEL_PATH = path
    try:
        return {"imported": import_excel()}
    finally:
        app_config.EXCEL_PATH = old_path

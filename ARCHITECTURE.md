# Architecture

```text
Telegram users
      |
      v
  main.py  ----------------------+
      |                          |
      v                          v
  ai_helper.py              poster.py
      |                          |
      +------------+-------------+
                   v
              database.py
                   |
                   v
              PostgreSQL

HTTP clients -> api.py -> database.py -> PostgreSQL
```

## Responsibilities

- `database.py`: SQLAlchemy model, session boundary, catalog queries and upsert.
- `catalog.py`: EasyTrade Excel import.
- `main.py`: Telegram adapter; admin and customer flows only.
- `ai_helper.py`: Gemini post generation and product-query extraction.
- `poster.py`: scheduled/channel posting using DB products.
- `api.py`: FastAPI read/search endpoints and protected admin import endpoint.
- PostgreSQL: product/category source of truth; `data/images` is only media storage.

## API

- `GET /health`
- `GET /api/v1/products?in_stock=true`
- `GET /api/v1/products/search?q=led&category=Yoritish`
- `POST /api/v1/admin/import` with `X-API-Key` and multipart Excel file

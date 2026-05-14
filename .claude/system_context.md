# System Context — Etsy Listing Manager
> File này là nguồn sự thật duy nhất về kiến trúc kỹ thuật. Architect Agent đọc file này thay vì scan toàn bộ codebase.
> Cập nhật cuối: 2026-05-13

---

## Tổng Quan Sản Phẩm

- **EtseeMate** là SaaS B2B cung cấp tool phân tích hiệu suất và optimize listing cho Etsy sellers.
- **Khách hàng (ICP):** Etsy seller cá nhân / shop nhỏ đang chạy Etsy Ads.
- **Trạng thái hiện tại:** Single-tenant pilot — data trong DB là của 1 seller reference account. Đang phát triển hướng multi-tenant.
- **Competitor:** eRank, Marmalead, Sale Samurai.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Vanilla HTML / CSS / JS (không framework) |
| Backend | FastAPI (Python), async SQLAlchemy 2.x |
| DB chính | PostgreSQL (Neon) — listings, reports, config |
| DB market | PostgreSQL riêng (`ETSY_MARKET_DB`) — etsy_star_engine output |
| ML / AI | scikit-learn, HuggingFace, Claude API (`claude-sonnet-4-6` default) |
| Deploy | Render.com (render.yaml) |

---

## Database Schema — DB Chính (`DATABASE_URL`)

### `listings`
| Column | Type | Ghi chú |
|---|---|---|
| id | String(36) PK | UUID |
| idea_sku | String(64) | indexed |
| ma_tam_listing | String(64) | |
| sample_sku | Text | |
| title | Text NOT NULL | |
| store | String(64) | indexed |
| personalization | Text | |
| description | Text | |
| tag | Text | comma-separated |
| attribute | Text | |
| trang_thai | String(32) | "Open"/"Closed", indexed |
| listing_id | String(32) | Etsy listing ID |
| listing_link | Text | |
| media_link | Text | |
| optimized_title | Text | AI output |
| optimized_tags | Text | AI output |
| optimized_description | Text | AI output |
| created_at | DateTime TZ | server_default |
| updated_at | DateTime TZ | onupdate |

### `listing_report`
| Column | Type | Ghi chú |
|---|---|---|
| id | Integer PK autoincrement | |
| listing_id | String(32) NOT NULL | FK logic (không enforce) |
| title | Text | |
| no_vm | String(16) | variation manager ID |
| price | Numeric(10,2) | |
| stock | Integer | |
| category | String(64) | |
| lifetime_orders | Integer | |
| lifetime_revenue | Numeric(12,2) | |
| period | String(32) NOT NULL | |
| views / clicks / orders | Integer | |
| revenue / spend | Numeric(12,2) | |
| roas | Numeric(8,2) | |
| import_time | DateTime TZ | |
| importer | String(64) | |

### `keyword_report`
Cùng structure với `listing_report` + thêm:
- `keyword` Text NOT NULL
- `click_rate` String(8)
- `relevant` String(8)
- Không có `price`, `stock`, `category`, `lifetime_*`

### `manual_listing_report`
= `listing_report` + thêm `batch_id String(64)`

### `manual_keyword_report`
= `keyword_report` + thêm `batch_id String(64)`

### `import_batch`
| Column | Type | Ghi chú |
|---|---|---|
| batch_id | String(32) PK | format `YYYYMMDD_HHMM` |
| status | String(16) | "uploaded"/"processing"/"confirmed"/"discarded" |
| file_count / listing_count / keyword_count | Integer | |
| progress / total_files | Integer | |
| created_at / confirmed_at | DateTime TZ | |
| note / error_message | Text | |
| image_files | JSONB | `[{"name","url","fileId"}]` |
| preview_data | JSONB | extraction preview (no filesystem dep) |
| snapshot_data | JSONB | final snapshot after confirm |

### `thumbnail_knowledge`
| Column | Type | Ghi chú |
|---|---|---|
| id | Integer PK autoincrement | |
| product_type | String(64) NOT NULL | onesie/blanket/sweater/crown/other |
| target_audience | String(64) NOT NULL | derived từ title clustering |
| patterns | JSON NOT NULL | { dominant_colors, bg_style, text_overlay, composition, mood, common_props, ta_signals, sample_count } |
| sample_urls | JSON | list image_urls đã dùng khi generate |
| sample_count | Integer | |
| generated_at | DateTime TZ | server_default |
| UNIQUE | (product_type, target_audience) | |

Source: market_listing WHERE badge ILIKE '%popular now%' OR '%best seller%'. Vision model: claude-haiku-4-5-20251001.

### `threshold_configs`
| Column | Type |
|---|---|
| id | Integer PK |
| roas_be | Numeric(5,2) — ROAS huề vốn |
| cr_high | Numeric(5,2) — CR cao ≥ X% |
| ctr_high | Numeric(5,2) — CTR cao ≥ X% |
| note | Text |
| created_by | Text |
| created_at | DateTime TZ |

### `scenarios_rules`
| Column | Type |
|---|---|
| id | Integer PK |
| roas_band | String(32) |
| cr_level / ctr_level | String(8) |
| case_name | Text |
| action | String(32) |
| cause / fix_listing / fix_ads | Text |
| updated_at | DateTime TZ |

---

## Database Schema — DB Market (`ETSY_MARKET_DB`)

### `market_listing` (read-only từ backend)
| Column | Type | Ghi chú |
|---|---|---|
| listing_id | text | Etsy listing ID |
| keyword | text | `search_tag` trong references |
| url | text | URL trang listing Etsy |
| image_url | text | `https://i.etsystatic.com/...` — thumbnail chính |
| title | text | |
| shop_name | text | |
| price | numeric | |
| discount | numeric | |
| rating | numeric | |
| review_count | integer | |
| tag_ranking | integer | thứ hạng keyword — thấp = trending cao |
| badge | text | |
| free_shipping | boolean | |
| is_ad | boolean | |
| product_type | text | backfill bởi Gemini (references_service) |
| crawled_at | timestamptz | |

---

## API Endpoints — `/api/v1`

### Listings `/api/v1/listings`
| Method | Path | Mô tả |
|---|---|---|
| GET | `/` | Danh sách listings (query filter) |
| GET | `/{listing_id}` | Chi tiết 1 listing |
| POST | `/` | Tạo listing mới |
| PATCH | `/{listing_id}` | Cập nhật listing |
| DELETE | `/{listing_id}` | Xóa listing |
| GET | `/stats/count` | Tổng số listings |

### Internal `/api/v1/internal` — Import pipeline
| Method | Path | Mô tả |
|---|---|---|
| GET | `/status` | Trạng thái batch hiện tại |
| GET | `/preview` | Xem trước dữ liệu extract |
| POST | `/upload` | Upload file báo cáo |
| POST | `/extract` | Chạy OCR/extract |
| POST | `/confirm` | Confirm batch → merge vào DB |
| POST | `/discard` | Hủy batch |
| POST | `/rollback` | Rollback batch đã confirm |
| GET | `/history` | Lịch sử import batches |
| GET | `/snapshot/{batch_id}` | Snapshot data của batch |

### Performance `/api/v1/performance`
| Method | Path | Mô tả |
|---|---|---|
| GET | `/listings` | Dashboard (join internal DB + market DB) |
| POST | `/refresh` | Trigger refresh ETL |

### Market `/api/v1/market`
| Method | Path | Mô tả |
|---|---|---|
| GET | `/samples` | Sample market listings theo product_type |

### Thresholds `/api/v1/thresholds`
| Method | Path | Mô tả |
|---|---|---|
| GET | `/current` | Config threshold hiện tại |
| GET | `/history` | Lịch sử thay đổi |
| POST | `` | Tạo config mới |

### Scenarios `/api/v1/scenarios`
| Method | Path | Mô tả |
|---|---|---|
| GET | `/rules` | Danh sách scenario rules |
| POST | `/rules` | Tạo rule mới |
| PUT | `/rules/{rule_id}` | Cập nhật rule |
| DELETE | `/rules/{rule_id}` | Xóa rule |

### Intelligence `/api/v1/intelligence`
| Method | Path | Mô tả |
|---|---|---|
| POST | `/thumbnail-knowledge/generate` | Generate knowledge từ badge-filtered market_listing (Popular now / Best Seller) |
| GET | `/thumbnail-knowledge` | List knowledge records, filter `?product_type=` |
| POST | `/thumbnail-eval` | Evaluate 1 ảnh thumbnail (multipart: image + product_type) |

### References `/api/v1/references`
| Method | Path | Mô tả |
|---|---|---|
| GET | `` | Danh sách references |
| GET | `/{listing_id}` | References của listing |
| POST | `/refresh` | Rebuild references từ market_listing |

---

## Cấu trúc thư mục Backend

```
backend/app/
├── core/
│   ├── config.py       — Settings (lru_cache), env vars
│   └── database.py     — AsyncEngine x2 (internal + market), get_db()
├── models/             — SQLAlchemy ORM models
├── schemas/            — Pydantic request/response schemas
├── api/routes/         — FastAPI routers (chỉ validate + delegate)
└── services/           — Business logic
    ├── listing_service.py
    ├── performance_service.py
    ├── internal_service.py
    ├── internal_extractor.py   — OCR/extract logic
    ├── reporting_etl.py
    ├── references_service.py
    ├── crawler_ops.py
    ├── imagekit_service.py
    └── claude_service.py       — Tập trung mọi Claude API call
```

---

## Frontend

- File chính: `frontend/etseemate.html`
- `frontend/index.html` — landing page
- Design tokens: `docs/DESIGN.md` (CSS vars: `--terracotta`, `--parchment`, ...)
- JS: `frontend/js/`, CSS: `frontend/css/`
- Gọi backend qua `fetch('/api/v1/...')` — không gọi thẳng DB

---

## Env Vars

| Var | Dùng cho |
|---|---|
| `DATABASE_URL` | Neon PostgreSQL — internal data |
| `ETSY_MARKET_DB` | Market data DB (etsy_star_engine output) |
| `ANTHROPIC_API_KEY` | Claude API |
| `CLAUDE_MODEL` | Model ID (default `claude-sonnet-4-6`) |
| `APP_ENV` | `development` / `production` |
| `SECRET_KEY` | App secret |
| `ALLOWED_ORIGINS` | CORS (comma-separated) |

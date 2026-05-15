# System Context — Etsy Listing Manager
> File này là nguồn sự thật duy nhất về kiến trúc kỹ thuật. Architect Agent đọc file này thay vì scan toàn bộ codebase.
> Cập nhật cuối: 2026-05-14 (sync commit 0ff771f)

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

### `listings_int_ext` (materialized reporting — rebuilt by `reporting_etl`)
| Column | Type | Ghi chú |
|---|---|---|
| listing_id | VARCHAR(32) | |
| period | VARCHAR(32) | |
| reference_date | TIMESTAMPTZ | |
| title | TEXT | |
| no_vm | VARCHAR(16) | |
| product | VARCHAR(64) | |
| url | TEXT | |
| views / clicks / orders | INTEGER | |
| revenue / spend | NUMERIC(12,2) | |
| roas | NUMERIC(8,2) | |
| ctr / cr | NUMERIC(6,2) | |
| cpc / cpp | NUMERIC(10,2) | |
| roas_band | VARCHAR(16) | |
| cr_level / ctr_level | VARCHAR(8) | |
| PRIMARY KEY | (listing_id, period) | |

### `listings_int_hist` (per-period history)
| Column | Type |
|---|---|
| listing_id | VARCHAR(32) |
| period | VARCHAR(32) |
| reference_date | TIMESTAMPTZ |
| views / clicks / orders | INTEGER |
| revenue / spend | NUMERIC(12,2) |
| roas / cpc / cpp | NUMERIC |
| source | VARCHAR(16) |
| rebuilt_at | TIMESTAMPTZ |
| PRIMARY KEY | (listing_id, period) |

### `keywords` (materialized keyword reporting)
| Column | Type |
|---|---|
| listing_id | VARCHAR(32) |
| keyword | TEXT |
| period | VARCHAR(32) |
| currently_status | VARCHAR(8) |
| views / clicks / orders | INTEGER |
| revenue / spend | NUMERIC(12,2) |
| roas / cpc / cpp | NUMERIC |
| click_rate | VARCHAR(8) |
| rebuilt_at | TIMESTAMPTZ |
| PRIMARY KEY | (listing_id, keyword, period) |

### `refresh_state` (singleton — advisory lock control)
| Column | Type | Ghi chú |
|---|---|---|
| id | INTEGER PK | luôn = 1 |
| last_refresh_at | TIMESTAMPTZ | |
| ingest_signature | TEXT | sha256 của raw import_time maxes — debounce |
| duration_ms | INTEGER | |
| row_counts | JSONB | |

### `crawl_run` (crawler ledger — DB chính)
| Column | Type | Ghi chú |
|---|---|---|
| id | SERIAL PK | |
| job_name | VARCHAR(64) | market / internal / rank |
| started_at / finished_at | TIMESTAMPTZ | |
| status | VARCHAR(16) | running / done / failed |
| target_count / success_count / fail_count | INTEGER | |
| error_summary | TEXT | |
| host | VARCHAR(64) | |
| metadata | JSONB | |

### `crawl_queue` (pending listings cho internal_listing_crawler)
| Column | Type | Ghi chú |
|---|---|---|
| listing_id | VARCHAR(32) PK | |
| queued_at | TIMESTAMPTZ | |
| last_attempt | TIMESTAMPTZ | |
| attempts | INTEGER | |
| next_after | TIMESTAMPTZ | |
| reason | VARCHAR(32) | |
| status | VARCHAR(16) | pending / done / failed |

### `thumbnail_knowledge` (vision knowledge base — chưa migrate)
| Column | Type | Ghi chú |
|---|---|---|
| id | SERIAL PK | |
| product_type | VARCHAR(64) | |
| target_audience | VARCHAR(64) | |
| patterns | JSONB | visual patterns từ trending thumbnails |
| sample_urls | JSONB | image_urls đã dùng để generate |
| sample_count | INTEGER | |
| generated_at | TIMESTAMPTZ | |
| UNIQUE | (product_type, target_audience) | |

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
| GET | `/listings` | Dashboard từ `listings_int_ext` (materialized) |
| POST | `/refresh` | Trigger `reporting_etl.rebuild_reporting()` — debounce qua `ingest_signature` |

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

### Intelligence `/api/v1/intelligence` *(mới — chưa hoàn chỉnh)*
| Method | Path | Mô tả |
|---|---|---|
| POST | `/thumbnail-knowledge/generate` | Generate visual knowledge từ badge-filtered market_listing |
| GET | `/thumbnail-knowledge` | List knowledge records theo category |
| POST | `/thumbnail-eval` | Evaluate 1 ảnh thumbnail theo segment |

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
│   ├── config.py           — Settings (lru_cache), env vars
│   └── database.py         — AsyncEngine x2 (internal + market), get_db()
├── models/                 — SQLAlchemy ORM models
├── schemas/
│   └── vision_schema.py    — Thumbnail eval schemas (mới)
├── api/routes/
│   └── intelligence.py     — /api/v1/intelligence (mới)
└── services/
    ├── listing_service.py
    ├── performance_service.py
    ├── internal_service.py
    ├── internal_extractor.py   — OCR/extract logic
    ├── reporting_etl.py        — Materialized reporting rebuild + debounce
    ├── references_service.py
    ├── crawler_ops.py          — crawl_run + crawl_queue DDL + helpers
    ├── imagekit_service.py     — ImageKit screenshot storage
    ├── vision_service.py       — Thumbnail knowledge + eval (mới)
    └── claude_service.py       — Tập trung mọi Claude API call

market_engine_crawler/          — Chạy trên Mac #2 (24/7)
├── run_scheduled.py            — Dispatcher 3 crawlers
├── crawl_ledger.py             — start_run / finish_run / queue helpers
├── captcha_notify.py           — Email alert + poll-resume khi CAPTCHA
└── launchd/                    — macOS launchd plists
    ├── com.etseemate.crawler.market.plist    (weekly Mon 02:00)
    ├── com.etseemate.crawler.internal.plist  (every 30m)
    ├── com.etseemate.crawler.rank.plist      (daily 04:00)
    └── git-sync.plist                        (every 5m)
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
| `GEMINI_API_KEY_paid` | Gemini Vision — primary (trả phí) |
| `GEMINI_API_KEY_free` | Gemini Vision — fallback (free tier) |
| `GEMINI_MODEL` | default `gemini-2.5-flash-lite` |
| `HUGGINGFACE_API_KEY` | HuggingFace router — fallback vision |
| `HF_MODEL` | default `zai-org/GLM-4.5V` |
| `IMAGEKIT_PUBLIC_KEY` | ImageKit screenshot storage |
| `IMAGEKIT_PRIVATE_KEY` | ImageKit screenshot storage |
| `IMAGEKIT_URL_ENDPOINT` | ImageKit screenshot storage |
| `IMAGEKIT_FOLDER` | default `/listing/EtseeMate` |
| `APP_ENV` | `development` / `production` |
| `SECRET_KEY` | App secret |
| `ALLOWED_ORIGINS` | CORS (comma-separated) |

---

## Auth & Payment System (Added 2026-05-14)

### New DB Tables

**users**: id(UUID PK), email(VARCHAR 255 UNIQUE), password_hash(VARCHAR 255), full_name(VARCHAR 128), is_active(BOOL), is_admin(BOOL), created_at, updated_at

**subscriptions**: id(UUID PK), user_id(UUID FK), plan(VARCHAR 32), status(VARCHAR 16: active/cancelled/expired), period_start(TIMESTAMPTZ), period_end(TIMESTAMPTZ), stripe_sub_id(VARCHAR 128), created_at

**credit_accounts**: id(UUID PK), user_id(UUID FK UNIQUE), balance(INT), updated_at

**credit_transactions**: id(UUID PK), user_id(UUID FK), amount(INT), tx_type(VARCHAR 16: deposit/debit), description(TEXT), stripe_pi_id(VARCHAR 128), created_at

**payment_records**: id(UUID PK), user_id(UUID FK nullable), stripe_event_id(VARCHAR 128 UNIQUE), event_type(VARCHAR 64), amount_cents(INT), currency(VARCHAR 8), payload(JSONB), processed_at(TIMESTAMPTZ)

### New API Endpoints

**Auth:**
- POST /api/v1/auth/register — public
- POST /api/v1/auth/login — public
- POST /api/v1/auth/refresh — public (refresh cookie)
- POST /api/v1/auth/logout — auth required
- GET /api/v1/auth/me — auth required → profile + subscription + credit balance

**Billing:**
- POST /api/v1/billing/subscribe — auth required → Stripe Checkout URL (subscription)
- GET /api/v1/billing/subscription — auth required → subscription status
- POST /api/v1/billing/cancel — auth required → cancel at period end
- POST /api/v1/billing/deposit — auth required → Stripe Checkout URL (one-time payment)
- GET /api/v1/billing/credits — auth required → balance + history
- POST /api/v1/billing/webhook — NO auth (Stripe sig verify) → process events

### Auth Gates
- /api/v1/performance/* → require active subscription
- /api/v1/intelligence/thumbnail-eval → require credit ≥ 1 (deduct 1 on success)

### Payment Gateway
- Stripe Checkout (hosted page)
- Webhook: checkout.session.completed (activate sub or credit +10), customer.subscription.deleted (expire sub)

### New Env Vars
JWT_SECRET_KEY, JWT_ALGORITHM, JWT_ACCESS_EXPIRE_MIN, JWT_REFRESH_EXPIRE_DAYS,
STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PUBLISHABLE_KEY,
STRIPE_PRICE_SUBSCRIPTION, STRIPE_PRICE_CREDIT_DEPOSIT

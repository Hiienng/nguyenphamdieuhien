# Data Description — Internal Listing DB

> Database: Neon PostgreSQL · Schema: `public` · Cập nhật: 2026-05-11

---

## Tổng quan
 
### Ingestion layer
A. DB etsy_pilot
|No.| Bảng | Mô tả | Status |
| --- |---|---|---|
|1.1 | `listing_report` | **Spy flow** Hiệu suất ads theo period / daily của từng listing | Có duplicate `(listing_id, period)` qua nhiều `import_time`. Pipeline reporting dedup bằng GROUP BY + MAX-per-metric, KHÔNG dùng `DISTINCT ON ORDER BY import_time DESC` (xem ghi chú §2.2). |
|1.2 | `keyword_report` | **Spy flow** Hiệu suất từng keyword ads trong từng period | Period có thể là `custom_default` — pipeline reporting BỎ QUA các row này khi tính `latest_period`. |
|2.1 | `import_batch` | **Manual import flow** Trạng thái từng batch import ảnh screenshot |Data clean|
|2.2 | `manual_listing_report` | **Manual import flow** Hiệu suất ads theo period / daily của từng listing | Một số dòng có cùng `(listing_id, period)` nhưng cột metric lúc = 0 lúc có value. Dedup bằng GROUP BY `(listing_id, period)` + `MAX(metric)` per column. Lý do: dòng latest theo `import_time` có thể là dòng zero-filled. KHÔNG dùng `DISTINCT ON ORDER BY import_time DESC`. |
|2.3| `manual_keyword_report` | **Manual import flow** Hiệu suất từng keyword ads trong từng period | UNION với `keyword_report` trong pipeline reporting, ưu tiên source manual khi conflict. |
|4.1| `scenarios_rules` | Ma trận kịch bản phân loại theo ROAS / CR / CTR |Data clean|
|4.2| `threshold_configs` | Ngưỡng ROAS / CR / CTR do user cấu hình |Data clean|
|4.3| `references_engine` | Listing đối thủ tham chiếu cho từng listing |Data clean|
|4.4| `listing_extense` | Dữ liệu thị trường mở rộng (crawl từ Etsy search) | Không tham gia `ingest_signature` — thay đổi bảng này KHÔNG tự trigger rebuild reporting. |

B. DB etsy_market_db
|No.| Bảng | Mô tả | Status |
| --- |---|---|---|
|1| `market_listing` | Snapshot listing đối thủ crawl từ Etsy search | Data clean|
|2| `market_listing_details` | Chi tiết sâu của listing đối thủ (giá, ship, AI summary) | Data clean|
|3| `market_listing_reviews` | Reviews của listing đối thủ | Data clean|
|4| `market_shop` | Thông tin shop đối thủ | Data clean|
|5| `keyword_rank_snapshot` | Lịch sử rank của listing theo keyword tại từng thời điểm crawl | Data clean|

### Reporting layer
|No.| Bảng | Mô tả | Status |
| --- |---|---|---|
|1 | `listings` | Master list các listing đang theo dõi (theo dõi unique internal listing_id từ `listing_report` và `manul_keyword_report`)| Data clean|
|2 | `listings_int_ext` | Báo cáo period range mới nhất của mỗi listing, bao gồm internal indicator (views/clicks/orders/revenue/spend/roas + cpc/cpp nội suy) và scenario (roas_band, cr_level, ctr_level + scenarios_rules) | Materialized — populate bởi `reporting_etl.rebuild_reporting()` |
|3 | `keywords` | Báo cáo keyword của import_time mới nhất mỗi listing, bao gồm internal indicator + cpc/cpp nội suy | Materialized — populate bởi `reporting_etl.rebuild_reporting()` |
|4 | `listings_int_hist` | Lịch sử daily (period dạng `YYYY-MM-DD`) của mỗi listing, bao gồm internal indicator + cpc/cpp nội suy | Materialized — populate bởi `reporting_etl.rebuild_reporting()` |
|5 | `refresh_state` | Singleton trạng thái lần rebuild gần nhất: `last_refresh_at`, `ingest_signature` (sha256 của max(import_time) các bảng raw), `duration_ms`, `row_counts` | Materialized |

* Internal indicators: views, clicks, orders, revenue, spend, roas, và 2 trường nội suy cpc=spend/clicks và cpp= spend/orders
* External indicators: price, rating, review_count, badge, discount, free_shipping, is_ad, url (lấy từ `etsy_market_db.market_listing` tại thời điểm serving, không materialize)

#### Pipeline rebuild

Trigger:
- `POST /api/v1/performance/refresh` (user bấm "Tải lại" trên FE Listing Improvement)
- `POST /api/v1/internal/confirm` (auto rebuild ngay sau khi import manual batch xong)
- Application startup (lifespan) — nếu `refresh_state` chưa có row nào (fresh deploy)

Logic:
1. Compute `ingest_signature` = sha256(MAX(import_time) lấy từ `listing_report`, `manual_listing_report`, `keyword_report`, `manual_keyword_report`, `references_engine`).
2. So với `refresh_state.ingest_signature`. Bằng + không `force` → trả `{status: 'cached'}`, không rebuild.
3. Khác → lấy PG advisory lock (key `0x4953524C` = ASCII `"ISRL"`, debug bằng `SELECT * FROM pg_locks WHERE locktype='advisory'`). Nếu lock bận → `{status: 'in_progress'}`.
4. `TRUNCATE` + `INSERT … SELECT` 3 bảng reporting trong 1 transaction. Dedup dùng **GROUP BY (listing_id, period) + MAX(metric)**, KHÔNG dùng `DISTINCT ON ... ORDER BY import_time DESC` — vì một số `(listing_id, period)` có nhiều rows mà row latest có metric = 0 (xem ghi chú `manual_listing_report` §2.2).
5. Upsert `refresh_state` + commit + release lock.

Serving (`GET /api/v1/performance/listings`) chỉ SELECT từ 3 bảng materialized + JOIN LATERAL `references_engine`/`keywords`/`listings_int_hist`, không còn join trực tiếp với raw.

#### Suggestion logic (runtime, không materialize)

Cột "Suggestion" trong sub-table Keywords được tính per-keyword tại FE từ `(orders, roas)` của chính keyword đó:
- Band `no_sales` (orders = 0 hoặc roas = 0) → `suggestion = 'off'`.
- Band `heavy_loss` (0 < roas < 1) → `suggestion = 'off'`.
- Band khác (`slight_loss`, `profitable`) → `suggestion = ''` (hiển thị `—`).

Listing-level band trong `listings_int_ext` chỉ dùng để map `scenarios_rules` (case_name / action / cause / fix_*), không quyết định suggestion keyword.
---

## Quy ước chung

|No.| Quy ước | Giá trị |
| ---|---|---|
|1| Timestamp timezone | Luôn dùng `TIMESTAMPTZ` (UTC) |
|2| `period` format | ISO 8601: `YYYY-MM-DD/YYYY-MM-DD` (range) · `YYYY-MM-DD` (daily) · `custom_default` (fallback) |
|3| Tiền tệ | `NUMERIC(12,2)` = USD · `BIGINT`/`INTEGER` = cents |
|4| `no_vm` | Mã VM viết hoa: `VM01`, `VM08`… |
|5| `importer` | Định danh source: `getify_bot`, `getify_json`, `internal_crawler`, `manual`… |

---

## Data description

### `listing_report`, `manual_listing_report`

Hiệu suất ads của từng listing theo từng period hoặc ngày đơn lẻ (daily breakdown). Với `listing_report` là kết quả của luồng crawl internal listing tự động (không có trong source code này), `manual_listing_report` là kết quả của  luồng **Manual Import**

| Column | PG Type | SQLAlchemy | Nullable | Ghi chú |
|---|---|---|---|---|
| `id` | `SERIAL` | `Integer` | NOT NULL | Primary key, auto-increment |
| `listing_id` | `VARCHAR(32)` | `String(32)` | NOT NULL | Etsy listing ID (FK → `listings.listing_id`) |
| `title` | `TEXT` | `Text` | YES | Tiêu đề listing tại thời điểm import |
| `no_vm` | `VARCHAR(16)` | `String(16)` | YES | Mã VM |
| `price` | `NUMERIC(10,2)` | `Numeric(10,2)` | YES | Giá bán (USD) |
| `stock` | `INTEGER` | `Integer` | YES | Số lượng tồn kho |
| `category` | `VARCHAR(64)` | `String(64)` | YES | Danh mục sản phẩm |
| `lifetime_orders` | `INTEGER` | `Integer` | YES | Tổng đơn hàng lifetime |
| `lifetime_revenue` | `NUMERIC(12,2)` | `Numeric(12,2)` | YES | Tổng doanh thu lifetime (USD) |
| `period` | `VARCHAR(32)` | `String(32)` | NOT NULL | **ISO 8601**: `YYYY-MM-DD/YYYY-MM-DD` (range) hoặc `YYYY-MM-DD` (daily) |
| `views` | `INTEGER` | `Integer` | YES | Lượt xem trong period |
| `clicks` | `INTEGER` | `Integer` | YES | Lượt click trong period |
| `orders` | `INTEGER` | `Integer` | YES | Số đơn hàng trong period |
| `revenue` | `NUMERIC(12,2)` | `Numeric(12,2)` | YES | Doanh thu ads trong period (USD) |
| `spend` | `NUMERIC(12,2)` | `Numeric(12,2)` | YES | Chi tiêu ads trong period (USD) |
| `roas` | `NUMERIC(8,2)` | `Numeric(8,2)` | YES | Return on Ad Spend |
| `import_time` | `TIMESTAMPTZ` | `DateTime(tz=True)` | YES | Thời điểm import |
| `importer` | `VARCHAR(64)` | `String(64)` | YES | Source: `getify_json`, `internal_crawler`… |

> **Period convention:** Một listing có thể có nhiều rows cho cùng `(listing_id, period)` — manual_listing_report đặc biệt hay có dòng zero-filled xen kẽ dòng có value.
>
> **Dedup chuẩn (pipeline reporting đang dùng):** `GROUP BY (listing_id, period) + MAX(metric)` per column. KHÔNG dùng `DISTINCT ON ORDER BY import_time DESC` vì dòng latest theo `import_time` có thể là dòng zero-filled, lấy nguyên row đó sẽ mất data thực.

---

### `keyword_report`, `manual_keyword_report`

Hiệu suất từng keyword trong ads của từng listing, theo period.

| Column | PG Type | SQLAlchemy | Nullable | Ghi chú |
|---|---|---|---|---|
| `id` | `SERIAL` | `Integer` | NOT NULL | Primary key, auto-increment |
| `listing_id` | `VARCHAR(32)` | `String(32)` | NOT NULL | Etsy listing ID |
| `keyword` | `TEXT` | `Text` | NOT NULL | Từ khoá ads |
| `no_vm` | `VARCHAR(16)` | `String(16)` | YES | Mã VM |
| `period` | `VARCHAR(32)` | `String(32)` | NOT NULL | **ISO 8601**: `YYYY-MM-DD/YYYY-MM-DD` hoặc `custom_default` |
| `roas` | `NUMERIC(8,2)` | `Numeric(8,2)` | YES | ROAS của keyword |
| `orders` | `INTEGER` | `Integer` | YES | Số đơn |
| `spend` | `NUMERIC(12,2)` | `Numeric(12,2)` | YES | Chi tiêu (USD) |
| `revenue` | `NUMERIC(12,2)` | `Numeric(12,2)` | YES | Doanh thu (USD) |
| `clicks` | `INTEGER` | `Integer` | YES | Số click |
| `click_rate` | `VARCHAR(8)` | `String(8)` | YES | CTR dạng chuỗi, giữ `%` (VD: `"1.1%"`) |
| `views` | `INTEGER` | `Integer` | YES | Số impressions |
| `relevant` | `VARCHAR(8)` | `String(8)` | YES | Trạng thái toggle: `"on"` / `"off"` / `null` |
| `import_time` | `TIMESTAMPTZ` | `DateTime(tz=True)` | YES | Thời điểm import |
| `importer` | `VARCHAR(64)` | `String(64)` | YES | Source: `getify_bot`, `internal_crawler`… |

> **Period `custom_default`:** Gán khi keyword không có period xác định từ screenshot (fallback). Pipeline reporting BỎ QUA các row này khi tính `latest_period`.
>
> **Latest keyword (pipeline reporting):** Lọc 2 tầng:
> 1. `MAX(period)` per `listing_id` (so sánh chuỗi ISO 8601 = chronological); bỏ `custom_default`.
> 2. Trong period đó, lấy `MAX(import_time)` để chống re-import cùng period.
> 3. `GROUP BY (listing_id, keyword, period)` + `MAX(metric)` tương tự dedup listing.

---

### `import_batch`

Theo dõi trạng thái từng batch upload ảnh screenshot từ FE. Là kết quả của luồng manual

| Column | PG Type | SQLAlchemy | Nullable | Ghi chú |
|---|---|---|---|---|
| `batch_id` | `VARCHAR(32)` | `String(32)` | NOT NULL | Primary key — format `YYYYMMDD_HHMM` |
| `status` | `VARCHAR(16)` | `String(16)` | NOT NULL | `uploaded` / `processing` / `done` / `error` |
| `file_count` | `INTEGER` | `Integer` | YES | Số file trong batch |
| `listing_count` | `INTEGER` | `Integer` | YES | Số listing rows đã xử lý |
| `keyword_count` | `INTEGER` | `Integer` | YES | Số keyword rows đã xử lý |
| `progress` | `INTEGER` | `Integer` | YES | File đã xử lý xong |
| `total_files` | `INTEGER` | `Integer` | YES | Tổng file cần xử lý |
| `created_at` | `TIMESTAMPTZ` | `DateTime(tz=True)` | YES | DEFAULT `now()` |
| `confirmed_at` | `TIMESTAMPTZ` | `DateTime(tz=True)` | YES | Thời điểm user confirm import |
| `note` | `TEXT` | `Text` | YES | Ghi chú tự do |
| `error_message` | `TEXT` | `Text` | YES | Chi tiết lỗi nếu `status = error` |

---

### `scenarios_rules`

Ma trận kịch bản phân loại listing theo 3 chiều: ROAS band × CR level × CTR level.

| Column | PG Type | SQLAlchemy | Nullable | Ghi chú |
|---|---|---|---|---|
| `id` | `SERIAL` | `Integer` | NOT NULL | Primary key |
| `roas_band` | `VARCHAR(32)` | `String(32)` | NOT NULL | `profitable` / `slight_loss` / `heavy_loss` / `no_sales` |
| `cr_level` | `VARCHAR(8)` | `String(8)` | NOT NULL | `high` / `low` / `zero` |
| `ctr_level` | `VARCHAR(8)` | `String(8)` | NOT NULL | `high` / `low` |
| `case_name` | `TEXT` | `Text` | NOT NULL | Tên kịch bản (VD: "Có sales và đang lời") |
| `action` | `VARCHAR(32)` | `String(32)` | NOT NULL | `keep` / `improve` / `improve_or_off` |
| `cause` | `TEXT` | `Text` | YES | Phân tích nguyên nhân |
| `fix_listing` | `TEXT` | `Text` | YES | Hành động cần làm với listing |
| `fix_ads` | `TEXT` | `Text` | YES | Hành động cần làm với ads |
| `updated_at` | `TIMESTAMPTZ` | `DateTime(tz=True)` | NOT NULL | DEFAULT `now()` |

> Bảng được seed lại hoàn toàn mỗi khi gọi `seed_scenarios()`. Không edit trực tiếp DB.

---

### `threshold_configs`

Ngưỡng phân loại ROAS / CR / CTR do user cấu hình, dùng để tính `roas_band`, `cr_level`, `ctr_level`.

| Column | PG Type | SQLAlchemy | Nullable | Ghi chú |
|---|---|---|---|---|
| `id` | `SERIAL` | `Integer` | NOT NULL | Primary key |
| `roas_be` | `NUMERIC(5,2)` | `Numeric(5,2)` | NOT NULL | ROAS hoà vốn (default: 2.0) |
| `cr_high` | `NUMERIC(5,2)` | `Numeric(5,2)` | NOT NULL | Ngưỡng CR cao ≥ X% (default: 3.0) |
| `ctr_high` | `NUMERIC(5,2)` | `Numeric(5,2)` | NOT NULL | Ngưỡng CTR cao ≥ X% (default: 1.5) |
| `note` | `TEXT` | `Text` | YES | Ghi chú |
| `created_by` | `TEXT` | `Text` | NOT NULL | User tạo config |
| `created_at` | `TIMESTAMPTZ` | `DateTime(tz=True)` | NOT NULL | DEFAULT `now()` |

---

### `references_engine`

Listing đối thủ tham chiếu cho từng listing nội bộ. Primary key composite `(listing_id, reference_listing_id)`.

| Column | PG Type | SQLAlchemy | Nullable | Ghi chú |
|---|---|---|---|---|
| `listing_id` | `VARCHAR(32)` | `String(32)` | NOT NULL | PK — listing nội bộ |
| `reference_listing_id` | `TEXT` | `Text` | NOT NULL | PK — listing đối thủ |
| `ref_rank` | `SMALLINT` | `SmallInteger` | NOT NULL | Thứ hạng đối thủ (1 = tốt nhất) |
| `ref_title` | `TEXT` | `Text` | YES | Tiêu đề listing đối thủ |
| `ref_shop` | `TEXT` | `Text` | YES | Tên shop đối thủ |
| `ref_url` | `TEXT` | `Text` | YES | URL listing đối thủ |
| `ref_price` | `INTEGER` | `Integer` | YES | Giá niêm yết (cents USD) |
| `ref_discount` | `INTEGER` | `Integer` | YES | Giá sale (cents USD) |
| `ref_rating` | `REAL` | `Float` | YES | Rating trung bình |
| `ref_review_count` | `INTEGER` | `Integer` | YES | Số review |
| `ref_tag_ranking` | `INTEGER` | `Integer` | YES | Ranking theo tag |
| `ref_badge` | `TEXT` | `Text` | YES | Badge: `"Star Seller"`, `"Bestseller"`… |
| `ref_free_shipping` | `BOOLEAN` | `Boolean` | YES | Có free shipping |
| `ref_product_type` | `TEXT` | `Text` | YES | Loại sản phẩm |
| `ref_import_date` | `DATE` | `Date` | YES | Ngày crawl dữ liệu đối thủ |
| `match_method` | `VARCHAR(16)` | `String(16)` | YES | DEFAULT `'category'` — cách match đối thủ |
| `refreshed_at` | `TIMESTAMPTZ` | `DateTime(tz=True)` | YES | DEFAULT `now()` |

---

### `listing_extense`

Dữ liệu thị trường mở rộng cho tập internal listing, crawl từ Etsy search — dùng cho Research Hub.

| Column | PG Type | SQLAlchemy | Nullable | Ghi chú |
|---|---|---|---|---|
| `id` | `VARCHAR(32)` | `String(32)` | NOT NULL | Primary key — Etsy listing ID |
| `search_tag` | `TEXT` | `Text` | YES | Tag tìm kiếm khi crawl |
| `product_type` | `TEXT` | `Text` | YES | Loại sản phẩm |
| `title` | `TEXT` | `Text` | YES | Tiêu đề listing |
| `price` | `BIGINT` | `BigInteger` | YES | Giá niêm yết (cents USD) |
| `original_price` | `BIGINT` | `BigInteger` | YES | Giá gốc trước sale (cents USD) |
| `shop_name` | `TEXT` | `Text` | YES | Tên shop |
| `rating` | `REAL` | `Float` | YES | Rating (0–5) |
| `review_count` | `INTEGER` | `Integer` | YES | Số review |
| `badge` | `TEXT` | `Text` | YES | `"Star Seller"`, `"Bestseller"`… |
| `discount` | `INTEGER` | `Integer` | YES | % giảm giá |
| `free_shipping` | `BOOLEAN` | `Boolean` | YES | Có free shipping |
| `is_ad` | `BOOLEAN` | `Boolean` | YES | DEFAULT `false` — có phải kết quả ads |
| `tag_ranking` | `INTEGER` | `Integer` | YES | Vị trí xuất hiện trong search |
| `url` | `TEXT` | `Text` | YES | URL listing |
| `import_date` | `DATE` | `Date` | YES | Ngày crawl |
| `importer` | `VARCHAR(32)` | `String(32)` | YES | Source crawl |
| `updated_at` | `TIMESTAMPTZ` | `DateTime(tz=True)` | YES | DEFAULT `now()` |

---

## `listings`

Master list các Etsy listing đang được theo dõi trong hệ thống.

| Column | PG Type | SQLAlchemy | Nullable | Ghi chú |
|---|---|---|---|---|
| `id` | `SERIAL` | `Integer` | NOT NULL | Primary key, auto-increment |
| `listing_id` | `VARCHAR(32)` | `String(32)` | NOT NULL | Etsy listing ID — **UNIQUE** |
| `title` | `TEXT` | `Text` | YES | Tiêu đề listing |
| `category` | `VARCHAR(64)` | `String(64)` | YES | Danh mục sản phẩm |
| `no_vm` | `VARCHAR(16)` | `String(16)` | YES | Mã VM quản lý (VM01, VM08…) |
| `url` | `TEXT` | `Text` | YES | URL Etsy listing |
| `import_time` | `TIMESTAMPTZ` | `DateTime(tz=True)` | YES | DEFAULT `now()` |
| `importer` | `VARCHAR(64)` | `String(64)` | YES | Source import (getify_bot, manual…) |

---

### `listings_int_ext`

Materialized overview — 1 row per `(listing_id, period)` cho period range mới nhất. **Internal indicators only** — các trường external (price, rating, badge, …) KHÔNG materialize ở đây, được join từ `etsy_market_db.market_listing` tại runtime trong `get_dashboard_listings()`.

| Column | PG Type | Nullable | Ghi chú |
|---|---|---|---|
| `listing_id` | `VARCHAR(32)` | NOT NULL | PK (composite) |
| `period` | `VARCHAR(32)` | NOT NULL | PK — chỉ chứa period range `YYYY-MM-DD/YYYY-MM-DD` |
| `reference_date` | `TIMESTAMPTZ` | YES | MAX(import_time) của raw rows được gộp |
| `title` | `TEXT` | YES | COALESCE từ raw + `listings.title` |
| `no_vm` | `VARCHAR(16)` | YES | |
| `product` | `VARCHAR(64)` | YES | |
| `url` | `TEXT` | YES | COALESCE từ `listings.url` hoặc fallback `https://www.etsy.com/listing/{id}` |
| `views`, `clicks`, `orders` | INT | YES | MAX per metric từ raw rows |
| `revenue`, `spend`, `roas` | NUMERIC | YES | MAX per metric |
| `ctr`, `cr` | NUMERIC(6,2) | YES | Tính từ MAX-ed metric ở trên |
| `cpc`, `cpp` | NUMERIC(10,2) | YES | `spend/clicks` và `spend/orders`, NULL nếu mẫu số = 0 |
| `roas_band` | VARCHAR(16) | YES | `no_sales` / `slight_loss` / `profitable` / `heavy_loss` |
| `cr_level`, `ctr_level` | VARCHAR(8) | YES | `high` / `low` (cr cũng có `zero`) |
| `scenario_action` | TEXT | YES | Từ `scenarios_rules.action` JOIN bằng band/level |
| `scenario_label`, `scenario_cause` | TEXT | YES | Tương tự |
| `scenario_fix_listing`, `scenario_fix_ads` | TEXT | YES | |
| `rebuilt_at` | TIMESTAMPTZ | NOT NULL | DEFAULT `now()` — thời điểm rebuild |

> **Primary key:** `(listing_id, period)`. TRUNCATE + bulk INSERT mỗi rebuild.

---

### `listings_int_hist`

Materialized history — daily rows (period dạng `YYYY-MM-DD`) cho mỗi listing.

| Column | PG Type | Nullable | Ghi chú |
|---|---|---|---|
| `listing_id` | `VARCHAR(32)` | NOT NULL | PK |
| `period` | `VARCHAR(32)` | NOT NULL | PK — chỉ chứa daily `YYYY-MM-DD` |
| `reference_date` | `TIMESTAMPTZ` | YES | MAX(import_time) |
| `views`, `clicks`, `orders` | INT | YES | MAX per metric |
| `revenue`, `spend`, `roas` | NUMERIC | YES | MAX per metric |
| `cpc`, `cpp` | NUMERIC(10,2) | YES | Tính sau dedup |
| `source` | VARCHAR(16) | YES | `spy` hoặc `manual` — ưu tiên `manual` khi conflict |
| `rebuilt_at` | TIMESTAMPTZ | NOT NULL | DEFAULT `now()` |

> Index: `idx_listings_int_hist_listing (listing_id)` cho LATERAL JOIN khi serving.

---

### `keywords`

Materialized keyword report — chỉ giữ latest period per listing.

| Column | PG Type | Nullable | Ghi chú |
|---|---|---|---|
| `listing_id` | `VARCHAR(32)` | NOT NULL | PK |
| `keyword` | `TEXT` | NOT NULL | PK |
| `period` | `VARCHAR(32)` | NOT NULL | PK — period range của latest report |
| `currently_status` | VARCHAR(8) | YES | Map từ raw `relevant`: `on` / `off` / null |
| `views`, `clicks`, `orders` | INT | YES | MAX per metric |
| `revenue`, `spend`, `roas` | NUMERIC | YES | MAX per metric |
| `click_rate` | VARCHAR(8) | YES | CTR dạng chuỗi giữ nguyên từ raw |
| `cpc`, `cpp` | NUMERIC(10,2) | YES | Tính sau dedup |
| `rebuilt_at` | TIMESTAMPTZ | NOT NULL | DEFAULT `now()` |

> Index: `idx_keywords_listing (listing_id)`.

---

### `refresh_state`

Singleton tracker (CHECK `id = 1`) lưu trạng thái lần rebuild reporting gần nhất.

| Column | PG Type | Nullable | Ghi chú |
|---|---|---|---|
| `id` | INT | PK | CHECK `= 1` — đảm bảo singleton |
| `last_refresh_at` | TIMESTAMPTZ | YES | Thời điểm rebuild thành công gần nhất |
| `ingest_signature` | TEXT | YES | sha256(MAX(import_time) các bảng raw), truncate 16 ký tự đầu |
| `duration_ms` | INT | YES | Thời gian rebuild |
| `row_counts` | JSONB | YES | `{"ext": N, "hist": N, "keywords": N}` — số row mỗi bảng reporting sau rebuild |



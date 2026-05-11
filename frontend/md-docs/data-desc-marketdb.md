# Data Modeling — Market DB (`etsy_market_db`)

> Database: Neon PostgreSQL · Schema: `public` · Cập nhật: 2026-05-06

---

## Tổng quan

| Bảng | Mô tả |
|---|---|
| `market_listing` | Snapshot listing đối thủ crawl từ Etsy search |
| `market_listing_details` | Chi tiết sâu của listing đối thủ (giá, ship, AI summary) |
| `market_listing_reviews` | Reviews của listing đối thủ |
| `market_shop` | Thông tin shop đối thủ |
| `keyword_rank_snapshot` | Lịch sử rank của listing theo keyword tại từng thời điểm crawl |

---

## `market_listing`

Snapshot listing đối thủ crawl từ kết quả Etsy search. Mỗi `listing_id` là một record duy nhất (upsert theo lần crawl mới nhất).

| Column | PG Type | Nullable | Ghi chú |
|---|---|---|---|
| `listing_id` | `BIGINT` | NOT NULL | Primary key — Etsy listing ID |
| `keyword` | `TEXT` | YES | Keyword tìm kiếm khi crawl ra listing này |
| `title` | `TEXT` | YES | Tiêu đề listing |
| `price` | `NUMERIC(12,2)` | YES | Giá hiển thị (USD) |
| `currency` | `CHAR(3)` | YES | Đơn vị tiền tệ (VD: `USD`) |
| `shop_name` | `VARCHAR(200)` | YES | Tên shop |
| `rating` | `NUMERIC(3,1)` | YES | Rating trung bình (0.0–5.0) |
| `review_count` | `INTEGER` | YES | Số lượng review |
| `badge` | `VARCHAR(50)` | YES | `"Star Seller"`, `"Bestseller"`… |
| `discount` | `SMALLINT` | YES | % giảm giá |
| `free_shipping` | `BOOLEAN` | YES | Có free shipping |
| `is_ad` | `BOOLEAN` | YES | Kết quả là quảng cáo hay organic |
| `tag_ranking` | `SMALLINT` | YES | Vị trí xuất hiện trong trang search |
| `url` | `TEXT` | YES | URL listing |
| `image_url` | `TEXT` | YES | URL ảnh thumbnail |
| `source_url` | `TEXT` | YES | URL trang search đã crawl |
| `crawled_at` | `TIMESTAMPTZ` | YES | Thời điểm crawl |

---

## `market_listing_details`

Chi tiết sâu của listing đối thủ, crawl từ trang listing trực tiếp. Quan hệ 1-1 với `market_listing`.

| Column | PG Type | Nullable | Ghi chú |
|---|---|---|---|
| `listing_id` | `BIGINT` | NOT NULL | Primary key — FK → `market_listing.listing_id` |
| `product_name` | `TEXT` | YES | Tên sản phẩm rút gọn |
| `design` | `TEXT` | YES | Mô tả design / kiểu sản phẩm |
| `base_price` | `NUMERIC(12,2)` | YES | Giá gốc (trước sale, USD) |
| `sale_price` | `NUMERIC(12,2)` | YES | Giá sale (USD) |
| `discount_percent` | `SMALLINT` | YES | % giảm giá |
| `currency` | `CHAR(3)` | YES | Đơn vị tiền tệ |
| `materials` | `TEXT` | YES | Chất liệu sản phẩm |
| `highlights` | `TEXT` | YES | Điểm nổi bật (Handmade, Made to order…) |
| `shipping_status` | `VARCHAR(100)` | YES | Mô tả trạng thái ship |
| `origin_ship_from` | `VARCHAR(100)` | YES | Địa điểm ship từ |
| `ship_time_max_days` | `SMALLINT` | YES | Thời gian ship tối đa (ngày) |
| `us_shipping` | `BOOLEAN` | YES | Có ship nội địa US |
| `return_policy` | `BOOLEAN` | YES | Có chính sách đổi trả |
| `ai_summary` | `TEXT` | YES | AI-generated summary phân tích listing |
| `crawled_at` | `TIMESTAMPTZ` | YES | Thời điểm crawl |

---

## `market_listing_reviews`

Reviews của listing đối thủ. Nhiều reviews cho một listing.

| Column | PG Type | Nullable | Ghi chú |
|---|---|---|---|
| `id` | `SERIAL` | NOT NULL | Primary key, auto-increment |
| `listing_id` | `BIGINT` | YES | FK → `market_listing.listing_id` |
| `reviewer` | `VARCHAR(100)` | YES | Tên người review |
| `review_date` | `DATE` | YES | Ngày review |
| `stars` | `SMALLINT` | YES | Số sao (1–5) |
| `content` | `TEXT` | YES | Nội dung review |
| `crawled_at` | `TIMESTAMPTZ` | YES | Thời điểm crawl |

---

## `market_shop`

Thông tin shop đối thủ. Primary key là `shop_name`.

| Column | PG Type | Nullable | Ghi chú |
|---|---|---|---|
| `shop_name` | `VARCHAR(200)` | NOT NULL | Primary key |
| `owner_name` | `VARCHAR(100)` | YES | Tên chủ shop |
| `location` | `VARCHAR(200)` | YES | Địa điểm shop |
| `join_year` | `SMALLINT` | YES | Năm gia nhập Etsy |
| `total_sales` | `INTEGER` | YES | Tổng số đơn hàng |
| `shop_rating` | `NUMERIC(3,1)` | YES | Rating shop (0.0–5.0) |
| `badge` | `VARCHAR(50)` | YES | `"Star Seller"`… |
| `smooth_shipping` | `BOOLEAN` | YES | Badge ship đúng hẹn |
| `speedy_replies` | `BOOLEAN` | YES | Badge phản hồi nhanh |
| `last_crawled_at` | `TIMESTAMPTZ` | YES | Thời điểm crawl gần nhất |

---

## `keyword_rank_snapshot`

Lịch sử vị trí rank của từng listing theo keyword tại mỗi thời điểm crawl. Append-only — không upsert.

| Column | PG Type | Nullable | Ghi chú |
|---|---|---|---|
| `id` | `BIGSERIAL` | NOT NULL | Primary key, auto-increment |
| `keyword` | `TEXT` | NOT NULL | Keyword tìm kiếm |
| `listing_id` | `BIGINT` | NOT NULL | Etsy listing ID |
| `rank` | `SMALLINT` | NOT NULL | Vị trí xuất hiện trong kết quả search |
| `badge` | `VARCHAR(50)` | YES | Badge tại thời điểm crawl |
| `product` | `TEXT` | YES | Loại sản phẩm |
| `crawled_at` | `TIMESTAMPTZ` | NOT NULL | Thời điểm crawl — dùng để track trend rank theo thời gian |

> **Append-only:** Mỗi lần crawl tạo row mới, không overwrite. Query trend dùng `GROUP BY keyword, listing_id ORDER BY crawled_at`.

---

## Quan hệ giữa các bảng

```
market_listing (listing_id)
    ├── market_listing_details (listing_id)   1-1
    ├── market_listing_reviews (listing_id)   1-N
    └── keyword_rank_snapshot (listing_id)    1-N (append-only)

market_shop (shop_name)
    └── market_listing (shop_name)            1-N  [không có FK constraint]
```

---

## Quan hệ với Internal DB

`market_listing.listing_id` được JOIN với `references_engine.reference_listing_id` và `listings.listing_id` trong Internal DB để hiển thị dữ liệu đối thủ tham chiếu trên Performance Hub.

---

## Quy ước chung

| Quy ước | Giá trị |
|---|---|
| Timestamp timezone | Luôn dùng `TIMESTAMPTZ` (UTC) |
| Listing ID | `BIGINT` — Etsy listing ID là số nguyên lớn |
| Giá tiền | `NUMERIC(12,2)` = USD thực · `SMALLINT` = % discount |
| Rating | `NUMERIC(3,1)` — một chữ số thập phân (VD: `4.8`) |
| `keyword_rank_snapshot` | Append-only, không update |

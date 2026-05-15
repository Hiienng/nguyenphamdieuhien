# Data Flow Handbook — EtseeMate SaaS
> Architect_master đọc file này khi review hạ tầng hàng tuần và khi thiết kế tính năng mới.
> Mục tiêu: Từ 1 seller pilot → 100 sellers trả tiền → scalable đến 1000 sellers.
> Stack hiện tại: FastAPI · PostgreSQL (Neon) · Render.com · ImageKit · Claude/Gemini API

---

## Nguyên tắc cốt lõi

EtseeMate là **analytics SaaS** — không phải e-commerce. Dữ liệu chủ yếu là:
- **Write-light:** Seller upload báo cáo Etsy Ads (OCR) 1-2 lần/tuần
- **Read-heavy:** Dashboard, keyword report, scenario recommendation truy vấn liên tục
- **Crawler batch:** market_listing crawl weekly từ Mac local, không realtime

→ Không cần Kafka, Flink, hay stream processing. PostgreSQL + Materialized Views + caching đúng chỗ là đủ đến 1000 sellers.

---

## Threshold Table — Dùng pattern nào, ở mốc nào

| Pattern | Áp dụng khi | EtseeMate hiện tại | Ưu tiên |
|---|---|---|---|
| **Materialized Views** | Ngay từ đầu | ✅ Có (`listings_int_ext`, `keywords`) | Done |
| **PostgreSQL RLS** | Trước user đầu tiên trả tiền | ❌ Chưa có | 🔴 Sprint tới |
| **tenant_id trên mọi bảng** | Trước user đầu tiên trả tiền | ❌ Chưa có | 🔴 Sprint tới |
| **IDOR protection** | Ngay từ đầu | ❌ Chưa có | 🔴 Sprint tới |
| **Soft-delete** | Ngay từ đầu | ❌ Chưa có | 🟡 Sprint 2 |
| **Index theo seller_id** | Khi có 2+ sellers | ❌ Chưa có | 🟡 Sprint 2 |
| **Pagination bắt buộc** | Khi list API > 100 rows | ⚠️ Một số route thiếu | 🟡 Sprint 2 |
| **Auth JWT + HttpOnly Cookie** | Trước launch public | ❌ Chưa có auth | 🔴 Sprint tới |
| **Rate Limiting** | Khi public | ❌ Chưa có | 🟡 Sprint 2 |
| **Redis Cache** | Khi p95 latency > 500ms | Chưa cần | 🔵 Defer → 50+ sellers |
| **Read replica** | Khi concurrent read > 30/s | Chưa cần | 🔵 Defer → 100+ sellers |
| **Kafka / Message Queue** | Khi concurrent write > 50/s | Chưa cần | 🔵 Defer → 500+ sellers |
| **ClickHouse / BigQuery** | Khi report query > 2s thường xuyên | Chưa cần | 🔵 Defer → 500+ sellers |
| **Kubernetes / Auto-scaling** | Khi traffic unpredictable | Chưa cần | 🔵 Defer → 1000+ sellers |

---

## Kiến trúc Data Flow theo giai đoạn

### Giai đoạn 1 — Hiện tại → 20 sellers (Render Free + Neon Free)

```
Seller Browser
    │
    ▼
FastAPI (Render) ──── PostgreSQL Neon (internal DB)
    │                      ├── listings, import_batch
    │                      ├── listings_int_ext (materialized)
    │                      ├── keywords (materialized)
    │                      └── crawl_run, crawl_queue
    │
    ├── Claude/Gemini API (OCR + AI optimize)
    ├── ImageKit (screenshot storage)
    │
    └── PostgreSQL Neon (market DB, read-only)
             └── market_listing (crawled weekly từ Mac local)
```

**Bottleneck cần xử lý trước khi có user 2:**
- Không có auth → bất kỳ ai cũng truy cập được API
- Không có tenant isolation → data của seller A lộ ra seller B nếu query sai
- Không có soft-delete → xóa là mất vĩnh viễn

### Giai đoạn 2 — 20 → 100 sellers (Render Starter ~$7/tháng)

Thêm vào kiến trúc hiện tại:
- **Auth layer:** JWT + HttpOnly Cookie refresh token
- **tenant_id:** Add column vào tất cả bảng user data
- **RLS:** PostgreSQL Row-Level Security enforce tại DB layer
- **Index:** Composite index `(tenant_id, listing_id)`, `(tenant_id, period)`
- **Rate limiting:** FastAPI middleware giới hạn theo IP/token
- **Cloudflare Free:** WAF + DDoS protection đặt trước Render

```
Seller Browser
    │
    ▼
Cloudflare (WAF + Rate Limit miễn phí)
    │
    ▼
FastAPI + Auth Middleware (JWT verify → inject tenant_id vào request context)
    │
    ▼
PostgreSQL Neon + RLS (mọi query tự filter WHERE tenant_id = :current)
```

**Chi phí:** Render Starter $7/tháng. Neon Free đủ đến ~100 sellers (~0.5GB).

### Giai đoạn 3 — 100 → 1000 sellers

Thêm vào khi có tín hiệu cụ thể:

| Tín hiệu | Hành động |
|---|---|
| p95 API latency > 500ms | Thêm Redis cache cho market_listing + threshold_configs |
| Report query > 2s | Tạo dedicated read replica trên Neon |
| Neon storage > 400MB | Upgrade Neon Launch ($19/tháng) |
| OCR queue > 10 jobs đồng thời | Thêm background task queue (Celery + Redis) |
| Crawler cần chạy nhiều keyword hơn | Scale Mac crawler, không thay đổi backend |

---

## Luồng dữ liệu đặc thù của EtseeMate

### Luồng 1 — Import báo cáo Etsy Ads (Write path)
```
Seller upload screenshot PNG/XLSX
    → ImageKit lưu file (URL trả về)
    → import_batch tạo record (status: uploaded)
    → OCR extract (Claude Vision / Gemini)
    → Preview data lưu vào import_batch.preview_data (JSONB)
    → Seller confirm → merge vào manual_listing_report / manual_keyword_report
    → reporting_etl.rebuild_reporting() tái tạo listings_int_ext + keywords
    → crawl_queue enqueue listing_ids mới cho internal crawler
```

**Idempotency quan trọng:** Import cùng 1 file 2 lần phải không tạo duplicate. Dùng `ingest_signature` (sha256) đã có trong `refresh_state`.

### Luồng 2 — Dashboard read (Read path)
```
Seller mở Performance Hub
    → GET /api/v1/performance/listings
    → Query listings_int_ext (đã materialized, không join runtime)
    → JOIN market_listing (read-only, market DB)
    → Trả về JSON, FE render
```

**Không được:** Query `listing_report` + `manual_listing_report` trực tiếp khi render dashboard → quá chậm khi có nhiều period.

### Luồng 3 — Market crawl (Background, Mac local)
```
Mac local (24/7) chạy launchd schedule
    → market_batch_scraper.py crawl Etsy
    → Ghi vào market_listing (ETSY_MARKET_DB, Neon riêng)
    → Ghi crawl_run log vào internal DB
    → references_service.refresh() backfill product_type
```

**Không thay đổi kiến trúc này đến 1000+ sellers.** Mac local + Chrome CDP là moat kỹ thuật, không expose ra cloud.

---

## Rules thiết kế — áp dụng cho mọi feature mới

1. **Không xử lý aggregation tại runtime** — mọi SUM/COUNT/AVG phải có trong materialized view hoặc pre-computed column
2. **Mọi API list endpoint bắt buộc có pagination** — default 50, max 200
3. **FE không được gửi seller_id lên API** — backend inject từ JWT token
4. **Mọi bảng user data phải có tenant_id** — kể từ sprint multi-tenant
5. **Không hardcode connection string** — đọc từ env var qua `get_settings()`
6. **Crawler Mac không kết nối internal DB trực tiếp** — chỉ ghi vào market DB riêng

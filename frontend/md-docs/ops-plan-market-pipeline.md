# Ops Plan — Market Crawl, Internal Market Sweep, Product Type Tagging

> Cập nhật: 2026-05-11 · Scope: 3 luồng tự động hoá còn thiếu sau khi reporting layer đã ổn định

---

## Bức tranh tổng

```
                    ┌──────────────────────────────────────┐
                    │  Master list: `listings`             │
                    │  (internal_listing_id + url + title) │
                    └────────────┬─────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        ▼                        ▼                        ▼
  [Flow 1]                 [Flow 2]                 [Flow 3]
  Market discovery         Sweep market data        Product type tagging
  crawl by keyword         cho từng internal_id     từ title (LLM/regex)
        │                        │                        │
        ▼                        ▼                        ▼
  market_listing*          market_listing           listings.product_type
  market_shop              (own rows: id == listing_id)   listings_int_ext.product
  keyword_rank_snapshot    market_listing_details
```

3 luồng hiện tại đã có **crawler script** nhưng chưa có **orchestration**: chạy thủ công, không schedule, không retry, không quan sát được trên FE.

---

## Trạng thái hiện tại

| Component | Có sẵn | Thiếu |
|---|---|---|
| `market_batch_scraper.py` — crawl theo keyword từ JSON file | ✅ | Chưa có cron, chưa wire vào DB job-queue, chỉ chạy local CLI |
| `internal_listing_crawler.py` — crawl detail cho từng internal listing | ✅ | Chưa schedule định kỳ, chưa enqueue khi `listings` thêm row mới |
| `keyword_rank_crawler.py` — crawl rank của keyword | ✅ | Chưa wire vào ETL, dữ liệu vào `keyword_rank_snapshot` nhưng không ai dùng |
| Product type tagger | ❌ | Chưa tồn tại — `product_type` chỉ có ở `listing_extense` và `references_engine` (crawl ra), chưa gán cho `listings` của ta |
| Crawler ↔ backend integration | ❌ | Crawler đang chạy độc lập với FastAPI service, không trigger được từ FE |
| Observability | ❌ | Không có bảng `crawl_run` / `crawl_job` để theo dõi |

---

## Mục tiêu

1. **Flow 1 — Market discovery**: lịch hàng tuần tự động crawl thị trường theo danh sách keyword đang theo dõi (VM01 + mở rộng). Output đi vào `market_listing*` để Research Hub và Listing Improvement có data tươi.
2. **Flow 2 — Internal market sweep**: mỗi khi có internal listing mới (thêm vào `listings`), tự enqueue crawl 1 lần detail. Định kỳ refresh giá / discount / rating (1×/tuần).
3. **Flow 3 — Product type tagging**: gán nhãn `product_type` cho mỗi internal listing dựa vào `title` (+ optional `category`). Lưu vào `listings.product_type` (cột mới). Trigger sau crawl Flow 2 hoặc khi listing được thêm.
4. **Quan sát**: 1 bảng `crawl_run` để dashboard show status, last run, success/fail count.

---

## Kiến trúc đề xuất

### Lựa chọn job runner

| Phương án | Pros | Cons | Khuyến nghị |
|---|---|---|---|
| **A. APScheduler + FastAPI lifespan** | Đơn giản, nằm trong cùng process backend, không cần infra mới | Crawler dùng real Chrome qua CDP → blocking, có thể chiếm slot uvicorn → nên chạy ở subprocess, không in-process | OK cho MVP nếu Chrome chạy ở subprocess riêng |
| **B. Render Cron Job** (riêng service `etsy-pilot-cron`) | Tách hẳn workload, không ảnh hưởng API; render.yaml hỗ trợ native | Cần config service thứ 2, billing thêm | ✅ **Khuyến nghị** — sạch nhất cho production |
| **C. Self-hosted (local Mac cron + tunnel)** | Tận dụng máy local — vốn đang chạy crawler thủ công | Không HA, máy tắt = pipeline dừng | Không khuyến nghị production, dùng tạm bridge nếu chưa ready Render Cron |

**Quyết định:** chọn **B** cho production, A cho dev (hoặc khi cần dispatch on-demand từ FE).

### Bảng mới đề xuất

```sql
-- Job ledger: mỗi lần job chạy ghi 1 row
CREATE TABLE crawl_run (
    id            SERIAL PRIMARY KEY,
    job_name      VARCHAR(64) NOT NULL,    -- 'market_discovery' | 'internal_sweep' | 'product_type_tag' | 'keyword_rank'
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    status        VARCHAR(16) NOT NULL DEFAULT 'running',  -- running | success | partial | failed
    target_count  INTEGER,                  -- bao nhiêu item đầu vào (keyword/listing)
    success_count INTEGER,
    fail_count    INTEGER,
    error_summary TEXT,
    metadata      JSONB                     -- {checkpoint_path, vm_code, ...}
);
CREATE INDEX idx_crawl_run_job_name ON crawl_run (job_name, started_at DESC);

-- Queue cho internal listings cần crawl/refresh (Flow 2)
CREATE TABLE crawl_queue (
    listing_id   VARCHAR(32) PRIMARY KEY,
    queued_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempt TIMESTAMPTZ,
    attempts     INTEGER NOT NULL DEFAULT 0,
    next_after   TIMESTAMPTZ DEFAULT now(), -- exponential backoff
    reason       VARCHAR(32),                -- 'new_listing' | 'periodic_refresh' | 'manual'
    status       VARCHAR(16) NOT NULL DEFAULT 'pending' -- pending | done | failed
);
CREATE INDEX idx_crawl_queue_status_next ON crawl_queue (status, next_after);

-- Thêm cột product_type cho listings (Flow 3)
ALTER TABLE listings ADD COLUMN IF NOT EXISTS product_type VARCHAR(64);
ALTER TABLE listings ADD COLUMN IF NOT EXISTS product_type_source VARCHAR(16); -- 'llm' | 'rule' | 'manual'
ALTER TABLE listings ADD COLUMN IF NOT EXISTS product_type_tagged_at TIMESTAMPTZ;
```

---

## Flow 1 — Market discovery (keyword-driven)

**Input:** danh sách keywords (file `vm01_keywords.json` hiện tại, sau này read từ bảng `market_keywords`).
**Output:** rows vào `market_listing`, `market_listing_details`, `market_listing_reviews`, `market_shop`, `keyword_rank_snapshot`.

### Schedule
- **Production:** Render Cron `0 2 * * 1` (mỗi thứ Hai 02:00 UTC) — chạy `market_batch_scraper.py --auto`.
- Mỗi run tối đa 30 keywords (~2-3 giờ). Quá thì chia 2 cron khác nhau (Mon/Thu).

### Implement
1. Thêm CLI flag `--write-run-ledger` vào `market_batch_scraper.py`:
   - Tạo `INSERT INTO crawl_run (job_name='market_discovery', target_count=N)`, lưu `run_id`.
   - Khi finish: `UPDATE crawl_run SET finished_at, status, success_count, fail_count, error_summary WHERE id=:run_id`.
2. Render service mới `etsy-pilot-cron-market`:
   ```yaml
   - type: cron
     name: etsy-pilot-cron-market
     schedule: "0 2 * * 1"
     buildCommand: pip install -r market_engine_crawler/requirements.txt
     startCommand: python3 market_engine_crawler/market_batch_scraper.py --auto 30 --write-run-ledger
   ```
3. FE: thêm card "Market crawler" ở góc dashboard, GET `/api/v1/ops/crawl-runs?job=market_discovery&limit=5`.

### Risk
- Chrome CDP cần real browser — Render Cron worker chưa chắc support headed Chrome. **Fallback:** chạy Playwright headless với stealth plugin; nếu CAPTCHA → flag run là `partial` để team xử lý manual.

---

## Flow 2 — Internal market sweep (listing-driven)

Mỗi internal listing nên có 1 row tương ứng trong `market_listing` (cùng `listing_id`) để Listing Improvement enrich price/rating. Hiện tại pipeline serving đang LEFT JOIN `market_listing WHERE listing_id = ANY(...)` — nếu không có thì price/rating đều null.

### Trigger
1. **Sự kiện:** khi có row mới insert vào `listings` (từ `/internal/confirm` hoặc seed) → enqueue vào `crawl_queue` với `reason='new_listing'`.
2. **Định kỳ:** Cron daily — chọn tất cả listing có `last_attempt > 7 days ago OR last_attempt IS NULL`, set lại `next_after=now()`.

### Worker
- Cron mỗi 30 phút (`*/30 * * * *`): pop tối đa 20 listings từ `crawl_queue WHERE status='pending' AND next_after <= now() ORDER BY queued_at`.
- Chạy `internal_listing_crawler.py` với list các URL → upsert vào `market_listing` (own rows) + `market_listing_details`.
- Update queue: success → `status='done'`; fail → `attempts +=1`, `next_after = now() + interval '1 hour' * 2^attempts` (backoff exponential).

### Implement
1. Thêm hook ở `internal_service.confirm_import`: sau khi insert listings mới → `INSERT INTO crawl_queue (listing_id, reason) ... ON CONFLICT DO NOTHING`.
2. Modify `internal_listing_crawler.py`: accept `--from-queue` flag → đọc queue thay vì full `listings`.
3. Render Cron service `etsy-pilot-cron-internal-sweep`, schedule `*/30 * * * *`.

### Hiệu ứng phụ tốt
Sau Flow 2, mọi internal listing đều có market_listing row → FE Listing Improvement bỏ được tình trạng price/rating null.

---

## Flow 3 — Product type tagging

**Mục tiêu:** mỗi internal listing có `product_type` rõ ràng (vd: `"baby blanket"`, `"baby onesie"`, `"phone case"`) để filter / group ở FE và để map references đúng.

### Cách tiếp cận

| Approach | Pros | Cons | Khuyến nghị |
|---|---|---|---|
| **A. Regex/keyword rule list** (whitelist) | Free, deterministic | Maintenance cao, miss case lạ | Dùng làm fallback layer |
| **B. LLM 1-shot (Gemini/Haiku)** với prompt + danh sách product_type cho phép | Cover được edge case, chính xác cao | Cost ~$0.001/listing, latency 1-2s, không deterministic | ✅ Primary |
| **C. Embedding + nearest-neighbor** dùng từ `model/src/embeddings/` | Re-use infra có sẵn | Cần thư viện product_type vector trước | Phase 2 |

**Quyết định:** **A + B kết hợp** — rule match trước (95% case), LLM cho phần còn lại.

### Triển khai

1. **Tạo từ điển `product_type_dict`:**
   ```sql
   CREATE TABLE product_type_dict (
       product_type VARCHAR(64) PRIMARY KEY,  -- 'baby blanket'
       aliases      TEXT[],                    -- {'baby quilt', 'newborn blanket', ...}
       enabled      BOOLEAN DEFAULT true
   );
   ```
   Seed từ `listing_extense.product_type` distinct + curate tay.

2. **Service mới `backend/app/services/product_type_tagger.py`:**
   ```python
   async def tag_listing(listing_id, title, category, db) -> dict:
       # 1. Rule match: lowercase title, kiểm tra alias nào xuất hiện
       # 2. Fallback LLM: prompt Gemini với danh sách product_type cho phép
       # 3. UPDATE listings SET product_type=..., product_type_source=..., product_type_tagged_at=now()
       return {"product_type": ..., "source": "rule|llm"}
   ```

3. **Trigger:**
   - Khi `crawl_queue.status='done'` (Flow 2 finish) → tag ngay sau khi có `market_listing.title`.
   - Cron daily quét `listings WHERE product_type IS NULL` để bắt sót.
   - FE bổ sung nút "Re-tag" trong card detail listing.

4. **Wire vào reporting:** `listings_int_ext.product` đang lấy `COALESCE(e.product, l.category)`. Đổi thành `COALESCE(l.product_type, e.product, l.category)` → product_type ưu tiên cao nhất.

---

## Quan sát (Observability)

### Bảng `crawl_run` — đã đề xuất ở trên

### FE component đề xuất
Thêm tab "Operations" hoặc card góc dashboard hiển thị:
- Last run mỗi job (3 luồng) + status badge + duration
- Queue depth: `SELECT count(*) FROM crawl_queue WHERE status='pending'`
- Coverage: `% listings có product_type`, `% listings có market_listing row`
- Manual trigger button → `POST /api/v1/ops/trigger?job=...` (chỉ admin)

### Endpoint mới (`backend/app/api/routes/ops.py`)
```
GET  /api/v1/ops/health         → tổng quan health của 3 luồng
GET  /api/v1/ops/crawl-runs     → list runs (filter by job_name, paginate)
POST /api/v1/ops/trigger        → dispatch job ad-hoc (auth required)
POST /api/v1/ops/queue/enqueue  → manual add listing_id vào queue
```

---

## Lộ trình triển khai

| Phase | Scope | Time | Output |
|---|---|---|---|
| **P0 — Infra base** (1 ngày) | DDL `crawl_run`, `crawl_queue`, `product_type_dict`, ALTER `listings`. Endpoint `/ops/health`, `/ops/crawl-runs`. FE card observability đơn giản. | 1 ngày | Visible quan sát, không cần job mới chạy thật |
| **P1 — Flow 2** (2-3 ngày) | Wire enqueue ở `/internal/confirm`. Modify `internal_listing_crawler.py --from-queue`. Render Cron 30-min. | 2-3 ngày | Internal market data auto-fresh; CPC/price không còn null |
| **P2 — Flow 3** (2 ngày) | `product_type_dict` seed + tagger service. Update `listings_int_ext` SQL. FE filter product_type chuẩn. | 2 ngày | Listing có product_type rõ → references_engine map tốt hơn |
| **P3 — Flow 1** (3-5 ngày) | Migrate `market_batch_scraper` lên Render Cron, integrate `crawl_run`. Đánh giá khả thi headless. | 3-5 ngày | Market discovery tự động, không cần chạy local |
| **P4 — Polish** (1-2 ngày) | Manual trigger UI, alerting (Slack webhook khi run failed), partial-success handling | 1-2 ngày | Production-grade |

Tổng ước lượng: **10-13 ngày developer thời gian** (chia thành 5 PR theo phase).

---

## Risks & open questions

1. **Render Cron + real Chrome:** Render không support headed browser. Cần migrate sang Playwright headless hoặc thuê service crawler bên ngoài (Bright Data, Apify). **Spike P3 trước khi commit.**
2. **CAPTCHA:** Etsy có CAPTCHA. Hiện tại `market_batch_scraper.py` có cơ chế pause cho human. Khi auto trên cron → cần dùng CAPTCHA-solving service hoặc residential proxy.
3. **Gemini cost cho Flow 3:** ~1000 listings × $0.001 = $1/lần re-tag full. Rule layer hạ xuống <50 listings cần LLM → <$0.05/lần. OK.
4. **Product type taxonomy:** danh sách `product_type` cố định hay mở rộng? Phase 2 cân nhắc gom dictionary từ `listing_extense` + curate.
5. **Idempotency:** Flow 1 crawl trùng keyword → upsert vào `market_listing` bằng `ON CONFLICT (listing_id) DO UPDATE`. Cần check schema hiện có constraint chưa.

---

## Quyết định cần user

1. Chọn job runner: Render Cron (B) — confirm OK?
2. Có quota để add 2-3 Render Cron service mới không?
3. Có sẵn Gemini API key cho Flow 3 chưa? (đã thấy `GEMINI_API_KEY` trong render.yaml — OK)
4. Phase nào ưu tiên triển khai trước? Mình đề xuất P0 → P2 → P1 → P3 (giá trị visible nhanh nhất: observability + product_type).

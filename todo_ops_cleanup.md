# Todo — Ops Cleanup
> Feature: Tối ưu operation pipeline — bỏ scheduled EtseeMate crawler + merge ETL vào confirm flow
> Approved: 2026-05-15
> Agents: @backend only (không có FE task)

---

## Backend Tasks

### Task 1 — Bỏ schedule EtseeMate_listing_crawler, chuyển sang queue-driven
- [x] Backend: Xác nhận `crawl_queue` đã được enqueue đúng trong `confirm_import` (kiểm tra `crawler_ops.py`) — `enqueue_listings()` đã có trong crawler_ops.py; đã thêm call vào `confirm_import()` trong EtseeMate_service.py
- [x] Backend: Sửa `EtseeMate_listing_crawler.py` — thêm mode `--queue` poll từ `crawl_queue` thay vì crawl toàn bộ `listings` — thêm `load_from_queue()`, `mark_queue_done()`, `mark_queue_failed()`, flag `queue_mode` vào `run()`, và `--queue [N]` entry point
- [x] Backend: Xóa hoặc disable `launchd/com.EtseeMate.crawler.EtseeMate.plist` (comment out StartInterval, giữ file để tham khảo)
- [x] Backend: Cập nhật `SETUP_CRAWLER_MAC.md` — ghi chú EtseeMate crawler không còn chạy theo schedule; thêm section "EtseeMate Crawler — Queue-Driven Mode"

### Task 2 — Merge ETL listings vào confirm_import flow
- [x] Backend: Move logic từ `data/etl/etl_listings.py` vào function `sync_listings_from_report()` trong `backend/app/services/EtseeMate_service.py` — async SQLAlchemy version, UPSERT COALESCE từ manual_listing_report
- [x] Backend: Gọi `sync_listings_from_report()` ngay sau confirm commit trong `confirm_import()` — gọi trước khi enqueue crawl_queue
- [x] Backend: Xóa `.github/workflows/` ETL job nếu có, hoặc disable trigger — đã comment out `schedule` cron trong `.github/workflows/etl-monday.yml`, giữ `workflow_dispatch`
- [ ] Backend: Smoke test: confirm 1 batch → kiểm tra `listings` table có được update ngay không

---

## Frontend Tasks
_Không có task FE cho ops cleanup này._

---

## Acceptance Criteria
- EtseeMate crawler chỉ chạy khi `crawl_queue` có item — không chạy định kỳ
- Sau `confirm_import`, bảng `listings` được sync ngay lập tức, không cần đợi ETL job
- Không còn GitHub Actions ETL job chạy thứ 2
- Không có regression trên confirm import flow hiện tại

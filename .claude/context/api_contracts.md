# API Contracts — EtseeMate `/api/v1`
> Đọc file này khi làm task liên quan đến API: thêm route, bind FE với BE, thiết kế endpoint mới.
> Cập nhật cuối: 2026-05-14 (sync commit 0ff771f)

---

## Listings `/api/v1/listings`
| Method | Path | Mô tả |
|---|---|---|
| GET | `/` | Danh sách listings (query filter) |
| GET | `/{listing_id}` | Chi tiết 1 listing |
| POST | `/` | Tạo listing mới |
| PATCH | `/{listing_id}` | Cập nhật listing |
| DELETE | `/{listing_id}` | Xóa listing |
| GET | `/stats/count` | Tổng số listings |

## Import Pipeline `/api/v1/EtseeMate`
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

## Performance `/api/v1/performance`
| Method | Path | Mô tả |
|---|---|---|
| GET | `/listings` | Dashboard từ `listings_int_ext` (materialized) |
| POST | `/refresh` | Trigger `reporting_etl.rebuild_reporting()` |

**Auth gate:** require active subscription

## Market `/api/v1/market`
| Method | Path | Mô tả |
|---|---|---|
| GET | `/samples` | Sample market listings theo product_type |

## Thresholds `/api/v1/thresholds`
| Method | Path | Mô tả |
|---|---|---|
| GET | `/current` | Config threshold hiện tại |
| GET | `/history` | Lịch sử thay đổi |
| POST | `` | Tạo config mới |

## Scenarios `/api/v1/scenarios`
| Method | Path | Mô tả |
|---|---|---|
| GET | `/rules` | Danh sách scenario rules |
| POST | `/rules` | Tạo rule mới |
| PUT | `/rules/{rule_id}` | Cập nhật rule |
| DELETE | `/rules/{rule_id}` | Xóa rule |

## Intelligence `/api/v1/intelligence`
| Method | Path | Mô tả |
|---|---|---|
| POST | `/thumbnail-knowledge/generate` | Generate knowledge từ badge-filtered market_listing |
| GET | `/thumbnail-knowledge` | List knowledge records, filter `?product_type=` |
| POST | `/thumbnail-eval` | Evaluate 1 ảnh thumbnail (multipart: image + product_type) |

**Auth gate:** `/thumbnail-eval` require credit ≥ 1 (deduct 1 on success)

## References `/api/v1/references`
| Method | Path | Mô tả |
|---|---|---|
| GET | `` | Danh sách references |
| GET | `/{listing_id}` | References của listing |
| POST | `/refresh` | Rebuild references từ market_listing |
| GET | `/product-categories` | Dynamic list of product types từ market_listing (public, no auth) |

## Auth `/api/v1/auth`
| Method | Path | Ghi chú |
|---|---|---|
| POST | `/register` | public |
| POST | `/login` | public |
| POST | `/refresh` | public (refresh cookie) |
| POST | `/logout` | auth required |
| GET | `/me` | auth required → profile + subscription + credit balance + onboarding_completed flag |
| POST | `/onboarding/setup` | auth required — set product_categories + seller_location (initial + one update per 90 days) |

## Billing `/api/v1/billing` (Polar.sh as gateway)
| Method | Path | Ghi chú |
|---|---|---|
| GET | `/plans` | public — plans + topups catalog (with polar_product_id) |
| GET | `/trial-status` | auth — trial active/expired, days remaining |
| GET | `/credits` | auth — `{subscription, topup, total, reset_at, balance(legacy), transactions[]}` |
| GET | `/subscription` | auth — subscription status |
| POST | `/subscribe` | auth — body `{plan: "basic_monthly"}` → `{checkout_url}` (Polar) |
| POST | `/topup` | auth — body `{pack: "topup_5"\|"topup_10"}` → `{checkout_url}` (Polar) |
| POST | `/cancel` | auth — cancel at period end (keeps access + sub credits till period_end) |
| POST | `/deposit` | DEPRECATED → 410 Gone. Use `/topup`. |
| POST | `/webhook` | NO auth — Polar HMAC-SHA256 sig (header `webhook-signature`) |

**Credit-consuming endpoints (Depends(require_credits(1)) + consume_or_refund):**
- POST `/api/v1/intelligence/thumbnail-eval`
- POST `/api/v1/intelligence/thumbnail-knowledge/generate`

Returns **HTTP 402** `{detail: {type: "insufficient_credits", needed, available, message}}` on empty balance.

---

## Backend File Map
```
backend/app/
├── core/
│   ├── config.py        — Settings (lru_cache), env vars
│   └── database.py      — AsyncEngine x2 (EtseeMate + market), get_db()
├── models/              — SQLAlchemy ORM models
├── schemas/
│   └── vision_schema.py — Thumbnail eval schemas
├── api/routes/
│   └── intelligence.py  — /api/v1/intelligence
└── services/
    ├── listing_service.py
    ├── performance_service.py
    ├── EtseeMate_service.py
    ├── EtseeMate_extractor.py  — OCR/extract logic
    ├── reporting_etl.py        — Materialized reporting rebuild + debounce
    ├── references_service.py
    ├── crawler_ops.py          — crawl_run + crawl_queue helpers
    ├── imagekit_service.py     — ImageKit screenshot storage
    ├── vision_service.py       — Thumbnail knowledge + eval
    └── claude_service.py       — Tập trung mọi Claude API call
```

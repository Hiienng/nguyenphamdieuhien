# DB Schema — EtseeMate
> Đọc file này khi làm task liên quan đến database: migration, query, ORM model, reporting ETL.
> Cập nhật cuối: 2026-05-14 (sync commit 0ff771f)

---

## DB Chính (`DATABASE_URL`)

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

### `listings_int_ext` (materialized — rebuilt by `reporting_etl`)
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

### `crawl_run`
| Column | Type | Ghi chú |
|---|---|---|
| id | SERIAL PK | |
| job_name | VARCHAR(64) | market / EtseeMate / rank |
| started_at / finished_at | TIMESTAMPTZ | |
| status | VARCHAR(16) | running / done / failed |
| target_count / success_count / fail_count | INTEGER | |
| error_summary | TEXT | |
| host | VARCHAR(64) | |
| metadata | JSONB | |

### `crawl_queue`
| Column | Type | Ghi chú |
|---|---|---|
| listing_id | VARCHAR(32) PK | |
| queued_at | TIMESTAMPTZ | |
| last_attempt | TIMESTAMPTZ | |
| attempts | INTEGER | |
| next_after | TIMESTAMPTZ | |
| reason | VARCHAR(32) | |
| status | VARCHAR(16) | pending / done / failed |

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

### Auth & Payment Tables (Added 2026-05-14)

**users**: id(UUID PK), email(VARCHAR 255 UNIQUE), password_hash(VARCHAR 255), full_name(VARCHAR 128), is_active(BOOL), is_admin(BOOL), onboarding_completed(BOOL, default=false), product_categories(JSON, default=[]), seller_location(VARCHAR 8 nullable), last_onboarding_update(TIMESTAMPTZ nullable), created_at, updated_at
- **Constraint:** One user per email (UNIQUE)
- **Onboarding:** Can update once after 90 days from created_at
- **product_categories:** Array of strings (e.g., ["onesie", "blanket"]), max 3 items

**subscriptions**: id(UUID PK), user_id(UUID FK), plan(VARCHAR 32), status(VARCHAR 16: active/cancelled/expired), period_start, period_end, stripe_sub_id(VARCHAR 128), created_at

**credit_accounts**: id(UUID PK), user_id(UUID FK UNIQUE), balance(INT, deprecated — kept = subscription+topup), subscription_credits(INT default 0 — monthly refill, expires), topup_credits(INT default 0 — purchased, never expire), subscription_credits_reset_at(TIMESTAMPTZ nullable), updated_at
- **Buckets:** Two pools per user. Deduction order: subscription first, then topup.
- **Trial grant:** 3 credits in subscription bucket, reset_at = trial.period_end (lost on day 8 if unused).
- **Basic plan refill:** subscription bucket reset to 5 each billing cycle (no carry-over).

**credit_transactions**: id(UUID PK), user_id(UUID FK), amount(INT, +grant / -debit), tx_type(VARCHAR 16: trial_grant/subscription_refill/topup_5/topup_10/feature_debit/refund), description(TEXT), stripe_pi_id(VARCHAR 128 — now stores Polar event_id), bucket(VARCHAR 16: subscription/topup), created_at

**payment_records**: id(UUID PK), user_id(UUID FK nullable), stripe_event_id(VARCHAR 128 UNIQUE), event_type(VARCHAR 64), amount_cents(INT), currency(VARCHAR 8), payload(JSONB), processed_at

---

## DB Market (`ETSY_MARKET_DB`) — read-only từ backend

### `market_listing`
| Column | Type | Ghi chú |
|---|---|---|
| listing_id | text | Etsy listing ID |
| keyword | text | `search_tag` trong references |
| url | text | URL trang listing Etsy |
| image_url | text | thumbnail chính |
| title | text | |
| shop_name | text | |
| price | numeric | |
| discount | numeric | |
| rating | numeric | |
| review_count | integer | |
| tag_ranking | integer | thấp = trending cao |
| badge | text | |
| free_shipping | boolean | |
| is_ad | boolean | |
| product_type | text | backfill bởi Gemini |
| crawled_at | timestamptz | |

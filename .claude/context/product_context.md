# Product Context — EtseeMate
> Đọc file này khi cần hiểu bối cảnh sản phẩm, stack, hoặc env vars.
> Cập nhật cuối: 2026-05-14 (sync commit 0ff771f)

---

## Tổng Quan Sản Phẩm

- **EtseeMate** là SaaS B2B cung cấp tool phân tích hiệu suất và optimize listing cho Etsy sellers.
- **ICP:** Etsy seller cá nhân / shop nhỏ đang chạy Etsy Ads.
- **Trạng thái:** Single-tenant pilot — data trong DB là của 1 seller reference account. Đang phát triển hướng multi-tenant.
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

## Frontend

- File chính: `frontend/EtseeMate.html`
- Landing page: `frontend/index.html`
- Design tokens: `docs/DESIGN.md` (CSS vars: `--terracotta`, `--parchment`, ...)
- JS: `frontend/js/`, CSS: `frontend/css/`

## Env Vars

| Var | Dùng cho |
|---|---|
| `DATABASE_URL` | Neon PostgreSQL — EtseeMate data |
| `ETSY_MARKET_DB` | Market data DB |
| `ANTHROPIC_API_KEY` | Claude API |
| `CLAUDE_MODEL` | default `claude-sonnet-4-6` |
| `GEMINI_API_KEY_paid` | Gemini Vision — primary |
| `GEMINI_API_KEY_free` | Gemini Vision — fallback |
| `GEMINI_MODEL` | default `gemini-2.5-flash-lite` |
| `HUGGINGFACE_API_KEY` | HuggingFace fallback vision |
| `HF_MODEL` | default `zai-org/GLM-4.5V` |
| `IMAGEKIT_PUBLIC_KEY` / `IMAGEKIT_PRIVATE_KEY` / `IMAGEKIT_URL_ENDPOINT` / `IMAGEKIT_FOLDER` | ImageKit screenshot storage |
| `APP_ENV` | `development` / `production` |
| `SECRET_KEY` | App secret |
| `ALLOWED_ORIGINS` | CORS (comma-separated) |
| `JWT_SECRET_KEY` / `JWT_ALGORITHM` / `JWT_ACCESS_EXPIRE_MIN` / `JWT_REFRESH_EXPIRE_DAYS` | Auth JWT |
| `POLAR_ACCESS_TOKEN` / `POLAR_ORG_ID` / `POLAR_WEBHOOK_SECRET` | Polar.sh — payment gateway (Stripe deprecated; Polar = Merchant of Record, no VN business license needed) |
| `POLAR_PRODUCT_BASIC_MONTHLY` / `POLAR_PRODUCT_TOPUP_5` / `POLAR_PRODUCT_TOPUP_10` | Polar product IDs ($9/mo, $5=15cr, $10=40cr) |
| `POLAR_SUCCESS_URL` / `POLAR_ENV` | Checkout redirect + `sandbox`/`production` |

## Crawler (Mac #2, 24/7)

```
market_engine_crawler/
├── run_scheduled.py     — Dispatcher 3 crawlers
├── crawl_ledger.py      — start_run / finish_run / queue helpers
├── captcha_notify.py    — Email alert + poll-resume khi CAPTCHA
└── launchd/
    ├── com.EtseeMate.crawler.market.plist    (weekly Mon 02:00)
    ├── com.EtseeMate.crawler.EtseeMate.plist  (every 30m)
    ├── com.EtseeMate.crawler.rank.plist      (daily 04:00)
    └── git-sync.plist                        (every 5m)
```

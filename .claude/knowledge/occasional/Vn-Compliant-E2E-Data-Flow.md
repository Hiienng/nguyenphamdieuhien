# Vietnam-Compliant Data Flow — EtseeMate SaaS
> Architect_master đọc file này khi review compliance và security hàng tuần.
> Cập nhật Compliance Status Tracker sau mỗi lần review.

---

## Compliance Status Tracker
> Architect_master cập nhật bảng này sau mỗi lần weekly review.

| # | Hạng mục | Status | Sprint | Ghi chú |
|---|---|---|---|---|
| 1 | TLS in transit | ✅ Done | — | Render enforce HTTPS tự động |
| 2 | Auth (JWT + HttpOnly Cookie) | ❌ Chưa có | Sprint tới | Blocker trước khi onboard user 2 |
| 3 | IDOR protection (không tin seller_id từ FE) | ❌ Chưa có | Sprint tới | Risk cao nhất hiện tại |
| 4 | tenant_id trên mọi bảng user data | ❌ Chưa có | Sprint tới | Cần migration |
| 5 | RLS PostgreSQL | ❌ Chưa có | Sprint 2 | Sau khi có tenant_id |
| 6 | Soft-delete (is_deleted flag) | ❌ Chưa có | Sprint 2 | Áp dụng cho listings, import_batch |
| 7 | Rate limiting theo seller_id + IP | ❌ Chưa có | Sprint 2 | FastAPI middleware |
| 8 | Cloudflare WAF (Free tier) | ❌ Chưa có | Sprint 2 | Đặt trước Render, miễn phí |
| 9 | Audit log (ai sửa gì, lúc nào) | ❌ Chưa có | Sprint 3 | PostgreSQL trigger hoặc service layer |
| 10 | Data Masking PII tại API layer | 🔵 Defer | → 50+ sellers | EtseeMate không lưu PII buyer |
| 11 | Data Localization (server tại VN) | 🔵 Defer | → 100+ sellers | Render Singapore tạm thời chấp nhận được |
| 12 | Anonymization Pipeline | 🔵 Defer | → 500+ sellers | Chỉ cần khi có Data Warehouse |
| 13 | Immutable Audit Storage (Kafka) | 🔵 Defer | → 1000+ sellers | PostgreSQL append-only đủ đến 500 sellers |

---

## I. Dữ liệu của EtseeMate — Phân loại

**EtseeMate KHÔNG lưu:**
- Thông tin buyer (tên, SĐT, địa chỉ giao hàng) — đây là data của Etsy, không sync về
- Thông tin thanh toán, tài khoản ngân hàng của seller

**EtseeMate CÓ lưu:**
- Thông tin đăng nhập seller (email, password hash) — **PII nhạy cảm nhất**
- Doanh thu, ROAS, spend của từng listing — **bí mật kinh doanh của seller**
- Báo cáo Etsy Ads upload dưới dạng ảnh — **ImageKit, không trên DB**
- Market data crawl từ Etsy public — không phải PII

→ **Risk thực tế** không phải Data Localization mà là **data leakage giữa sellers** (IDOR) và **bí mật kinh doanh bị lộ** (no auth).

---

## II. Compliance Nghị định 13/2023/NĐ-CP — Áp dụng cho EtseeMate

### 1. Data Localization

**Quy định:** Dữ liệu cá nhân người dùng VN phải có bản sao tại máy chủ VN.

**EtseeMate hiện tại:** Render Singapore + Neon (US/Singapore).

**Lộ trình:**
- **1 → 100 sellers:** Singapore region chấp nhận được, chưa có nghĩa vụ pháp lý bắt buộc với SaaS nhỏ
- **100+ sellers hoặc khi có yêu cầu pháp lý:** Thêm Neon replica tại VNG Cloud hoặc VNPT IDC cho bảng `users` (PII) — các bảng analytics không cần localize

### 2. Phân loại và Mã hóa dữ liệu

**Áp dụng ngay:**
- TLS 1.3: ✅ Render enforce
- Password: bcrypt hash, không lưu plaintext
- API key (ANTHROPIC, GEMINI, IMAGEKIT): chỉ trong `.env`, không commit

**Áp dụng khi có multi-tenant (Sprint 2):**
- Encrypt `revenue`, `spend`, `roas` tại rest nếu lưu sensitive financial data
- HttpOnly Cookie cho refresh token — chống XSS

### 3. Right to be Forgotten

**Thiết kế cho EtseeMate:**
```
Seller request xóa account
    → Soft-delete: is_deleted = true, xóa khỏi active queries (30 ngày)
    → Hard-delete job (Cron): sau 30 ngày xóa sạch
       - listings, listing_report, keyword_report
       - manual_listing_report, manual_keyword_report
       - import_batch + xóa files trên ImageKit
       - Giữ lại: crawl_run logs (không phải PII)
```

**Bảng cần thêm `is_deleted`:** `listings`, `import_batch` — các bảng report cascade delete theo `listing_id`.

---

## III. Security Architecture — Theo giai đoạn

### Sprint tới (Blocker trước user 2)

**Auth — JWT + HttpOnly Cookie**
```
POST /api/v1/auth/login
    → Verify email + password
    → Tạo Access Token (15 phút, JWT, payload: seller_id + role)
    → Tạo Refresh Token (30 ngày, opaque, lưu DB)
    → Set HttpOnly Cookie: refresh_token
    → Trả về Access Token trong response body

Mọi request protected:
    → Header: Authorization: Bearer <access_token>
    → Middleware extract seller_id từ JWT
    → Inject vào request.state.seller_id
    → KHÔNG tin bất kỳ seller_id nào từ query param hay body
```

**IDOR Protection — Rule bắt buộc**
```python
# SAI — tin seller_id từ FE
listing = await db.get(listing_id=request.body.listing_id)

# ĐÚNG — luôn filter bằng seller_id từ token
listing = await db.get(
    listing_id=request.body.listing_id,
    seller_id=request.state.seller_id  # từ JWT, không từ FE
)
```

### Sprint 2 (20 → 100 sellers)

**Multi-Tenant RLS — PostgreSQL**
```sql
-- Bật RLS trên mọi bảng user data
ALTER TABLE listings ENABLE ROW LEVEL SECURITY;

CREATE POLICY seller_isolation ON listings
    USING (tenant_id = current_setting('app.tenant_id')::text);

-- Backend set trước mỗi query
SET LOCAL app.tenant_id = :seller_id;
```

**Rate Limiting — FastAPI Middleware**
```
Giới hạn theo seller_id (từ JWT):
- OCR extract: 10 requests/hour (tốn Claude API)
- Performance dashboard: 60 requests/minute
- Market data: 30 requests/minute

Giới hạn theo IP (chống anonymous abuse):
- Login attempt: 5/minute (brute force protection)
- Public endpoints: 100/minute
```

**Cloudflare Free — Đặt trước Render**
- WAF rules: block SQLi, XSS patterns
- DDoS protection tự động
- SSL termination (không cần config thêm)
- Chi phí: $0

### Sprint 3 (100+ sellers)

**Audit Logging — PostgreSQL append-only (không cần Kafka)**
```sql
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    actor_id    TEXT NOT NULL,        -- seller hoặc system
    action      VARCHAR(32) NOT NULL, -- INSERT/UPDATE/DELETE
    table_name  TEXT NOT NULL,
    record_id   TEXT NOT NULL,
    before_data JSONB,
    after_data  JSONB,
    ip_address  INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Chỉ append, không UPDATE/DELETE bảng này
-- Index: (tenant_id, table_name, created_at)
```

Ghi audit log tại service layer (không phải trigger DB) — dễ maintain hơn.

**RBAC — Seller có thể tạo sub-account**
```
Role: owner   → full access
Role: analyst → read-only dashboard + reports
Role: importer → chỉ upload báo cáo, không xem financial data
```

---

## IV. Kiến trúc bảo mật tổng thể (Target 100 sellers)

```
Internet
    │
    ▼
Cloudflare (WAF + DDoS + SSL) [Free]
    │
    ▼
Render.com HTTPS
    │
    ▼
FastAPI
    ├── Auth Middleware (JWT verify → inject tenant_id)
    ├── Rate Limit Middleware (per seller_id + IP)
    └── Routes
          │
          ▼
    PostgreSQL Neon
    ├── RLS enforce tenant isolation
    ├── audit_log (append-only)
    └── Soft-delete trên listings, import_batch
```

**Chi phí toàn bộ stack bảo mật này:** $0 thêm (Cloudflare Free + PostgreSQL RLS native).

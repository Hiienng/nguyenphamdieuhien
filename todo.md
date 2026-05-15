# TODO — Auth + Payment System

> Generated: 2026-05-14 | Status: pending

---

## BACKEND DEVELOPER

### BE-1: DB Models + Migration
- [ ] Tạo `backend/app/models/user.py` — SQLAlchemy model cho `users` table
  - Fields: id (UUID PK), email (VARCHAR 255 UNIQUE), password_hash (VARCHAR 255), full_name (VARCHAR 128), is_active (BOOL default true), is_admin (BOOL default false), created_at, updated_at
- [ ] Tạo `backend/app/models/subscription.py` — model cho `subscriptions` table
  - Fields: id (UUID PK), user_id (UUID FK→users), plan (VARCHAR 32 default 'monthly'), status (VARCHAR 16: active/cancelled/expired), period_start (TIMESTAMPTZ), period_end (TIMESTAMPTZ), stripe_sub_id (VARCHAR 128), created_at
- [ ] Tạo `backend/app/models/credit.py` — models cho `credit_accounts` + `credit_transactions`
  - credit_accounts: id (UUID PK), user_id (UUID FK UNIQUE), balance (INT default 0), updated_at
  - credit_transactions: id (UUID PK), user_id (UUID FK), amount (INT: +10 deposit / -1 debit), tx_type (VARCHAR 16: deposit/debit), description (TEXT), stripe_pi_id (VARCHAR 128 nullable), created_at
- [ ] Tạo `backend/app/models/payment.py` — model cho `payment_records` table
  - Fields: id (UUID PK), user_id (UUID FK nullable), stripe_event_id (VARCHAR 128 UNIQUE), event_type (VARCHAR 64), amount_cents (INT), currency (VARCHAR 8), payload (JSONB), processed_at (TIMESTAMPTZ)
- [ ] Tạo migration script (Alembic hoặc raw SQL) tạo 5 tables trên
- [ ] Cập nhật `backend/app/models/__init__.py` export các models mới

### BE-2: Auth Service + Routes
- [ ] Tạo `backend/app/services/auth_service.py`
  - `hash_password(plain)` → bcrypt hash
  - `verify_password(plain, hashed)` → bool
  - `create_access_token(user_id, expires_delta)` → JWT string
  - `create_refresh_token(user_id)` → JWT string (7 ngày)
  - `decode_token(token)` → payload dict
- [ ] Tạo `backend/app/api/routes/auth.py`
  - `POST /api/v1/auth/register` — tạo user + credit_account (balance=0), trả access_token
  - `POST /api/v1/auth/login` — verify password, trả access_token + set refresh_token cookie (httpOnly)
  - `POST /api/v1/auth/refresh` — validate refresh cookie, issue new access_token
  - `POST /api/v1/auth/logout` — clear refresh cookie
  - `GET /api/v1/auth/me` — trả profile + subscription status + credit balance
- [ ] Cập nhật `backend/app/core/config.py` — thêm fields:
  - JWT_SECRET_KEY, JWT_ALGORITHM (default HS256), JWT_ACCESS_EXPIRE_MIN (30), JWT_REFRESH_EXPIRE_DAYS (7)
  - STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PUBLISHABLE_KEY
  - STRIPE_PRICE_SUBSCRIPTION (recurring $9.9/month), STRIPE_PRICE_CREDIT_DEPOSIT (one-time $9.9)
- [ ] Cập nhật `.env.example` với các env vars mới

### BE-3: Auth Middleware
- [ ] Tạo `backend/app/core/auth_middleware.py`
  - `get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db))` → User
  - `get_current_active_user` → raise 401 nếu is_active=false
  - `require_subscription(user, db)` → raise 403 nếu không có active subscription
  - `require_credit(user, db, amount=1)` → raise 402 nếu balance < amount

### BE-4: Billing Service
- [ ] Tạo `backend/app/services/billing_service.py`
  - `create_subscription_checkout(user_id, success_url, cancel_url)` → Stripe Checkout Session URL
  - `create_deposit_checkout(user_id, success_url, cancel_url)` → Stripe Checkout Session URL
  - `handle_webhook_event(payload, sig_header)` → process Stripe event:
    - `checkout.session.completed` với mode=subscription → activate subscription record
    - `checkout.session.completed` với mode=payment → credit +10 vào credit_account
    - `customer.subscription.deleted` → set subscription status=expired
  - `deduct_credit(user_id, db, amount=1)` → deduct + log credit_transaction

### BE-5: Billing Routes
- [ ] Tạo `backend/app/api/routes/billing.py`
  - `POST /api/v1/billing/subscribe` (auth required) → tạo Stripe Checkout Session subscription
  - `GET /api/v1/billing/subscription` (auth required) → trả subscription status
  - `POST /api/v1/billing/cancel` (auth required) → cancel subscription at period end
  - `POST /api/v1/billing/deposit` (auth required) → tạo Stripe Checkout Session payment
  - `GET /api/v1/billing/credits` (auth required) → balance + 10 giao dịch gần nhất
  - `POST /api/v1/billing/webhook` (NO auth — Stripe signature verify) → xử lý webhook

### BE-6: Gate Existing Routes
- [ ] Sửa `backend/app/api/routes/intelligence.py`
  - Thêm `get_current_active_user` dependency cho `POST /api/v1/intelligence/thumbnail-eval`
  - Gọi `require_credit(user, db)` trước khi chạy eval
  - Gọi `deduct_credit(user_id, db)` sau khi eval thành công
- [ ] Sửa `backend/app/api/routes/performance.py` (hoặc file routes tương ứng)
  - Thêm `require_subscription` dependency cho các GET/POST performance endpoints
- [ ] Sửa `backend/app/main.py`
  - Include routers: `auth.router`, `billing.router`
- [ ] Cập nhật `backend/requirements.txt` thêm:
  - `stripe>=7.0.0`, `python-jose[cryptography]>=3.3.0`, `passlib[bcrypt]>=1.7.4`, `python-multipart>=0.0.6`

---

## FRONTEND DEVELOPER

> ⚠️ Đọc `.claude/knowledge/DESIGN.md` trước khi viết bất kỳ CSS/HTML nào. Mọi font, màu, spacing phải follow Design System — không được tự suy đoán.

> File chính: `frontend/EtseeMate.html` — KHÔNG tạo lại, KHÔNG xóa

### FE-1: Thay Login Gate → Real Auth
- [ ] Xóa static token hash login (SHA-256 hardcoded)
- [ ] Thêm Login modal HTML: email input + password input + submit button + "Register" link
- [ ] JS: `authLogin(email, password)` → `POST /api/v1/auth/login` → lưu access_token trong memory (biến JS)
- [ ] JS: `authLogout()` → `POST /api/v1/auth/logout` → xóa token, reload về login
- [ ] JS: auto-refresh token khi nhận 401 response → gọi `POST /api/v1/auth/refresh`
- [ ] JS: `getAuthHeaders()` → `{ Authorization: 'Bearer <token>' }` — inject vào mọi fetch call
- [ ] Wrap toàn bộ app trong auth gate: nếu chưa login → show login modal, ẩn app content

### FE-2: Register Modal
- [ ] Thêm Register modal HTML: full_name + email + password + confirm_password + submit
- [ ] JS: `authRegister(data)` → `POST /api/v1/auth/register` → auto login sau khi đăng ký thành công
- [ ] Validate client-side: email format, password ≥ 8 ký tự, confirm match
- [ ] Toggle link giữa Login ↔ Register modal

### FE-3: Nav User Info + Badges
- [ ] Thêm vào header/nav: user avatar (initials) + full_name
- [ ] Subscription badge: "PRO" (xanh) nếu active subscription, "Free" (xám) nếu không
- [ ] Credit counter: "⚡ 10 credits" — cập nhật từ `GET /api/v1/auth/me`
- [ ] Logout button
- [ ] Fetch user info khi load app → populate badges

### FE-4: Paywall Modals
- [ ] **Subscription Paywall Modal** (trigger khi click Performance Hub tab mà chưa có subscription):
  - Tiêu đề: "Unlock Performance Hub"
  - Mô tả: Full access to all performance analytics for $9.9/month
  - CTA button: "Subscribe $9.9/month" → `POST /api/v1/billing/subscribe` → redirect to Stripe Checkout URL
  - Link: "Or deposit credits instead"
- [ ] **Deposit Modal** (trigger khi credit = 0 và cố dùng Thumbnail Scoring):
  - Tiêu đề: "You're out of credits"
  - Mô tả: Get 10 thumbnail scoring credits for $9.9
  - CTA button: "Deposit $9.9 → 10 credits" → `POST /api/v1/billing/deposit` → redirect to Stripe Checkout
  - Credit balance display: "Current balance: 0 credits"
- [ ] Stripe Checkout redirect: sau khi payment success, Stripe redirect về app với `?payment=success` → toast notification + refresh user info

---

## DONE CRITERIA
- [ ] User có thể register, login, logout
- [ ] User có thể subscribe $9.9/month qua Stripe Checkout → access Performance Hub
- [ ] User có thể deposit $9.9 → nhận 10 credits → dùng Thumbnail Scoring
- [ ] Credit deducted sau mỗi lần scoring, balance hiển thị real-time
- [ ] Unauthenticated requests bị reject 401
- [ ] Non-subscriber bị reject 403 khi truy cập performance routes
- [ ] Zero-credit user bị reject 402 khi dùng thumbnail eval

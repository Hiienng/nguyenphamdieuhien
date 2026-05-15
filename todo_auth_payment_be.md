# TODO — Auth + Payment System · BACKEND
> Generated: 2026-05-14 | Assignee: Backend Developer Agent

---

### BE-1: DB Models + Migration
- [ ] Tạo `backend/app/models/user.py` — SQLAlchemy model `users`
  - Fields: id (UUID PK), email (VARCHAR 255 UNIQUE NOT NULL), password_hash (VARCHAR 255 NOT NULL), full_name (VARCHAR 128), is_active (BOOL default true), is_admin (BOOL default false), created_at (TIMESTAMPTZ), updated_at (TIMESTAMPTZ)
- [ ] Tạo `backend/app/models/subscription.py` — model `subscriptions`
  - Fields: id (UUID PK), user_id (UUID FK→users), plan (VARCHAR 32 default 'monthly'), status (VARCHAR 16: active/cancelled/expired), period_start (TIMESTAMPTZ), period_end (TIMESTAMPTZ), stripe_sub_id (VARCHAR 128), created_at (TIMESTAMPTZ)
- [ ] Tạo `backend/app/models/credit.py` — models `credit_accounts` + `credit_transactions`
  - credit_accounts: id (UUID PK), user_id (UUID FK UNIQUE), balance (INT default 0), updated_at
  - credit_transactions: id (UUID PK), user_id (UUID FK), amount (INT: +10 deposit / -1 debit), tx_type (VARCHAR 16: deposit/debit), description (TEXT), stripe_pi_id (VARCHAR 128 nullable), created_at
- [ ] Tạo `backend/app/models/payment.py` — model `payment_records`
  - Fields: id (UUID PK), user_id (UUID FK nullable), stripe_event_id (VARCHAR 128 UNIQUE), event_type (VARCHAR 64), amount_cents (INT), currency (VARCHAR 8), payload (JSONB), processed_at (TIMESTAMPTZ)
- [ ] Tạo migration script (Alembic) tạo 5 tables — không DROP table hiện có
- [ ] Cập nhật `backend/app/models/__init__.py` export các models mới

### BE-2: Auth Service + Routes
- [ ] Tạo `backend/app/services/auth_service.py`
  - `hash_password(plain)` → bcrypt hash
  - `verify_password(plain, hashed)` → bool
  - `create_access_token(user_id, expires_delta)` → JWT string (30 min)
  - `create_refresh_token(user_id)` → JWT string (7 ngày)
  - `decode_token(token)` → payload dict
- [ ] Tạo `backend/app/api/routes/auth.py`
  - `POST /api/v1/auth/register` — tạo user + credit_account (balance=0), trả access_token
  - `POST /api/v1/auth/login` — verify password, trả access_token + set refresh_token httpOnly cookie
  - `POST /api/v1/auth/refresh` — validate refresh cookie → issue new access_token
  - `POST /api/v1/auth/logout` — clear refresh cookie
  - `GET /api/v1/auth/me` — trả profile + subscription status + credit balance
- [ ] Cập nhật `backend/app/core/config.py` — thêm:
  - JWT_SECRET_KEY, JWT_ALGORITHM (HS256), JWT_ACCESS_EXPIRE_MIN (30), JWT_REFRESH_EXPIRE_DAYS (7)
  - STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PUBLISHABLE_KEY
  - STRIPE_PRICE_SUBSCRIPTION, STRIPE_PRICE_CREDIT_DEPOSIT
- [ ] Cập nhật `.env.example` với tất cả env vars mới

### BE-3: Auth Middleware
- [ ] Tạo `backend/app/core/auth_middleware.py`
  - `get_current_user(token=Depends(oauth2_scheme), db=Depends(get_db))` → User
  - `get_current_active_user` → raise 401 nếu is_active=false
  - `require_subscription(user, db)` → raise 403 nếu không có active subscription
  - `require_credit(user, db, amount=1)` → raise 402 nếu balance < amount

### BE-4: Billing Service
- [ ] Tạo `backend/app/services/billing_service.py`
  - `create_subscription_checkout(user_id, success_url, cancel_url)` → Stripe Checkout Session URL
  - `create_deposit_checkout(user_id, success_url, cancel_url)` → Stripe Checkout Session URL
  - `handle_webhook_event(payload, sig_header)`:
    - `checkout.session.completed` mode=subscription → activate subscription record
    - `checkout.session.completed` mode=payment → credit_account balance +10
    - `customer.subscription.deleted` → subscription status=expired
  - `deduct_credit(user_id, db, amount=1)` → deduct + insert credit_transaction

### BE-5: Billing Routes
- [ ] Tạo `backend/app/api/routes/billing.py`
  - `POST /api/v1/billing/subscribe` (auth required) → Stripe Checkout Session subscription
  - `GET  /api/v1/billing/subscription` (auth required) → subscription status
  - `POST /api/v1/billing/cancel` (auth required) → cancel at period end
  - `POST /api/v1/billing/deposit` (auth required) → Stripe Checkout Session payment
  - `GET  /api/v1/billing/credits` (auth required) → balance + 10 giao dịch gần nhất
  - `POST /api/v1/billing/webhook` (NO auth — Stripe sig verify) → process webhook

### BE-6: Gate Existing Routes + Wire-up
- [ ] Sửa `backend/app/api/routes/intelligence.py`
  - Thêm `get_current_active_user` dependency cho `POST /api/v1/intelligence/thumbnail-eval`
  - Gọi `require_credit(user, db)` trước eval
  - Gọi `deduct_credit(user_id, db)` sau eval thành công
- [ ] Sửa route performance (xác định file thực tế) — thêm `require_subscription` dependency
- [ ] Sửa `backend/app/main.py` — include `auth.router` + `billing.router`
- [ ] Cập nhật `backend/requirements.txt`:
  - `stripe>=7.0.0`
  - `python-jose[cryptography]>=3.3.0`
  - `passlib[bcrypt]>=1.7.4`
  - `python-multipart>=0.0.6`

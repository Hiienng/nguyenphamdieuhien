# Credit & Subscription System — EtseeMate

**Architect:** Claude  
**Created:** 2026-05-17  
**Status:** Plan Ready for Approval  
**Timeline:** 3 days

---

## I. Executive Summary

Restructure the billing model around **credits** (consumable) + **base subscription** (access):

### Pricing Plans

| Plan | Price | Access | Credits | Credit Behavior |
|---|---|---|---|---|
| **Free Trial** | $0 | 7 days | 3 (one-time) | Expires with trial |
| **Basic** | $9/month | Forever (while active) | 5/month (refilled monthly) | Refilled credits expire when not used in cycle |
| **Top-up $5** | $5 one-time | — | +15 credits | **Never expire**, non-refundable |
| **Top-up $10** | $10 one-time | — | +40 credits | **Never expire**, non-refundable |

### Feature Access Rules

- **All features** are unlocked for any user with `active subscription OR trial`
- Features split into **2 tiers**:
  - **Free features** (no API cost): Browse market, view dashboard, see references, basic listing list
  - **Credit features** (1 credit per call): Thumbnail eval, AI title/tag generation, market trend deep-dive, competitor analysis crawl
- Each credit-consuming endpoint **deducts 1 credit atomically on success** (refunded on failure)

### Credit Buckets

Each user has TWO credit pools:

1. **`subscription_credits`** — Refilled monthly with subscription. Expires at end of cycle if unused.
2. **`topup_credits`** — Purchased via top-up. **Never expire.**

Deduction order: **subscription_credits first** (use-it-or-lose-it), then **topup_credits**.

---

## II. User Journey

```
Signup → Auto trial (7 days, 3 credits in subscription_credits, expires with trial)
  ↓
User explores features. Free features = unlimited. Credit features = -1 credit each.
  ↓
[Day 7] Trial ends → all credit-feature endpoints return 402 "Insufficient credits or no active plan"
  ↓
User upgrades to Basic ($9/mo) → status="active", subscription_credits = 5 (refilled monthly)
  ↓
User wants more credits → Top-up $5 (+15) or $10 (+40) → added to topup_credits (no expiry)
  ↓
Monthly: subscription_credits resets to 5 (old unused = lost), topup_credits untouched
```

---

## III. Database Changes

### `credit_accounts` — split balance into 2 buckets

| Column | Type | Ghi chú |
|---|---|---|
| id | UUID PK | existing |
| user_id | UUID FK UNIQUE | existing |
| subscription_credits | INT default 0 | NEW — monthly refill, expires |
| topup_credits | INT default 0 | NEW — purchased, never expire |
| ~~balance~~ | INT | DEPRECATED — keep for backward compat, sync = sub + topup |
| subscription_credits_reset_at | TIMESTAMPTZ | NEW — when to refill (= subscription.period_end) |
| updated_at | TIMESTAMPTZ | existing |

### `credit_transactions` — extend `tx_type`

Existing `tx_type` values: `deposit`, `debit`. Add:
- `trial_grant` — Initial 3 credits on signup
- `subscription_refill` — Monthly 5 credits on Basic plan
- `topup_5` / `topup_10` — Stripe one-time purchase
- `feature_debit` — 1 credit deducted per API call

Add column:
- `bucket` VARCHAR(16) — `"subscription"` or `"topup"` — which pool the transaction touched

### `subscriptions` — clarify plan codes

Plan values:
- `trial_7_days` — 7-day trial
- `basic_monthly` — $9/month Basic plan
- (future) `pro_monthly`, etc.

---

## IV. Backend API Changes

### Credit Service (`backend/app/services/credit_service.py` — NEW)

```python
async def get_balance(user_id, db) -> dict:
    """Returns {subscription: int, topup: int, total: int}"""

async def grant_credits(user_id, amount, bucket, reason, db) -> None:
    """Add credits to a bucket + record transaction"""

async def consume_credits(user_id, amount, feature, db) -> bool:
    """Atomically deduct from subscription bucket first, then topup.
    Returns False if insufficient. Records transaction."""

async def refund_credits(user_id, amount, feature, db) -> None:
    """If API call fails after deduction, refund 1 credit."""

async def refill_subscription_credits(user_id, plan, db) -> None:
    """Called on monthly cycle: reset subscription_credits to plan's monthly allowance."""
```

### Endpoints

| Method | Path | Behavior |
|---|---|---|
| GET | `/api/v1/billing/credits` | Returns `{subscription, topup, total, history}` |
| GET | `/api/v1/billing/plans` | Returns plan catalog (Free, Basic, top-ups) |
| POST | `/api/v1/billing/subscribe` | Body `{plan: "basic_monthly"}` → Stripe Checkout URL |
| POST | `/api/v1/billing/topup` | Body `{pack: "topup_5"\|"topup_10"}` → Stripe Checkout URL |
| POST | `/api/v1/billing/webhook` | Stripe webhook → grants credits / activates sub |

### New Middleware

`require_credits(amount: int)` — Used on every credit-consuming endpoint:

```python
@router.post("/thumbnail-eval", dependencies=[Depends(require_credits(1))])
async def thumbnail_eval(...):
    # If insufficient: 402 Payment Required
    # Else: deduct 1, proceed. On exception: refund.
```

### Endpoints Marked as "Credit-Consuming"

| Endpoint | Cost | Reason |
|---|---|---|
| `POST /api/v1/intelligence/thumbnail-eval` | 1 | Vision API call |
| `POST /api/v1/intelligence/thumbnail-knowledge/generate` | 1 | Vision API + DB write |
| `POST /api/v1/listings/optimize-title` (future) | 1 | Claude API |
| `POST /api/v1/listings/optimize-tags` (future) | 1 | Claude API |
| `POST /api/v1/market/deep-analysis` (future) | 1 | Heavy query + Claude |

**Free (no credit):** dashboard, listings list, references view, market browse, performance reports.

---

## V. Frontend Changes

### Credit Display in App Header

```
┌─────────────────────────────────────────┐
│ EtseeMate    [Dashboard] [Market] ...   │
│                          ⚡ 8 credits ▾ │ ← New chip in header
└─────────────────────────────────────────┘
```

Click → dropdown:
```
Subscription credits: 3 (resets in 12 days)
Top-up credits:       5 (never expire)
─────────────────────────────
                          [+ Buy credits]
                       [Upgrade to Basic]
```

### Per-Feature Cost Badge

On every credit-consuming button, show a small badge:

```
[ Score Thumbnail ⚡ 1 credit ]
[ Optimize Title  ⚡ 1 credit ]
```

Tooltip on hover: *"This action uses 1 credit (you have 8)"*

### Pre-Action Confirmation (only when balance ≤ 3)

```
┌───────────────────────────────────────┐
│ Use 1 credit to score this thumbnail? │
│ You have 2 credits remaining.         │
│                                       │
│         [ Cancel ]  [ Yes, use 1 ]    │
└───────────────────────────────────────┘
```

Above 3 credits: silent (just deduct + run).

### Out-of-Credits Modal

When backend returns 402:

```
┌──────────────────────────────────────┐
│  💳 Out of credits                   │
│                                       │
│  This action needs 1 credit but      │
│  you have 0.                         │
│                                       │
│  Choose a top-up:                    │
│  ○ $5  → 15 credits ($0.33 each)     │
│  ● $10 → 40 credits ($0.25 each)     │
│                                       │
│  Or upgrade to Basic for $9/mo       │
│  (5 monthly credits + access)        │
│                                       │
│      [Buy credits]  [Upgrade]        │
└──────────────────────────────────────┘
```

---

## VI. Implementation Tasks

### Backend

| Task | Files | Notes |
|---|---|---|
| **B11** Migration: add credit buckets | `migrations/010_credit_buckets.sql` | ALTER credit_accounts + credit_transactions |
| **B12** Credit service | `services/credit_service.py` (NEW) | get/grant/consume/refund/refill |
| **B13** Refactor signup grant | `routes/auth.py` | Trial = 3 credits in subscription bucket |
| **B14** `require_credits` middleware | `core/auth_middleware.py` | Decorator that deducts + refunds on error |
| **B15** Apply to feature endpoints | `routes/intelligence.py` | Add `Depends(require_credits(1))` |
| **B16** Plans catalog endpoint | `routes/billing.py` | GET `/billing/plans` |
| **B17** Top-up endpoint | `routes/billing.py` | POST `/billing/topup` → Polar checkout URL |
| **B18** Polar webhook handler | `routes/billing.py` | Verify signature + handle 6 event types |
| **B19** Subscription credit refill on renewal | `services/billing_service.py` | Triggered on `subscription.updated` (new period) |
| **B20** Polar SDK adapter | `services/payment_service.py` (NEW) | Gateway-agnostic interface for future swap |

### Frontend

| Task | Files | Notes |
|---|---|---|
| **F8** Credit chip in app header | `app.html`, `js/credit-display.js` (NEW) | Polls `/billing/credits` on load |
| **F9** Per-feature cost badge | `app.html` (button HTML) + small CSS | `⚡ 1 credit` |
| **F10** Pre-action confirm (low balance) | `js/credit-confirm.js` (NEW) | Modal when balance ≤ 3 |
| **F11** Out-of-credits modal (402 handler) | `js/credit-display.js` | Intercept 402, show purchase options |
| **F12** Update pricing section on landing | `index.html` | Reflect new $9 + top-up tiers |

### Architect-Owned

- **B11** migration script + apply via existing `apply_migration.py`
- Update context files: `db_schema.md`, `api_contracts.md`

---

## VII. Atomicity & Race Condition Handling

**Critical:** Credit deduction must be **atomic** to prevent double-spend.

```sql
-- In credit_service.consume_credits():
UPDATE credit_accounts
SET subscription_credits = GREATEST(subscription_credits - LEAST(subscription_credits, $1), 0),
    topup_credits = topup_credits - GREATEST($1 - subscription_credits, 0),
    updated_at = NOW()
WHERE user_id = $2
  AND (subscription_credits + topup_credits) >= $1
RETURNING subscription_credits, topup_credits;
```

If 0 rows returned → insufficient credits, raise 402.  
Always wrap deduct + API-call + insert-transaction in **one DB transaction**. If API call fails after deduct, refund in `finally` block.

---

## VIII. Polar.sh Configuration (env vars)

**Why Polar.sh:** Merchant-of-Record (no Vietnamese business license required), 4% + $0.40 per transaction, handles VAT globally, payout to Wise/bank.

Add to `.env.example`:

```
POLAR_ACCESS_TOKEN=polar_pat_xxx              # API token (Settings → Developers)
POLAR_ORG_ID=org_xxx                          # Polar organization ID
POLAR_WEBHOOK_SECRET=whsec_xxx                # For verifying webhook signatures
POLAR_PRODUCT_BASIC_MONTHLY=prod_xxx          # $9/mo recurring product ID
POLAR_PRODUCT_TOPUP_5=prod_xxx                # $5 one-time = 15 credits
POLAR_PRODUCT_TOPUP_10=prod_xxx               # $10 one-time = 40 credits
POLAR_SUCCESS_URL=https://etseemate.com/billing/success
POLAR_ENV=sandbox                             # "sandbox" or "production"
```

**SDK:** `polar-sdk` (Python) — `pip install polar-sdk`

**Webhook events to handle:**
- `checkout.created` — User started checkout (no action)
- `checkout.updated` with `status="succeeded"` — Payment completed → grant credits / activate sub
- `subscription.created` — New subscription → set status="active", refill credits
- `subscription.updated` — Renewal → refill subscription_credits
- `subscription.canceled` — User cancelled → keep access until period_end, then expired
- `order.created` — One-time purchase confirmed (top-up) → grant topup_credits

**Webhook security:** Polar uses standard webhook signature (HMAC-SHA256). Verify `webhook-signature` header on every request.

**Customer linkage:** Pass `customer_email` or `metadata={"user_id": "..."}` when creating checkout sessions. Webhook payload includes the metadata so we know which user to credit.

**Routing:** Replace `routes/billing.py` Stripe references with `routes/billing.py` using Polar SDK. Architecture is gateway-agnostic via `services/payment_service.py` abstraction.

---

## IX. Migration Plan (Backward Compatible)

1. Apply `010_credit_buckets.sql`: ADD COLUMNS (default 0) — no data loss.
2. Backfill existing users: `UPDATE credit_accounts SET topup_credits = balance` (treat all existing credits as topup, since they were purchased).
3. Deploy backend with dual-read: still expose `balance` field as `subscription + topup` for compatibility.
4. Deploy frontend with new credit chip; old clients keep working via `balance`.
5. After 2 weeks: drop `balance` column.

---

## X. Success Criteria

**Backend:**
- [ ] Signup grants 3 trial credits (subscription bucket, expires with trial)
- [ ] `consume_credits` deducts subscription first, then topup
- [ ] Failed API call → credits refunded
- [ ] 402 returned when insufficient
- [ ] Stripe webhooks correctly refill (Basic) and add (top-up) credits
- [ ] Race-condition-free under 10 concurrent requests

**Frontend:**
- [ ] Header chip shows live balance, updates after each action
- [ ] Cost badges visible on all credit features
- [ ] Out-of-credits modal opens on 402
- [ ] Pricing page updated to new $9 + top-up structure

**Integration:**
- [ ] User can sign up → use 3 credits → upgrade → get 5 → top up $5 → see 20 (5+15)
- [ ] After 30 days, subscription credits reset to 5; top-ups untouched

---

## XI. Outstanding Questions

1. **Trial = 3 credits in `subscription` bucket — confirmed?** (Lost when trial ends, which matches "expires with trial.")
2. **Basic plan: 5 credits each calendar month vs each billing cycle?** Recommend billing cycle (simpler with Stripe).
3. **What happens if user cancels Basic mid-month?** Recommend: keep credits till period_end, then both buckets cleared except topup.
4. **Should we show "X credits used today" history in dashboard?** (Out of scope for MVP — covered by transaction log endpoint.)

---

## Ready for Approval ✅

**Document:** todo_credit_subscription.md  
**Status:** ⏳ Awaiting approval  
**Created:** 2026-05-17

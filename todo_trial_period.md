# Trial Period System — EtseeMate
**Architect:** Claude  
**Created:** 2026-05-17  
**Status:** Implementation Plan  
**Timeline:** 2 days  

---

## I. Executive Summary

After signup, users automatically get a **7-day free trial**:
- Access to all features (market data, thumbnail scoring, competitor analysis)
- Trial starts at account creation
- On day 8, features locked until user upgrades to paid plan
- Can check trial status anytime via `/api/v1/billing/trial-status`

**Key Logic:**
- Trial ends at: `created_at + 7 days`
- Paid plans (Stripe) override trial — user gets full access immediately upon payment
- Free tier users can stay on trial until day 8, then must upgrade

---

## II. User Journey

```
Signup (POST /api/v1/auth/register)
  ↓
created_at = now()
trial_ends_at = now() + 7 days
  ↓
User onboards (products + location)
  ↓
Access dashboard: See market data, thumbnail scoring, competitor analysis
  ↓
Check trial status: GET /api/v1/billing/trial-status
Response: { trial_active: true, days_remaining: 6, trial_ends_at: "2026-05-24T..." }
  ↓
Day 8: Trial expired
  ↓
User tries to access /api/v1/performance/* or /api/v1/intelligence/thumbnail-eval
  ↓
Backend returns 403 with message: "Trial expired. Upgrade to continue."
  ↓
User upgrades: POST /api/v1/billing/subscribe
  ↓
Stripe webhook sets subscription to active
  ↓
Access restored immediately
```

---

## III. Database Schema Changes

### Modify `users` Table
No new columns needed — we calculate trial status from existing `created_at`.

### Modify `subscriptions` Table
Ensure we can distinguish:
- `status = "trial"` — Active trial (no Stripe sub yet)
- `status = "active"` — Paid subscription (Stripe)
- `status = "cancelled"` — Expired/cancelled subscription

### Alternative: Add `subscription_tier` Column to Users

| Column | Type | Ghi chú |
|---|---|---|
| subscription_tier | VARCHAR(16) | "free_trial" / "paid" / "free" (future) |

Or use `subscriptions` table status field:
- No subscription row = trial
- subscription row with status="trial" = trial (explicit)
- subscription row with status="active" = paid

**Recommendation:** Use `subscriptions` table. On signup, create a `trial` subscription record:

```sql
INSERT INTO subscriptions (id, user_id, plan, status, period_start, period_end, created_at)
VALUES (uuid, user_id, 'trial_7_days', 'trial', now(), now() + interval '7 days', now());
```

---

## IV. API Design

### New Endpoint: GET `/api/v1/billing/trial-status` (public)

**Auth:** Required (Bearer token)

**Response:**
```json
{
  "trial_active": true,
  "days_remaining": 6,
  "trial_ends_at": "2026-05-24T10:00:00Z",
  "hours_remaining": 152,
  "can_access_features": true
}
```

**Or if trial expired:**
```json
{
  "trial_active": false,
  "days_remaining": 0,
  "trial_ends_at": "2026-05-24T10:00:00Z",
  "hours_remaining": 0,
  "can_access_features": false,
  "message": "Trial expired. Upgrade to continue."
}
```

### Update: POST `/api/v1/auth/register`

On successful signup, automatically create a trial subscription:

```python
# In register endpoint, after user creation:
trial_subscription = Subscription(
    id=str(uuid.uuid4()),
    user_id=user.id,
    plan='trial_7_days',
    status='trial',
    period_start=datetime.now(timezone.utc),
    period_end=datetime.now(timezone.utc) + timedelta(days=7),
    stripe_sub_id=None,  # No Stripe for trial
)
db.add(trial_subscription)
await db.commit()
```

### Update: Protected Endpoints

Add trial check to endpoints that require active subscription:
- `GET /api/v1/performance/listings` — Check trial active
- `POST /api/v1/intelligence/thumbnail-eval` — Check credits OR trial active
- `POST /api/v1/intelligence/thumbnail-knowledge/generate` — Check trial active

**Error Response (403):**
```json
{
  "detail": "Trial expired. Please upgrade to continue.",
  "type": "trial_expired",
  "upgrade_url": "/pricing"
}
```

---

## V. Implementation Tasks

### B7: Database & Subscription Logic

- [ ] Ensure `subscriptions` table has `plan` column (VARCHAR 64)
- [ ] Ensure `subscriptions.status` can be: "trial", "active", "cancelled", "expired"
- [ ] Create service: `backend/app/services/trial_service.py`
  - `get_trial_status(user: User, db) → TrialStatus`
  - `is_trial_active(user: User, db) → bool`
  - `get_days_remaining(user: User, db) → int`
  - `get_trial_subscription(user_id, db) → Subscription | None`

### B8: Trial Status Endpoint

- [ ] Create `GET /api/v1/billing/trial-status` endpoint
  - Check if user has active trial subscription
  - Calculate days/hours remaining
  - Return trial status object

### B9: Update Auth Register Endpoint

- [ ] Modify `POST /api/v1/auth/register` to create trial subscription
  - After user creation, create subscription with plan="trial_7_days"
  - period_start = now()
  - period_end = now() + 7 days
  - status = "trial"

### B10: Add Trial Check Middleware

- [ ] Create auth dependency: `require_active_subscription()`
  - Checks: trial active OR paid subscription active
  - Returns 403 if neither
- [ ] Apply to protected endpoints:
  - `/api/v1/performance/listings`
  - `/api/v1/intelligence/thumbnail-eval`
  - `/api/v1/intelligence/thumbnail-knowledge/generate`

### F7: Update Frontend Dashboard

- [ ] Add trial status indicator in header/sidebar
  - "Trial: 6 days remaining" (if active)
  - "Trial expired" (if not active) with upgrade CTA
- [ ] Display on GET /app.html load
  - Fetch trial status from backend
  - Show banner with countdown or upgrade prompt
- [ ] Update app.js to handle 403 "trial_expired" errors
  - Redirect to /pricing or show upgrade modal

---

## VI. File Map

**Backend:**
- `backend/app/services/trial_service.py` (NEW) — Trial logic
- `backend/app/schemas/billing.py` → Add `TrialStatus` schema
- `backend/app/api/routes/billing.py` → Add trial-status endpoint
- `backend/app/api/routes/auth.py` → Update register to create trial subscription
- `backend/app/core/auth_middleware.py` → Add `require_active_subscription()` dependency
- `backend/migrations/009_update_subscriptions_for_trial.sql` (NEW) — Add plan column if missing

**Frontend:**
- `frontend/js/app.js` → Fetch trial status, handle 403 errors
- `frontend/app.html` → Add trial indicator in header
- `frontend/css/app.css` → Styling for trial banner

---

## VII. API Contracts

### GET `/api/v1/billing/trial-status`

**Auth:** Required

**Response (200):**
```json
{
  "trial_active": true,
  "days_remaining": 6,
  "hours_remaining": 152,
  "trial_ends_at": "2026-05-24T10:00:00Z",
  "can_access_features": true
}
```

**Response (200, expired):**
```json
{
  "trial_active": false,
  "days_remaining": 0,
  "hours_remaining": 0,
  "trial_ends_at": "2026-05-24T10:00:00Z",
  "can_access_features": false
}
```

### Protected Endpoint (e.g., GET `/api/v1/performance/listings`)

**If trial expired:**
```json
{
  "detail": "Trial expired. Please upgrade to continue.",
  "type": "trial_expired"
}
```
Status: 403 Forbidden

---

## VIII. Trial Logic Pseudo-Code

### Check Trial Active

```python
async def is_trial_active(user_id: str, db: AsyncSession) -> bool:
    """Check if user's trial is still active."""
    sub = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "trial",
            Subscription.period_end > datetime.now(timezone.utc),
        )
    )
    return sub is not None
```

### Check Active Subscription (Trial OR Paid)

```python
async def has_active_subscription(user_id: str, db: AsyncSession) -> bool:
    """Check if user has trial or paid subscription."""
    now = datetime.now(timezone.utc)
    sub = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["trial", "active"]),
            Subscription.period_end > now,
        )
    )
    return sub is not None
```

### Get Trial Status

```python
async def get_trial_status(user_id: str, db: AsyncSession) -> dict:
    """Get detailed trial status."""
    trial_sub = await db.scalar(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == "trial",
        )
    )
    
    if not trial_sub:
        return {"trial_active": False, "days_remaining": 0, ...}
    
    now = datetime.now(timezone.utc)
    if trial_sub.period_end <= now:
        return {"trial_active": False, "days_remaining": 0, ...}
    
    days_left = (trial_sub.period_end - now).days
    hours_left = (trial_sub.period_end - now).seconds // 3600
    
    return {
        "trial_active": True,
        "days_remaining": days_left,
        "hours_remaining": hours_left,
        "trial_ends_at": trial_sub.period_end.isoformat(),
        "can_access_features": True,
    }
```

---

## IX. Frontend Trial Status Display

### Header/Sidebar Banner (if trial active)

```html
<div class="trial-banner trial-banner-active">
  <span class="trial-icon">⏳</span>
  <span class="trial-text">Free trial: <strong>6 days remaining</strong></span>
  <a href="/pricing" class="trial-link">Upgrade now</a>
</div>
```

### Header/Sidebar Banner (if trial expired)

```html
<div class="trial-banner trial-banner-expired">
  <span class="trial-icon">⚠️</span>
  <span class="trial-text">Trial expired. <strong>Upgrade to continue.</strong></span>
  <a href="/pricing" class="trial-link btn-primary">Upgrade</a>
</div>
```

### CSS

```css
.trial-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 0.9rem;
  margin-bottom: 16px;
}

.trial-banner-active {
  background: #fff8e1;
  border: 1px solid #ffe0b2;
  color: #f57c00;
}

.trial-banner-expired {
  background: #ffebee;
  border: 1px solid #ef9a9a;
  color: #c62828;
}

.trial-link {
  margin-left: auto;
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
}

.trial-link.btn-primary {
  background: var(--color-terracotta);
  color: white;
  padding: 6px 12px;
  border-radius: 6px;
  text-decoration: none;
}
```

---

## X. Success Criteria

**Backend:**
- [ ] Migration creates/updates subscriptions table (plan, status columns)
- [ ] Signup automatically creates trial subscription (7-day period)
- [ ] GET /api/v1/billing/trial-status returns correct status
- [ ] Protected endpoints check trial/subscription, return 403 if expired
- [ ] Paid subscription overrides trial (user gets full access)
- [ ] Trial calculation accurate to hours

**Frontend:**
- [ ] Trial banner displays on dashboard (active/expired states)
- [ ] Trial status updates on page load
- [ ] 403 errors redirect to pricing page with upgrade CTA
- [ ] Countdown shows correct days remaining

**Integration:**
- [ ] Signup → trial created → dashboard accessible
- [ ] Day 7 → trial active, can access features
- [ ] Day 8 → trial inactive, 403 error, upgrade prompt
- [ ] User upgrades → access restored immediately

---

## XI. Questions & Decisions

1. **Trial subscription row in DB?**
   - ✅ YES: Create subscription row with status="trial" on signup (easier to track, consistent with paid)

2. **What if user had trial, it expired, then they want to extend?**
   - Future feature: Contact support for extension or immediate upgrade

3. **Multiple users, shared account?**
   - Out of scope: Trial per account (per email), not per shop/user

4. **Trial notifications (email warnings)?**
   - Out of scope for MVP: Implement in Phase 2

5. **Grace period after trial expires?**
   - No: Hard cutoff at day 8. User must upgrade immediately.

---

**Timeline:** 2 days (B7-B10, F7)  
**Ready to implement:** Yes

---

**Document:** todo_trial_period.md  
**Status:** ⏳ Ready for implementation  
**Created:** 2026-05-17

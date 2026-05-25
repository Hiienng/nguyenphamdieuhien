# Onboarding Setup Flow — EtseeMate
**Architect:** Claude  
**Created:** 2026-05-17  
**Status:** Plan Ready for Approval  
**Timeline:** 1 week (Week 2 June)  

---

## I. Executive Summary

After user signup (`POST /api/v1/auth/register`), they are redirected to an **onboarding wizard** that captures:

1. **Product Category** — What do they sell? (max 3 products, choose once forever)
2. **Seller Location** — Which country? (choose once forever)

**Why this matters to user:**
- ⚠️ **Critical Notice:** "These settings determine your market intelligence data. You can only set them once. Choose wisely."
- Different product categories → different market trends, competitors, benchmark data
- Seller location → market reach, pricing context, currency
- EtseeMate's ML models and crawlers are optimized per product category

**Data Impact:**
- Product category → triggers appropriate crawlers in `etsy_star_engine` for that category (e.g., "onesie" → crawl onesie listings, competitors, trends)
- Seller location → geographic market scope, currency, shipping context
- Once set → **immutable** (user cannot change; would require admin intervention)
- Max 3 products per account in MVP (constraint stored in schema)

---

## II. User Journey

```
Login successful (POST /api/v1/auth/register → access_token)
  ↓
Redirect to /app.html?onboarding=true
  ↓
Check: Has user completed onboarding? (user.onboarding_completed flag)
  ↓
If NO → Show onboarding wizard (modal/full-page flow)
  ├── Step 1: "What products do you sell?" (multi-select, max 3)
  │   - Product dropdown (Etsy categories: onesies, blankets, sweaters, crown, etc.)
  │   - Show: "This helps us fetch market trends for YOUR products"
  │   - Validation: min 1, max 3 products selected
  │
  ├── Step 2: "Where are you based?" (single-select)
  │   - Country dropdown (US, UK, CA, AU, DE, etc.)
  │   - Show: "Determines your market scope and currency"
  │   - Validation: country required
  │
  ├── Step 3: "Important Notice" (read-only)
  │   - "Your product category and location are FINAL."
  │   - "They determine the market intelligence we provide."
  │   - "You cannot change them after this step."
  │   - Checkbox: "I understand and agree"
  │   - Validation: checkbox must be checked
  │
  └── Step 4: Submit → POST /api/v1/auth/onboarding/setup
         Response: { success, user { id, onboarding_completed, product_categories, seller_location } }
         Redirect: /app.html (dashboard, no onboarding flag)
  
If YES → Show dashboard directly
```

---

## III. API Design

### New Endpoint: POST `/api/v1/auth/onboarding/setup`

**Auth:** Required (Bearer token from signup)

**Request Body:**
```json
{
  "product_categories": ["onesie", "blanket"],  // Array of strings, length 1-3
  "seller_location": "US"                        // ISO country code (US, UK, CA, etc.)
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "user": {
    "id": "uuid",
    "email": "seller@example.com",
    "full_name": "Sarah",
    "onboarding_completed": true,
    "product_categories": ["onesie", "blanket"],
    "seller_location": "US",
    "created_at": "2026-05-17T10:00:00Z"
  }
}
```

**Errors:**
- **400 Bad Request:** Missing or invalid product_categories / seller_location
  ```json
  { "detail": "product_categories must have 1-3 items" }
  ```
- **400 Bad Request:** Invalid product category
  ```json
  { "detail": "Invalid product category: 'xyz'. Valid: onesie, blanket, sweater, ..." }
  ```
- **400 Bad Request:** Onboarding already completed
  ```json
  { "detail": "Onboarding already completed for this user" }
  ```
- **401 Unauthorized:** No valid JWT token

---

## IV. Database Schema Changes

### New Columns on `users` Table

| Column | Type | Constraint | Ghi chú |
|---|---|---|---|
| onboarding_completed | BOOLEAN | NOT NULL, default=false | Initial setup done? |
| product_categories | JSON | NOT NULL, default=[] | Array of product type strings |
| seller_location | VARCHAR(8) | nullable | ISO country code (US, UK, CA, AU, etc.) |
| last_onboarding_update | TIMESTAMPTZ | nullable | Track 90-day update window |

**Migration (Alembic):**
```python
# migration_file: add_onboarding_fields_to_users.py
def upgrade():
    op.add_column('users', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('product_categories', sa.JSON(), nullable=True))
    op.add_column('users', sa.Column('seller_location', sa.String(8), nullable=True))

def downgrade():
    op.drop_column('users', 'seller_location')
    op.drop_column('users', 'product_categories')
    op.drop_column('users', 'onboarding_completed')
```

---

## V. Frontend Tasks (F6: Onboarding Wizard)

### F6: Onboarding Wizard UI

**Create:** `frontend/js/onboarding.js` + `frontend/css/onboarding.css`

**Features:**
- [ ] 4-step wizard modal/flow
- [ ] Step 1: Product selector (multi-select checkbox, max 3, validate on change)
  - Fetch from `GET /api/v1/references/product-categories`
  - Display as checkboxes: user can select 1-3
  - Show count: "Selected: X/3"
  - Disable 4th+ selections
  - Note: "One account per email. You can update your products after 90 days."
- [ ] Step 2: Country dropdown (pre-populated list)
- [ ] Step 3: Confirmation notice with checkbox agreement
  - Highlight: "One account per email address"
  - Highlight: "You can update your products once after 90 days from today"
  - Clear warning: "After that, these settings lock for another 90 days"
  - Checkbox: "I understand my product choices are important"
- [ ] Step 4: Submit button (disabled until all steps valid)
- [ ] Progress bar (step 1/4, 2/4, 3/4, 4/4)
- [ ] Back/Next buttons (except Step 1)
- [ ] Error handling (invalid input, API errors)
- [ ] Success → redirect to /app.html (dashboard)
- [ ] Auto-check onboarding status on page load (if completed, skip wizard)

**Product Categories (Dynamic Enum):**
- Frontend: Fetch from `GET /api/v1/references/product-categories` → Dynamic list from market data
- Or: Pre-populate from analysis of etsy_star_engine output (recommend dynamic fetch)
- Must include: "other" option for unlisted products
- User selects via checkboxes (max 3)

**Countries (All countries supported):**
- Use standard ISO 3166-1 alpha-2 country codes
- Fetch from `GET /api/v1/references/countries` or pre-populate with full ISO list
- No geographic restriction — user can choose any country

**Integration Points:**
- After login success → check `GET /api/v1/auth/me` for `onboarding_completed` flag
- If false → show onboarding modal
- On submit → `POST /api/v1/auth/onboarding/setup` with product_categories + seller_location
- On success → set localStorage flag + redirect to dashboard

---

## VI. Backend Tasks (B4-B5: Onboarding Endpoint)

### B4: Database Migration

- [ ] Create Alembic migration to add 3 new columns to users table
- [ ] Columns: onboarding_completed (BOOL), product_categories (JSON), seller_location (VARCHAR(8))
- [ ] Run migration locally + test with Postman

### B5: Product Categories Reference Endpoint

- [ ] Create route: `GET /api/v1/references/product-categories` (public, no auth required)
- [ ] Response: `{ categories: [ { id, name, label }, ... ], includes_other: true }`
- [ ] Data source: Extract from `market_listing.product_type` DISTINCT values (via etsy_star_engine data)
- [ ] Always include: "other" category for unlisted products
- [ ] Cache: Refresh daily or on-demand, frontend can cache aggressively

**Example Response:**
```json
{
  "categories": [
    { "id": "onesie", "name": "onesie", "label": "Custom Onesie" },
    { "id": "blanket", "name": "blanket", "label": "Personalized Blanket" },
    { "id": "sweater", "name": "sweater", "label": "Custom Sweater" },
    { "id": "crown", "name": "crown", "label": "Birthday Crown" },
    { "id": "shirt", "name": "shirt", "label": "Custom Shirt" },
    { "id": "other", "name": "other", "label": "Other Products" }
  ]
}
```

### B6: Onboarding Endpoint Implementation

- [ ] Create route: `POST /api/v1/auth/onboarding/setup` in `backend/app/api/routes/auth.py` (and/or in references route)
- [ ] Validation:
  - JWT token required (get current user)
  - Check `user.onboarding_completed` — if true, return 400 "Already completed"
  - Validate product_categories: array, 1-3 items, all in enum list
  - Validate seller_location: string, valid ISO country code
- [ ] Update user record:
  - Set `onboarding_completed = true`
  - Set `product_categories = [list]` (as JSON array)
  - Set `seller_location = 'US'`
- [ ] Return 201 with updated user object (include onboarding fields)
- [ ] Error handling: 400 for validation, 401 for no auth, 403 for already completed

**Pseudo-code:**
```python
@router.post("/onboarding/setup", status_code=201)
async def setup_onboarding(
    request: OnboardingSetupRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    # Check if initial setup (not completed) OR update window (90+ days since last update)
    now = datetime.utcnow()
    can_update_initial = not current_user.onboarding_completed
    can_update_after_90d = (
        current_user.onboarding_completed 
        and current_user.last_onboarding_update is not None 
        and (now - current_user.last_onboarding_update).days >= 90
    )
    
    if not (can_update_initial or can_update_after_90d):
        raise HTTPException(status_code=400, detail="Onboarding locked. Can update after 90 days.")
    
    # Fetch valid product categories from references service
    valid_categories = await get_valid_product_categories(db)
    
    # Validate product_categories
    if not (1 <= len(request.product_categories) <= 3):
        raise HTTPException(status_code=400, detail="Must select 1-3 products")
    if not all(cat in valid_categories for cat in request.product_categories):
        raise HTTPException(status_code=400, detail="Invalid product category")
    
    # Validate seller_location (ISO country code)
    if not is_valid_country_code(request.seller_location):
        raise HTTPException(status_code=400, detail="Invalid country code")
    
    # Update user
    current_user.onboarding_completed = True
    current_user.product_categories = request.product_categories
    current_user.seller_location = request.seller_location
    current_user.last_onboarding_update = now
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    
    return {
        "success": True,
        "user": UserSchema.model_validate(current_user)
    }
```

---

## VII. Integration with Landing Page

### Updated Auth Flow

1. User clicks "Try Free" on landing page
2. Signup modal opens → enter email + password → `POST /api/v1/auth/register`
3. Backend returns access_token + user with `onboarding_completed=false`
4. Frontend redirects to `/app.html?onboarding=true`
5. Dashboard loads onboarding wizard automatically
6. User completes: product_categories + seller_location
7. Submit → `POST /api/v1/auth/onboarding/setup`
8. Success → redirect to actual dashboard (with market data for their products)

---

## VIII. Key Design Decisions

### ✅ Product Categories & Location Policy

**Initial Setup (One-Time at Signup):**
1. **Data Foundation:** Product category determines which market crawlers run, which competitor data we pull, which ML models we use
2. **Scope Control:** Prevents user confusion ("Why is my onesie data different after I changed to sweater?")
3. **System Simplicity:** Crawlers don't need to handle mid-stream category changes
4. **Analytics:** Baseline is consistent — can measure user growth per category

**Update Window (After 90 Days):**
- User can update product_categories + seller_location **ONE TIME** after 90 days from account creation
- After update: Locked for another 90 days
- Logic: `if (now - created_at >= 90 days) AND (now - last_onboarding_update >= 90 days) → allow update`
- New columns: `last_onboarding_update` (timestamp, tracks last update time)

**Account Creation Constraint:**
- One user email = one account lifetime
- Cannot create duplicate accounts (email unique index enforces)
- If user loses access: contact support for account recovery
- Note in flow: "One account per email. Choose your products wisely — you can update after 90 days."

### ⚠️ User Notification Strategy

**During Onboarding:**
- Step 3 has a clear warning: "These settings determine your market intelligence. **FINAL.** Cannot change later."
- Checkbox: "I understand and agree"
- Toast/banner after completion: "✅ Your market setup is locked in. We're now crawling YOUR products!"

**In Dashboard (after onboarding):**
- Display current products + location in account settings
- Show "Locked" badge: "⚠️ These cannot be changed"
- If user needs different products → contact support (future feature: account migration)

### 📊 Future Expansion (Phase 2)

- Support multi-shop: Different shop = different onboarding
- Product updates: After 90 days, user can request one update (or pay)
- Category expansion: As EtseeMate adds new categories (jewelry, prints, etc.)

---

## IX. Scope & Dependencies

### In Scope (Week 2)
✅ Onboarding wizard UI (F6)
✅ Database migration (B4)
✅ Backend endpoint (B5)
✅ Integration with login flow
✅ Immutability enforcement

### Out of Scope (Defer to Phase 2)
❌ Support for changing products/location
❌ Multi-shop onboarding
❌ API rate limiting per location
❌ Market crawling triggering (crawler ops handled separately)

---

## X. Success Criteria

**Frontend (F6):**
- [ ] Onboarding modal loads after login
- [ ] Product selector: multi-select, max 3, validate count
- [ ] Country dropdown populated, required
- [ ] Warning notice clear and prominent
- [ ] Submit button disabled until all valid
- [ ] Error messages friendly and actionable
- [ ] Redirect to dashboard on success
- [ ] No console errors

**Backend (B4-B5-B6):**
- [ ] Migration runs without errors (4 new columns: onboarding_completed, product_categories, seller_location, last_onboarding_update)
- [ ] GET /api/v1/references/product-categories returns dynamic list from market data
- [ ] POST /api/v1/auth/onboarding/setup validates: product_categories (1-3 items), seller_location (ISO code)
- [ ] Returns 201 with user object including onboarding fields
- [ ] Enforces 90-day update window: rejects update if < 90 days since last_onboarding_update
- [ ] Tested with Postman: valid inputs, invalid categories, update window enforcement

**Integration:**
- [ ] Signup → onboarding → dashboard flow seamless
- [ ] GET /api/v1/auth/me includes onboarding_completed flag
- [ ] Onboarding status persists (refresh page → no re-prompt if completed)

---

## XI. File Map

**Frontend:**
- `frontend/js/onboarding.js` — Wizard logic, API calls, form handling
- `frontend/css/onboarding.css` — Styling per DESIGN.md (Parchment bg, Terracotta button)
- Update `frontend/js/landing.js` → After successful login, check onboarding status

**Backend:**
- `backend/alembic/versions/[timestamp]_add_onboarding_fields.py` — Migration (4 new columns)
- `backend/app/schemas/auth.py` → Add `OnboardingSetupRequest`, `OnboardingSetupResponse`, `ProductCategory` schemas
- `backend/app/models/user.py` → Add 4 new columns (ORM): onboarding_completed, product_categories, seller_location, last_onboarding_update
- `backend/app/api/routes/auth.py` → Add `POST /onboarding/setup` endpoint
- `backend/app/api/routes/references.py` → Add `GET /product-categories` endpoint (or extend existing)
- `backend/.env.example` → No new env vars needed
- `backend/app/services/references_service.py` → Helper to fetch valid product categories from market_listing

---

## XII. Task Assignments

| Component | Agent | Tasks | Timeline |
|-----------|-------|-------|----------|
| **Frontend** | Haiku | F6: Wizard UI, form validation, API integration (GET categories + POST setup) | 2 days |
| **Backend** | Sonnet | B4: Alembic migration (4 columns), B5: Product categories endpoint (GET /references/product-categories), B6: Onboarding setup endpoint (POST /auth/onboarding/setup with 90-day logic) | 2 days |
| **Testing** | Both | Integration: signup → onboarding (dynamic category list + country selection) → 90-day update validation → dashboard | 1 day |

---

## XIII. Approval Checklist

- [ ] Product categories enum appropriate for MVP (8 categories sufficient?)
- [ ] Seller location: Countries list covers target markets?
- [ ] Immutability acceptable to user (no option to change later in MVP)?
- [ ] Warning language clear enough for non-technical users?
- [ ] Should we pre-populate country from IP geolocation, or let user choose?
- [ ] Database: JSON array or comma-separated string for product_categories?

---

## Ready for Approval ✅

**Next Step:** User approves plan → Backend Agent runs B4-B5, Frontend Agent runs F6 → Integration testing

**Outstanding Questions:**
1. Are the 8 product categories sufficient, or should we add more?
2. Which countries should we support in the location dropdown? (Recommend: US, UK, CA, AU, DE, FR, NL, ES, IT, JP, CN, SG, IN)
3. Is immutability acceptable, or should we allow one-time update after 30 days?
4. Should we auto-fill seller location from IP geolocation, or require manual selection?
5. Should product_categories be stored as JSON array or comma-separated string in DB?

---

**Document:** todo_onboarding_setup.md  
**Status:** ⏳ Awaiting user approval  
**Created:** 2026-05-17

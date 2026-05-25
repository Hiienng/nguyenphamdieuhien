# Landing Page Build Plan — EtseeMate

**Architect:** Claude  
**Created:** 2026-05-17  
**Status:** Plan Ready for Approval  
**Timeline:** 3 weeks (Week 1-3 June)  

---

## I. Architecture Overview

### Design Approach
```
Landing page (index.html) — Single-page, no JS framework
├── Hero section (call-to-action)
├── Problem/Solution cards (3 columns)
├── Live demo carousel
├── How it works (3-step)
├── Pricing table
├── Testimonials
├── FAQ accordion
├── Footer
└── Tech: Vanilla HTML/CSS/JS (follow DESIGN.md)
```

### Key Principles
1. **Follow DESIGN.md tokens** — All colors, fonts, spacing from design system
2. **No external frameworks** — Pure HTML/CSS/JS per project rules
3. **Responsive mobile-first** — 480px / 768px / 992px breakpoints
4. **Maximize parallelization** — Frontend can build UI while backend works on auth/payment

---

## II. Data Flow & Dependencies

```
Frontend (Landing Page)
├── Static HTML/CSS/JS (no dynamic data needed)
├── CTA buttons → modal form (email + password)
├── Form submit → POST /api/v1/auth/register (backend)
└── Backend returns JWT + redirect to /app.html

Backend (Auth)
├── POST /api/v1/auth/register
├── POST /api/v1/auth/login  
├── JWT token generation
├── Cookie session management
└── DB: users, subscriptions, credits tables
```

**Parallel Work:**
- **Frontend Agent:** Build landing page UI (independent of backend logic)
- **Backend Agent:** Implement auth endpoints + Stripe integration
- **Mock API:** Frontend can stub `/api/v1/auth/register` call locally during development

---

## III. File Structure & Tasks

### New Files to Create

```
frontend/
├── index.html                    ← Landing page (MAIN)
├── css/landing.css              ← Landing page styles
├── js/landing.js                ← Landing page interactions (modal, form)
└── lib/
    └── api-client.js            ← Fetch wrapper (shared with app.html)

backend/
├── app/api/routes/auth.py       ← Auth endpoints (already exists, needs landing page support)
├── app/services/auth_service.py ← Auth business logic
└── app/models/user.py           ← User ORM model
```

### Task Breakdown

#### Frontend Tasks

**Task F1: HTML Structure**
- [ ] Create `frontend/index.html` with semantic structure
- [ ] 9 main sections (hero, problem/solution, demo, how-it-works, pricing, testimonials, FAQ, CTA, footer)
- [ ] Navigation bar (sticky) with logo + nav links + "Try Free" CTA
- [ ] Accessibility: alt text, heading hierarchy, ARIA labels

**Task F2: CSS Design System Integration**
- [ ] Create `frontend/css/landing.css`
- [ ] Import design tokens from `docs/DESIGN.md` (CSS variables)
- [ ] Color palette: Parchment, Ivory, Terracotta, Near Black, Olive, Stone
- [ ] Typography: Georgia serif (headlines), system sans (body)
- [ ] Spacing: 8px scale (8, 16, 24, 32, 40, 48, 80, 120px)
- [ ] Components: buttons, cards, grid, shadows, radius
- [ ] Responsive: mobile (< 480px), tablet (480–768px), desktop (> 992px)

**Task F3: Interactive Elements**
- [ ] Create `frontend/js/landing.js`
- [ ] "Try Free" CTA button → open modal form
- [ ] Email + password form validation
- [ ] Form submit → POST /api/v1/auth/register (mock endpoint)
- [ ] Loading state + error handling
- [ ] Success: redirect to /app.html (authenticated)
- [ ] Carousel: auto-play + manual navigation for demo section
- [ ] Accordion: FAQ expand/collapse

**Task F4: Demo Section (Carousel)**
- [ ] 3 slides: market trends, thumbnail score, competitor landscape
- [ ] Use real EtseeMate dashboard screenshots (anonymized)
- [ ] Annotations overlay with text
- [ ] Auto-play (5s per slide), manual prev/next

**Task F5: Responsive & Polish**
- [ ] Test on mobile, tablet, desktop
- [ ] Mobile menu (hamburger) if needed
- [ ] Cross-browser testing (Chrome, Safari, Firefox)
- [ ] Performance optimization (lazy load images, minify CSS/JS)
- [ ] Accessibility audit (axe, WAVE)

---

#### Backend Tasks

**Task B1: Auth Routes (Already Exists, Needs Polish)**
- [ ] POST /api/v1/auth/register — public endpoint
  - Request: `{ email, password, full_name }`
  - Response: `{ access_token, refresh_token, user: { id, email, full_name } }`
  - Error handling: duplicate email, validation
  
- [ ] POST /api/v1/auth/login — public endpoint
  - Request: `{ email, password }`
  - Response: `{ access_token, refresh_token }`
  
- [ ] POST /api/v1/auth/logout — auth required
  - Clear JWT cookie
  
- [ ] GET /api/v1/auth/me — auth required
  - Return user profile + subscription status + credit balance

**Task B2: User Model & Database**
- [ ] Ensure `users` table exists with: id, email, password_hash, full_name, is_active, created_at
- [ ] Hash passwords with bcrypt (never store plain text)
- [ ] Create unique index on email

**Task B3: JWT Token Management**
- [ ] JWT secret from env var `JWT_SECRET_KEY`
- [ ] Access token expiry: 15 minutes (from `JWT_ACCESS_EXPIRE_MIN`)
- [ ] Refresh token (cookie-based) expiry: 30 days
- [ ] Auth middleware: validate JWT on protected routes

**Task B4: Stripe Integration (for future, but prepare)**
- [ ] POST /api/v1/billing/subscribe — create Stripe checkout session
- [ ] Webhook handler for Stripe events (checkout.session.completed)
- [ ] Activate user subscription on payment success

---

#### DevOps/Testing Tasks

**Task D1: Local Development**
- [ ] Test landing page locally at http://localhost:8000 (Frontend serving from Render)
- [ ] Mock backend auth endpoints (stub response) during FE dev
- [ ] Test real backend auth after implementation

**Task D2: Deployment**
- [ ] Update `render.yaml` to serve `frontend/index.html` at `/` (root)
- [ ] Ensure `/app.html` still serves at `/app`
- [ ] CORS config: allow signup/login requests from localhost + production domain

**Task D3: Analytics & Monitoring**
- [ ] GA4 setup: track page views, signup clicks, signup completions
- [ ] Error tracking: Sentry or similar for JS errors
- [ ] Conversion funnel: visitor → signup → login → app

---

## IV. API Contracts (Mock for Frontend Development)

### POST /api/v1/auth/register
```json
Request:
{
  "email": "seller@etsy.com",
  "password": "SecurePassword123",
  "full_name": "Sarah"
}

Response (Success 201):
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "user": {
    "id": "uuid",
    "email": "seller@etsy.com",
    "full_name": "Sarah"
  }
}

Response (Error 400):
{
  "detail": "Email already registered"
}
```

### POST /api/v1/auth/login
```json
Request:
{
  "email": "seller@etsy.com",
  "password": "SecurePassword123"
}

Response (Success 200):
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "user": { ... }
}
```

---

## V. Design System Integration Checklist

**Frontend must follow `docs/DESIGN.md`:**

- [ ] Colors: Use CSS variables (`--parchment`, `--terracotta`, `--olive`, etc.)
- [ ] Typography: 
  - Headlines: Georgia, 500 weight, 1.1–1.2 line-height
  - Body: System sans, 400 weight, 1.6 line-height
- [ ] Spacing: 8px scale (no magic numbers)
- [ ] Buttons: 
  - Primary (CTA): Terracotta bg, ivory text, 12px radius
  - Secondary: Warm sand bg, charcoal text, 8px radius
- [ ] Cards: 1px border (border-cream), ring shadow, 8px radius
- [ ] Forms: 12px border-radius inputs, focus ring (terracotta)
- [ ] Responsive breakpoints: 480px, 768px, 992px

---

## VI. Task Dependencies & Parallelization

```
Frontend (Can start immediately)
├── F1: HTML structure (no backend needed) ✓ Independent
├── F2: CSS design system (read DESIGN.md only) ✓ Independent
├── F3: JS interactions (mock API locally) ✓ Can mock backend
├── F4: Demo carousel (use static screenshots) ✓ Independent
└── F5: Responsive & polish (final phase)

Backend (Parallel work)
├── B1: Auth routes (GET existing routes) ✓ Can start now
├── B2: User model (should exist already) ✓ Verify
├── B3: JWT management (configure env vars) ✓ Can start
└── B4: Stripe prep (for Phase 2, can defer)

Sync points:
- After B1 complete → F3 removes mock, uses real API
- Before launch → test F3 + B1 integration
```

---

## VII. Scope & Non-Scope

### In Scope (Phase 1 Launch)
✅ Landing page (9 sections)  
✅ Auth signup/login forms  
✅ User table + JWT tokens  
✅ Responsive design  
✅ GA4 analytics  

### Out of Scope (Defer to Phase 2)
❌ Stripe subscription (will implement after MVP)  
❌ Multi-language support  
❌ Email verification (can add later)  
❌ Social login (OAuth)  
❌ Dark mode toggle  

---

## VIII. Success Criteria

**Frontend:**
- [ ] Landing page loads < 2s on 4G
- [ ] Mobile layout perfect (no horizontal scroll)
- [ ] Form validation working (client-side)
- [ ] Lighthouse score > 90
- [ ] No console errors/warnings

**Backend:**
- [ ] /api/v1/auth/register creates user in DB
- [ ] /api/v1/auth/login returns valid JWT
- [ ] Auth middleware protects /api/v1/performance/*
- [ ] Password hashing working (bcrypt)
- [ ] CORS allows cross-origin requests

**Integration:**
- [ ] Signup flow: landing → modal → backend → /app.html
- [ ] GA4 tracks: page view, signup click, signup success
- [ ] Error messages display in modal (friendly copy)

---

## IX. Team Assignments

| Role | Agent | Tasks |
|---|---|---|
| **Frontend** | Claude (Haiku) | F1, F2, F3, F4, F5 |
| **Backend** | Claude (Sonnet) | B1, B2, B3, B4 |
| **DevOps** | Claude (Sonnet) | D1, D2, D3 |
| **Architect** | Claude (Opus) | Sync, Planning, Decisions |

---

## X. Timeline & Milestones

### Week 1 (June 2–8, 2026)
**Frontend Sprint:**
- [ ] F1, F2, F3 complete
- [ ] Landing page locally testable
- [ ] Mock auth endpoints working

**Backend Sprint:**
- [ ] B1, B2, B3 complete
- [ ] Auth endpoints tested with Postman
- [ ] JWT tokens valid

**Sync:** Integrate frontend + backend, test signup flow

### Week 2 (June 9–15, 2026)
**Polish & Testing:**
- [ ] F4, F5 complete
- [ ] Responsive testing (mobile/tablet/desktop)
- [ ] Error handling + edge cases
- [ ] Analytics setup

**Backend:**
- [ ] B4 prepare (Stripe integration skeleton)
- [ ] Env vars configured for production

**Sync:** Full integration test, bug fixes

### Week 3 (June 16–22, 2026)
**Launch Prep:**
- [ ] Final QA
- [ ] Performance optimization
- [ ] Deployment config (Render)

**Launch Day:**
- [ ] Deploy to production
- [ ] Smoke tests
- [ ] Share on Reddit/Facebook/email

---

## XI. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Auth endpoints not ready | FE blocked | Mock API early, FE can proceed |
| Mobile responsiveness fails | Low score, bounces | Test on device early (week 1) |
| Stripe integration complex | Payment flow broken | Defer Stripe to Phase 2, use simple payment for MVP |
| Performance slow on 4G | Users leave | Optimize images, lazy load, minify assets |
| CORS issues in production | Cross-origin fails | Test CORS locally, configure Render CORS |

---

## XII. Approval Checklist

- [ ] Scope accepted (all 9 sections, no deferral requests)
- [ ] Timeline realistic (3 weeks)
- [ ] Task assignments clear
- [ ] Design system understood (frontend knows DESIGN.md rules)
- [ ] API contracts approved (backend knows auth endpoints)
- [ ] Success criteria measurable
- [ ] Team ready to start

---

## Ready for Approval ✅

**Next step:** User approves plan → Frontend & Backend agents start in parallel

**Questions for user:**
1. Are the 9 sections in the landing page sufficient? (hero, problem/solution, demo, how-it-works, pricing, testimonials, FAQ, CTA, footer)
2. Should we include email verification before first login, or defer?
3. Should Stripe be fully integrated at launch, or stub payment for MVP?
4. Any additional analytics events beyond GA4 (page view, signup click, signup success)?

---

**Document:** todo_landing_page.md  
**Status:** ⏳ Awaiting user approval  
**Created:** 2026-05-17

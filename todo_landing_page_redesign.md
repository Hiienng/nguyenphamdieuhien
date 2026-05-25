# Todo — Landing Page Redesign [COMPLETED]
> Agent: @frontend
> Knowledge: .claude/knowledge/occasional/landing_page_patterns.md (đọc vì task "landing page")
> Files: frontend/index.html, frontend/css/landing.css

---

## Task 1 — Kiểm tra CSS vars trong landing.css [Frontend]
- [ ] Mở `frontend/css/landing.css`, kiểm tra `:root` đã có các vars sau chưa:
  - `--parchment: #f5f4ed`
  - `--ivory: #faf9f5`
  - `--terracotta: #c96442`
  - `--coral: #d97757`
  - `--near-black: #141413`
  - `--charcoal: #4d4c48`
  - `--stone: #87867f`
  - `--warm-silver: #b0aea5`
  - `--border-cream: #f0eee6`
  - `--border-warm: #e8e6dc`
  - `--font-serif: Georgia, 'Times New Roman', serif`
  - `--font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`
- [ ] Bổ sung bất kỳ var nào còn thiếu vào `:root`
- [ ] Thêm classes mới vào cuối file nếu chưa có:
  `.lp-eyebrow`, `.lp-trust-line`, `.lp-card-marker`, `.lp-card-contrast`,
  `.lp-metrics-row`, `.lp-metric`, `.lp-metric-number`, `.lp-metric-label`,
  `.lp-pricing-card--featured`, `.lp-pricing-badge`, `.lp-steps`, `.lp-step`,
  `.lp-step-number`, `.lp-step-content`, `.lp-section-sub`

---

## Task 2 — Rewrite Section 1: Hero [Frontend]
File: `frontend/index.html`

Thay thế toàn bộ `<section class="lp-hero">` hiện tại bằng skeleton sau:

**Yêu cầu:**
- [ ] Eyebrow: `"For Etsy sellers running ads"` — class `lp-eyebrow`
- [ ] Headline: `"Know which listings are<br>actually making money."` — class `lp-hero-headline`, font-family serif
- [ ] Sub: một câu, không list, không bullet — class `lp-hero-sub`
- [ ] CTA button: `"See Your Market Data Free"` — class `lp-btn-primary`
- [ ] Trust line ngay dưới CTA: `"No credit card · Free 14 days · Cancel anytime"` — class `lp-trust-line`
- [ ] Visual placeholder div bên phải (2-col grid) — class `lp-hero-visual`, bên trong đặt placeholder img với alt text rõ ràng
- [ ] **Không dùng emoji, không bullet list trong hero**

---

## Task 3 — Rewrite Section 2: Problem [Frontend]
File: `frontend/index.html`

Thay thế section `<section class="lp-section lp-problem">` hiện tại:

- [ ] Section heading đổi thành: `"Sound familiar?"`
- [ ] Mỗi card: xóa `<div class="lp-card-icon">📈</div>` → thay bằng `<div class="lp-card-marker">01</div>`
- [ ] Giữ nguyên pain headline (có thể điều chỉnh ngôn ngữ theo seller voice)
- [ ] Thêm `<p class="lp-card-contrast">` sau body text mỗi card — đây là phần "EtseeMate instead..." viết bằng terracotta color
- [ ] **Không dùng emoji**

3 cards và contrast text:
- Card 01 "My trend data is always late" → contrast: `"EtseeMate crawls Etsy weekly — you see what's trending now, not last quarter."`
- Card 02 "I can't tell which ads are worth it" → contrast: `"EtseeMate shows ROAS, CTR, and spend per listing — know exactly what to scale and what to pause."`
- Card 03 "Redesigning thumbnails is a gamble" → contrast: `"Upload your thumbnail → get an AI score before you publish. Launch confident the first time."`

---

## Task 4 — Thêm mới Section 3: Social Proof [Frontend]
File: `frontend/index.html`

Chèn section mới SAU `.lp-problem`, TRƯỚC section How It Works:

- [ ] Background `#141413` (dark), text `#faf9f5`
- [ ] 3 metric blocks ngang hàng — class `lp-metrics-row`
- [ ] Mỗi metric: số lớn serif coral + label nhỏ warm silver
  - `"7 days"` → `"Market data freshness vs. 6–8 weeks for eRank"`
  - `"3 steps"` → `"Upload report → see ROAS by listing → decide"`
  - `"0 guessing"` → `"Every decision backed by your actual Etsy data"`

---

## Task 5 — Rewrite Section 4: How It Works [Frontend]
File: `frontend/index.html`

Thay thế section How It Works hiện tại (nếu có) hoặc tạo mới:

- [ ] Section heading: `"From zero to insight in 3 steps"`
- [ ] Dùng `<ol class="lp-steps">` thay vì card grid
- [ ] 3 steps theo activation path (không phải feature list):
  1. `"Connect your Etsy Ads report"` — "Download from Etsy Ads Manager. Upload it — takes 30 seconds."
  2. `"See ROAS by listing — instantly"` — "Know which listings are profitable, breaking even, or draining your budget."
  3. `"Make your next move with confidence"` — "Scale what's working. Fix what's not. Time your next launch with market trends."

---

## Task 6 — Refactor Section 5: Pricing [Frontend]
File: `frontend/index.html`

- [ ] Thêm `lp-pricing-card--featured` vào Pro card (card giữa)
- [ ] Thêm `<div class="lp-pricing-badge">Most popular</div>` bên trong Pro card
- [ ] Thêm trust line dưới CTA của Pro card: `"No credit card required"`
- [ ] Đảm bảo Free card dùng `lp-btn-secondary`, Pro card dùng `lp-btn-primary`
- [ ] CSS: `.lp-pricing-card--featured` → background `#141413`, color `#faf9f5`, transform scale(1.03)
- [ ] CSS: `.lp-pricing-badge` → background `var(--terracotta)`, color white, position absolute, font-size 11px

---

## Task 7 — Thêm mới Section 6: FAQ [Frontend]
File: `frontend/index.html`

Thêm section FAQ trước `<footer>` (hoặc cuối trang):

- [ ] Section heading: `"Questions"`
- [ ] 5 Q&A dạng accordion đơn giản (click toggle) hoặc static list
- [ ] 5 objections từ seller perspective:
  1. Q: "Is this different from eRank?" → A: "Yes — eRank shows keyword volume from 6–8 weeks ago. EtseeMate shows what's trending on Etsy *this week*, plus ROAS analytics eRank doesn't have."
  2. Q: "Do I need to connect my Etsy account?" → A: "No. Just download your Ads report CSV from Etsy and upload it. No OAuth, no permissions needed."
  3. Q: "What if I only have a few listings?" → A: "EtseeMate works for any shop size. Even 3 listings — knowing which one has the best ROAS changes how you allocate ad spend."
  4. Q: "Is my data safe?" → A: "Your data stays in your account. We don't share or sell it. Connection strings and reports are stored encrypted."
  5. Q: "Can I cancel anytime?" → A: "Yes. No contracts, no cancellation fees. Cancel from your account settings in under 30 seconds."

---

## Checklist cuối trước khi done
- [ ] Không có emoji nào trong body copy của tất cả sections
- [ ] Không có hex color hardcode trong HTML (chỉ dùng CSS vars hoặc class)
- [ ] Mỗi section chỉ có 1 primary CTA
- [ ] `openAuthModal('register')` còn nguyên trên tất cả CTA buttons
- [ ] Nav và footer không bị thay đổi

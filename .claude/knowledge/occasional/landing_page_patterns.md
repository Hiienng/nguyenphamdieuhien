# Landing Page Patterns — EtseeMate
> Đọc file này khi build hoặc refactor landing page (frontend/index.html).
> Mọi pattern ở đây đã được calibrate theo AIDA framework + Warm Editorial visual style.
> Không đọc khi task chỉ sửa app portal (EtseeMate.html) hoặc logic JS.

---

## Visual Style — Warm Editorial (Claude/Anthropic-inspired)

**Không phải copy Anthropic** — mà áp dụng cùng design philosophy:
- Background: `#f5f4ed` (parchment) — không dùng pure white hay gray lạnh
- Headline font: serif (`Georgia` fallback cho `Anthropic Serif`) — tight line-height 1.1–1.2
- Body/UI font: sans-serif — không mix serif vào label, caption, button
- Brand accent: `#c96442` (terracotta) — CTA button, highlight, link color
- Neutral text: `#4d4c48` (warm charcoal) — không dùng `#000000` hay `#333`
- No gradients, no shadows nặng — depth qua surface tone và spacing
- No emoji trong body copy — dùng inline SVG icon hoặc text-based marker

**References (cùng tone):**
- anthropic.com/claude — parchment canvas, serif headline, organic illustrations
- notion.so — clean section alternation, large serif hero
- linear.app — negative space, confident typography

---

## SECTION 1 — Hero (Above the Fold)

**Rule:** 1 pain-point headline → 1 sub → 1 primary CTA. Không list tính năng.

**Headline formula:** "[Outcome seller muốn] — without [frustration họ đang có]"

**Good examples:**
```
"Know which listings are actually making money — before you waste more ad spend."
"See what Etsy buyers want this week. Not last quarter."
"Stop guessing on thumbnails. Score them before you upload."
```

**Bad examples (đang dùng):**
```
❌ "Catch Etsy trends real-time. Design thumbnails smart. Optimize confident."
   → 3 tính năng, không phải 1 pain point. Không có "you" — không kết nối.
```

**HTML Skeleton:**
```html
<section class="lp-hero">
  <div class="lp-container lp-hero-inner">

    <!-- Text side -->
    <div class="lp-hero-text">
      <p class="lp-eyebrow">For Etsy sellers running ads</p>
      <h1 class="lp-hero-headline">
        Know which listings are<br>actually making money.
      </h1>
      <p class="lp-hero-sub">
        Real-time market data, AI thumbnail scoring, and competitor
        pricing — so every decision you make on Etsy is backed by data.
      </p>
      <div class="lp-hero-ctas">
        <button class="lp-btn-primary" onclick="openAuthModal('register')">
          See Your Market Data Free
        </button>
        <span class="lp-trust-line">No credit card · Free 14 days · Cancel anytime</span>
      </div>
    </div>

    <!-- Visual side: dashboard screenshot or illustration -->
    <div class="lp-hero-visual">
      <img src="/assets/dashboard-preview.png"
           alt="EtseeMate dashboard showing ROAS by listing"
           class="lp-hero-img" />
    </div>

  </div>
</section>
```

**CSS notes:**
- `.lp-hero`: `background: var(--parchment)`, min-height 100vh không cần, đủ padding-top 120px
- `.lp-hero-inner`: 2-column grid `1fr 1fr`, gap 64px. Mobile: stack, visual xuống dưới
- `.lp-hero-headline`: `font-family: var(--font-serif)`, size 52–64px, line-height 1.1, color `#141413`
- `.lp-eyebrow`: uppercase, letter-spacing 0.1em, size 12px, color `#87867f` (stone gray)
- `.lp-trust-line`: size 13px, color `#87867f`, margin-top 12px — không bold

---

## SECTION 2 — Problem (3 Pain Points)

**Rule:** Nói bằng ngôn ngữ seller, không ngôn ngữ feature. Mỗi card = 1 pain → 1 contrast với EtseeMate.

**Format chuẩn mỗi card:**
```
[Pain headline — seller self-identifies]
[1-2 câu mô tả frustration cụ thể]
[contrast: "EtseeMate instead..."]
[link: See how →]
```

**HTML Skeleton:**
```html
<section class="lp-section lp-problem">
  <div class="lp-container">
    <h2 class="lp-section-heading">Sound familiar?</h2>

    <div class="lp-card-grid lp-card-grid-3">

      <article class="lp-card">
        <div class="lp-card-marker">01</div>
        <h3 class="lp-card-heading">"My trend data is always late"</h3>
        <p class="lp-card-body">
          eRank keyword data is 6–8 weeks old. By the time you launch,
          the trend already peaked and competitors grabbed the demand.
        </p>
        <p class="lp-card-contrast">
          EtseeMate crawls Etsy weekly — you see what's trending now,
          not what was trending last quarter.
        </p>
      </article>

      <article class="lp-card">
        <div class="lp-card-marker">02</div>
        <h3 class="lp-card-heading">"I can't tell which ads are worth it"</h3>
        <p class="lp-card-body">
          You're spending on ads but Etsy's dashboard doesn't show
          ROAS by listing. You're optimizing blind.
        </p>
        <p class="lp-card-contrast">
          EtseeMate shows ROAS, CTR, and spend per listing — so you
          know exactly which ones to scale and which to pause.
        </p>
      </article>

      <article class="lp-card">
        <div class="lp-card-marker">03</div>
        <h3 class="lp-card-heading">"Redesigning thumbnails is a gamble"</h3>
        <p class="lp-card-body">
          You redesign 2–3 times before something converts. Each
          attempt costs hours and delays your launch.
        </p>
        <p class="lp-card-contrast">
          Upload your thumbnail → get an AI score before you publish.
          Launch confident the first time.
        </p>
      </article>

    </div>
  </div>
</section>
```

**CSS notes:**
- `.lp-card-marker`: `font-family: var(--font-serif)`, size 32px, color `#e8e6dc` (border warm) — decorative number, very light
- `.lp-card`: `background: var(--ivory)` (`#faf9f5`), border `1px solid #f0eee6`, border-radius 8px, padding 32px
- `.lp-card-contrast`: color `#c96442` (terracotta), font-size 14px, margin-top 16px — the "after" state

---

## SECTION 3 — Social Proof

**Rule:** Số liệu cụ thể > generic testimonial. Nếu chưa có data thật → dùng product metrics, không fabricate user quotes.

**Hierarchy:**
1. 3 metric numbers (large, serif) — "what the product delivers"
2. Testimonial quotes (nếu có) — với tên shop thật, không "a seller"
3. Logo bar (nếu applicable)

**HTML Skeleton:**
```html
<section class="lp-section lp-social-proof" style="background: #141413; color: #faf9f5;">
  <div class="lp-container">

    <div class="lp-metrics-row">
      <div class="lp-metric">
        <span class="lp-metric-number">7 days</span>
        <span class="lp-metric-label">Market data freshness vs. 6–8 weeks for eRank</span>
      </div>
      <div class="lp-metric">
        <span class="lp-metric-number">3 steps</span>
        <span class="lp-metric-label">Upload report → see ROAS by listing → decide</span>
      </div>
      <div class="lp-metric">
        <span class="lp-metric-number">0 guessing</span>
        <span class="lp-metric-label">Every action backed by your actual Etsy data</span>
      </div>
    </div>

  </div>
</section>
```

**CSS notes:**
- Dark section (`#141413`) alternates with parchment sections — creates visual rhythm
- `.lp-metric-number`: `font-family: var(--font-serif)`, size 48–64px, color `#d97757` (coral accent on dark)
- `.lp-metric-label`: size 14px, color `#b0aea5` (warm silver), max-width 200px

---

## SECTION 4 — How It Works (3 Steps)

**Rule:** Activation path, không feature list. User phải thấy mình trong từng bước.

```html
<section class="lp-section lp-how-it-works">
  <div class="lp-container">
    <h2 class="lp-section-heading">From zero to insight in 3 steps</h2>

    <ol class="lp-steps">
      <li class="lp-step">
        <span class="lp-step-number">1</span>
        <div class="lp-step-content">
          <h3>Connect your Etsy Ads report</h3>
          <p>Download your report from Etsy Ads Manager. Upload it — takes 30 seconds.</p>
        </div>
      </li>
      <li class="lp-step">
        <span class="lp-step-number">2</span>
        <div class="lp-step-content">
          <h3>See ROAS by listing — instantly</h3>
          <p>EtseeMate parses your data and shows which listings are profitable,
             which are breaking even, and which are draining your budget.</p>
        </div>
      </li>
      <li class="lp-step">
        <span class="lp-step-number">3</span>
        <div class="lp-step-content">
          <h3>Make your next move with confidence</h3>
          <p>Scale what's working. Fix what's not. Use market trends to
             time your next launch.</p>
        </div>
      </li>
    </ol>

  </div>
</section>
```

---

## SECTION 5 — Pricing

**Rule:** 3 tiers max. Most popular tier highlighted. CTA = action, không "Choose plan".

```html
<section class="lp-section lp-pricing" id="pricing">
  <div class="lp-container">
    <h2 class="lp-section-heading">Simple pricing</h2>
    <p class="lp-section-sub">Start free. Upgrade when you're ready.</p>

    <div class="lp-card-grid lp-card-grid-3">

      <article class="lp-pricing-card">
        <h3 class="lp-pricing-tier">Free</h3>
        <div class="lp-pricing-price"><span class="lp-price-num">$0</span>/mo</div>
        <ul class="lp-pricing-features">
          <li>Market trend overview</li>
          <li>5 thumbnail scores/month</li>
          <li>1 report import</li>
        </ul>
        <button class="lp-btn-secondary" onclick="openAuthModal('register')">
          Get started free
        </button>
      </article>

      <article class="lp-pricing-card lp-pricing-card--featured">
        <div class="lp-pricing-badge">Most popular</div>
        <h3 class="lp-pricing-tier">Pro</h3>
        <div class="lp-pricing-price"><span class="lp-price-num">$29</span>/mo</div>
        <ul class="lp-pricing-features">
          <li>Full market intelligence</li>
          <li>Unlimited thumbnail scoring</li>
          <li>Unlimited report imports</li>
          <li>ROAS & spend analytics</li>
          <li>Competitor pricing tracker</li>
        </ul>
        <button class="lp-btn-primary" onclick="openAuthModal('register')">
          Start 14-day free trial
        </button>
        <p class="lp-trust-line">No credit card required</p>
      </article>

      <article class="lp-pricing-card">
        <h3 class="lp-pricing-tier">Credits</h3>
        <div class="lp-pricing-price"><span class="lp-price-num">$9</span>/10 credits</div>
        <ul class="lp-pricing-features">
          <li>Pay per thumbnail eval</li>
          <li>No subscription needed</li>
          <li>Credits never expire</li>
        </ul>
        <button class="lp-btn-secondary" onclick="openAuthModal('register')">
          Buy credits
        </button>
      </article>

    </div>
  </div>
</section>
```

**CSS notes:**
- `.lp-pricing-card--featured`: `background: #141413`, `color: #faf9f5`, scale transform 1.03 — visual hierarchy
- `.lp-pricing-badge`: terracotta background, white text, position absolute top-left, size 12px

---

## SECTION 6 — FAQ

**Rule:** Max 5 câu. Câu hỏi phải là objection thật, không "What is EtseeMate?".

Top objections để address:
1. "Is this different from eRank?" → Yes — explain data freshness + ROAS
2. "Do I need to give Etsy access?" → No — you just upload a CSV
3. "What if I only have 5 listings?" → Works for any size shop
4. "Is my data safe?" → Address Vn-Compliant data handling briefly
5. "Can I cancel anytime?" → Yes, no contract

---

## Typography Hierarchy — Quick Reference

| Element | Font | Size | Weight | Color |
|---|---|---|---|---|
| Hero headline | Serif | 52–64px | 400 | `#141413` |
| Section heading | Serif | 36–42px | 400 | `#141413` |
| Card heading | Sans | 18–20px | 600 | `#141413` |
| Body text | Sans | 15–16px | 400 | `#4d4c48` |
| Caption/meta | Sans | 12–13px | 400 | `#87867f` |
| CTA button | Sans | 15px | 500 | `#ffffff` on `#c96442` |
| Eyebrow | Sans | 11–12px | 500 uppercase | `#87867f` |

---

## Anti-patterns — Không làm

- **Emoji trong body copy** — dùng số (`01 02 03`) hoặc inline SVG thay thế
- **Bullet list trong hero** — hero chỉ có 1 headline + 1 sub
- **Generic CTA** — "Get Started", "Learn More" → phải nói rõ outcome: "See Your Market Data Free"
- **Cool grays** — không dùng `#666`, `#999`, `#ccc` — mọi neutral phải warm-toned
- **Multiple primary CTAs trên 1 section** — mỗi section chỉ có 1 primary action
- **Justify text alignment** — dùng left-align cho body, center chỉ cho metric/hero

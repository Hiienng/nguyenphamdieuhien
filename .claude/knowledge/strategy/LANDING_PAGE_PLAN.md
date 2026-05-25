# EtseeMate Landing Page — Xây Dựng Plan

**Tài liệu:** Landing Page Architecture & Build Plan  
**Cập nhật:** 2026-05-17  
**Scope:** Phase 1 MVP landing page  
**Timeline:** 2-3 tuần

---

## I. Landing Page Strategy

### Goal
Convert: Cold visitor (Reddit/Facebook) → Free tier signup  
**Target conversion rate:** 8-12% (visitors → free signups)

### User Journey
```
Cold visitor (heard from Reddit/friend)
    ↓
Land on homepage
    ↓
See: Real-time trends + Thumbnail score + Competitor analysis
    ↓
"This solves my pain point" → Click "Try Free"
    ↓
See pricing (Free tier = real value)
    ↓
Signup (email + password)
    ↓
Dashboard: Connect Etsy, see market data
```

### Key Principle
**Show, don't tell.** Real data, real examples, real seller testimonials.

---

## II. Landing Page Structure

### **Section 0: Navigation Bar (Sticky)**
```
Logo: EtseeMate (left)
Nav links: Features | Pricing | Blog (center, optional)
CTA button: "Try Free" (right, terracotta)
```

**Design Notes:**
- Height: 60px
- Background: Parchment (#f5f4ed)
- Border-bottom: 1px solid border-cream
- Logo font: serif (Georgia)
- CTA: terracotta button, always visible

---

### **Section 1: Hero**

#### Copy:
```
Headline (64px serif, tight 1.1 line-height):
"Catch Etsy trends real-time.
Design thumbnails smart.
Optimize confident."

Subheader (20px sans, 1.6 line-height, olive #5e5d59):
"See what's trending on Etsy today (not 2 months ago).
Score your thumbnails before upload.
Know competitor pricing & strategy."

CTA Button (18px, terracotta):
"See Market Data Free"

Secondary CTA (smaller, link):
"How it works?" → scroll to demo
```

#### Design:
- Background: Parchment gradient (vertical, light→lighter)
- Content max-width: 800px, centered
- Padding: 120px (top) 40px (sides)
- Image/graphic: (right side, optional) animated dashboard preview or market trend chart

#### Visual:
- Hero image: Real EtseeMate dashboard screenshot (anonymized seller data)
  - Show: Market trends chart + thumbnail score card + competitor list
  - Dimensions: 400px height, rounded corners 12px, subtle shadow

---

### **Section 2: Problem + Solution**

#### 3-Column Layout: Pain → EtseeMate Solution

**Column 1: Real-Time Trends**
```
Icon: 📈 Trend graph
Headline (25px serif): "Trends move fast"
Copy (16px sans, 1.6 line-height):
"eRank keyword data: 2 months old
When you launch, trend already peaked.

EtseeMate market data: Updated weekly
Launch when demand is hot → +20-30% revenue"

CTA: "See market trends" (link to demo)
```

**Column 2: Thumbnail Quality**
```
Icon: 🎨 Image frame
Headline (25px serif): "Design thumbnail smart"
Copy (16px sans, 1.6 line-height):
"Redesign 2-3 times before it sells
= waste time + money + opportunity loss

EtseeMate ML score:
Upload → Score 0-1 → Recommendations
→ Launch confident first time"

CTA: "Score your thumbnail" (link to form)
```

**Column 3: Competitor Context**
```
Icon: ⚔️ Swords
Headline (25px serif): "Know your enemy"
Copy (16px sans, 1.6 line-height):
"Competitor pricing $28, rating 4.8
You: $35, rating 4.2
Gap = pricing or quality?

EtseeMate auto-pulls top-10 competitors
Inform: pricing strategy, improvement priorities"

CTA: "See competitors" (link to demo)
```

#### Design:
- Background: Ivory (#faf9f5)
- 3-column grid (responsive: 1 column mobile)
- Card shadows: ring shadow (0 0 0 1px border-warm)
- Spacing: 20px gap between columns
- Padding: 80px vertical, 40px horizontal
- Max-width container: 1200px

---

### **Section 3: Live Demo**

#### Copy:
```
Headline (52px serif, centered):
"See it in action"

Demo type: Interactive slider / carousel
- Slide 1: Market trends dashboard
  - Screenshot: Chart showing "Custom name onesie: 300→450 listings (last 7 days)"
  - Annotation: "EtseeMate detects trend jump, alerts seller"
  
- Slide 2: Thumbnail scoring
  - Screenshot: Thumbnail card with score 5.2/10
  - Annotation: "Recommendations: Add contrast, center subject, reduce text"
  
- Slide 3: Competitor landscape
  - Screenshot: Top-10 competitors table (price, rating, reviews)
  - Annotation: "Pricing gap identified: $28 vs Your $35"

CTA (after carousel): "Try it yourself" (signup button)
```

#### Design:
- Background: Parchment
- Screenshots: Real EtseeMate UI, rounded 12px, shadow
- Carousel: Auto-play (5 sec per slide), manual navigation
- Text overlay: Semi-transparent dark background, white text
- Padding: 80px vertical

---

### **Section 4: How It Works (3-Step)**

#### Copy:
```
Headline (52px serif, centered):
"Three steps to market clarity"

Step 1: Connect
Icon: 🔗
Copy (16px):
"Link your Etsy shop
EtseeMate reads public market data
(No need seller dashboard access)"
Time: "30 seconds"

Step 2: Explore
Icon: 🔍
Copy (16px):
"Check: Market trends per category
Thumbnail scores per product
Competitor pricing & strategy"
Time: "2-5 minutes"

Step 3: Act
Icon: ✅
Copy (16px):
"Launch smart: right time + right design + right price
Monitor: market saturation, competitor moves
Optimize: based on real data"
Time: "Ongoing"
```

#### Design:
- Background: Deep dark / Near black (#141413) with ivory text
- 3 circles (step numbers): Terracotta background, 60px diameter
- Vertical flow: step-icon → headline → copy → time
- Padding: 80px vertical, 40px horizontal
- CTA at bottom: "Start free" button (large, white text on terracotta)

---

### **Section 5: Pricing**

#### Copy:
```
Headline (52px serif, centered):
"Simple, transparent pricing"

Free Tier:
$0/month (forever)
- Market trends (weekly data)
- Competitor top-10 per category
- Thumbnail ML score (3 evaluations/month)
- 1 listing tracked
- Basic dashboard

→ "Try Free" button (terracotta)

Paid Tier:
$12/month (or $99/year, 25% off)
- Everything in Free
- Historical market trends (3-month lookback)
- Thumbnail unlimited evals
- Competitor deeper analysis
- Multi-listing tracking (5 listings)
- Market trend alerts
- Email support

→ "Start Paid" button (secondary, warm sand)

Note (small, 12px):
"No credit card required for free tier.
Cancel anytime.
Free tier never expires."
```

#### Design:
- Background: Parchment
- 2-column pricing cards (side-by-side, responsive stacked)
- Free card: Ivory background, border-cream border
- Paid card: Slightly elevated (shadow), highlight "most popular" badge (terracotta)
- Padding: 80px vertical, 40px horizontal
- Comparison table (optional): "What's included" detailed breakdown

---

### **Section 6: Social Proof (Testimonials)**

#### Content:
```
Headline (52px serif, centered):
"Sellers trust EtseeMate"

Testimonial 1:
Quote: "Caught trend 'custom name onesie' 3 weeks early.
Launched while demand was hot.
+50% sales first month."
Author: Sarah, 5-shop dropshipper
Avatar: (placeholder user icon)
Rating: ⭐⭐⭐⭐⭐

Testimonial 2:
Quote: "Thumbnail score 4.5 → redesigned → score 7.8 → CTR +35%
EtseeMate saved me from uploading a dud."
Author: Mike, solo seller
Avatar: (placeholder user icon)
Rating: ⭐⭐⭐⭐⭐

Testimonial 3:
Quote: "Competitor pricing data changed how I price.
Found $5 gap vs market avg.
Lowered price, ROAS improved."
Author: Lisa, vintage shop
Avatar: (placeholder user icon)
Rating: ⭐⭐⭐⭐⭐
```

#### Design:
- Background: Deep dark (#141413), ivory text
- 3-column grid (responsive stacked)
- Quote icon (large, terracotta, faded)
- Author: small avatar + name + shop type
- Cards: bordered, subtle shadow
- Padding: 80px vertical, 40px horizontal

---

### **Section 7: FAQ**

#### Copy:
```
Headline (52px serif, centered):
"Common questions"

Q1: "Etsy market data public, tại sao phải pay?"
A: "Public ≠ organized. EtseeMate crawls, analyzes, alerts automatically.
You save 3-5 hours/week manual research.
Plus: Thumbnail scoring + competitive analysis = EtseeMate unique."

Q2: "EtseeMate có cần Etsy dashboard access không?"
A: "No. EtseeMate reads public market data (Etsy search results).
Free tier never needs seller dashboard."

Q3: "Thumbnail score accurate không?"
A: "ML model trained on 50K+ bestseller thumbnails (rating 4.8+).
Score = probability thumbnail matches bestseller pattern.
Try free tier, upload thumbnail, judge yourself."

Q4: "Can I cancel anytime?"
A: "Yes. Monthly subscription, cancel anytime.
Free tier never expires."

Q5: "Multi-shop support when?"
A: "Roadmap Q4 2026. Currently: 1 shop per account.
Join waitlist for multi-shop beta."
```

#### Design:
- Background: Parchment
- Accordion layout (click to expand)
- Q: 18px bold sans, charcoal
- A: 16px sans, olive
- Padding: 80px vertical, 40px horizontal
- Max-width: 800px, centered

---

### **Section 8: CTA Footer**

#### Copy:
```
Headline (52px serif, centered):
"Ready to catch trends?"

Copy (18px sans, olive, centered):
"Join 100+ sellers using EtseeMate.
Start free today, no credit card."

CTA Button (large, 18px, terracotta):
"See Market Data Free"

Secondary: "Read blog" (link) | "Watch demo" (video link)
```

#### Design:
- Background: Terracotta gradient (top→bottom)
- Text: Ivory
- Button: White text, hover opacity change
- Padding: 100px vertical, 40px horizontal

---

### **Section 9: Footer**

#### Content:
```
Left column:
Logo
"EtseeMate: Market intelligence for Etsy sellers"

Center column:
Links: Home | Blog | Privacy | Terms | Contact

Right column:
Social: Twitter | Reddit | Email
Newsletter signup: "Get market trends" (email input)

Bottom:
"© 2026 EtseeMate. Catch trends. Design smart."
```

#### Design:
- Background: Deep dark (#141413), ivory text
- 3-column flex layout (responsive stacked)
- Link color: Terracotta
- Font: 14px sans
- Padding: 60px vertical, 40px horizontal

---

## III. Technical Implementation

### Stack
- **Frontend:** Vanilla HTML/CSS/JS (as per project rules)
- **Design system:** Follow DESIGN.md (parchment bg, terracotta CTA, warm neutrals)
- **Components:** Reusable CSS classes (button, card, grid, typography)
- **Responsive:** Mobile-first, breakpoints at 480px / 768px / 992px

### Key Pages
1. `/` (homepage) — full landing page
2. `/pricing` (optional, can be section on homepage)
3. `/faq` (optional, can be section on homepage)

### Features to Build
- [ ] Sticky navbar with CTA
- [ ] Hero with gradient background
- [ ] 3-column problem/solution cards
- [ ] Carousel/slider for demos
- [ ] Pricing cards with highlight
- [ ] Testimonial cards grid
- [ ] Accordion FAQ
- [ ] Form modal for "Try Free" CTA
- [ ] Responsive design (mobile, tablet, desktop)

### Sign-up Flow
```
User clicks "Try Free"
↓
Modal popup: Email + Password form
↓
Backend: Create account, send verification email
↓
Redirect: /dashboard (show "Connect Etsy" wizard)
↓
User connects Etsy (OAuth or manual)
↓
Dashboard: Show market data, thumbnail score form
```

---

## IV. Copy Guidelines

### Tone
- **Helpful, confident, not hype**
  - ✅ "eRank data 2 months old → you launch when trend peaked"
  - ❌ "eRank is garbage, EtseeMate is the BEST tool ever"

- **Specific, not generic**
  - ✅ "+20-30% revenue from catching trend 3 weeks early"
  - ❌ "Improve your sales dramatically"

- **User-centric, not feature-centric**
  - ✅ "Design thumbnail that sells → EtseeMate scores it"
  - ❌ "ML-powered thumbnail evaluation engine"

### Language
- **Tiếng Anh (professional)** for homepage
- **Tiếng Việt (supportive)** for onboarding wizard

### CTAs
- Primary: "Try Free" / "See Market Data Free" (curiosity-driven)
- Secondary: "Learn more" / "See competitors" (education-driven)
- Avoid: "Sign up" / "Register" (too transactional)

---

## V. Design Specifications

### Color Palette (from DESIGN.md)
```
Primary background: Parchment (#f5f4ed)
Card background: Ivory (#faf9f5)
Dark sections: Near Black (#141413)
Brand CTA: Terracotta (#c96442)
Text primary: Near Black (#141413)
Text secondary: Olive (#5e5d59)
Border: Border Cream (#f0eee6)
```

### Typography
```
Headlines: Georgia serif, 500 weight
- Hero: 64px, line-height 1.1
- Section: 52px, line-height 1.2
- Subsection: 25px, line-height 1.2

Body: System sans-serif
- Large: 20px, line-height 1.6
- Standard: 16px, line-height 1.6
- Small: 14px, line-height 1.5
```

### Spacing
```
Section vertical padding: 80-120px
Card padding: 24-32px
Grid gap: 20-24px
Button padding: 12-16px vertical, 20-32px horizontal
Border radius: 8-12px cards, 8px buttons
```

### Shadows
```
Light cards: 0px 0px 0px 1px #f0eee6 (ring shadow)
Medium: 0px 4px 12px rgba(0,0,0,0.05)
Dark cards: 0px 0px 0px 1px #30302e (ring shadow)
```

---

## VI. Build Timeline

### Week 1: Setup + Design System
- [ ] Create HTML structure (semantic, accessibility-first)
- [ ] Build CSS reset + design tokens
- [ ] Create reusable component classes
- [ ] Setup responsive framework

### Week 2: Sections
- [ ] Hero + navbar
- [ ] Problem/solution cards
- [ ] Demo carousel
- [ ] Pricing cards
- [ ] Testimonials
- [ ] FAQ accordion
- [ ] Footer

### Week 3: Polish + Launch
- [ ] Forms integration (email signup, password)
- [ ] Modal/overlay for CTA
- [ ] Responsive testing (mobile, tablet, desktop)
- [ ] Performance optimization
- [ ] Cross-browser testing
- [ ] Analytics setup (GA4)
- [ ] Go live

---

## VII. Launch Checklist

### Pre-Launch
- [ ] Copy finalized and proofread
- [ ] All images/screenshots ready
- [ ] Form validation working
- [ ] Email signup backend ready
- [ ] Analytics configured
- [ ] Meta tags/OG images for sharing

### Day of Launch
- [ ] Deploy to production
- [ ] Smoke test all pages on 3 devices
- [ ] Share on Reddit (r/Etsy, r/EtsySellers)
- [ ] Post on Facebook groups
- [ ] Send to email list (if any)

### Post-Launch
- [ ] Monitor: traffic, signups, conversion rate
- [ ] Gather user feedback
- [ ] Fix bugs within 24 hours
- [ ] Plan improvements based on bounce rate

---

## VIII. Success Metrics

**Week 1-2:**
- Unique visitors: 200+
- Signup conversion: 5-8%

**Month 1:**
- Unique visitors: 500+
- Free signups: 40-50
- Free→paid conversion: >10%

**Month 3:**
- Unique visitors: 1000+
- Free signups: 100+
- Paid subscribers: 20+
- MRR: $240-300

---

## IX. Next Steps

1. **Content finalization** (Confirm copy, testimonials, examples)
2. **Design mockup** (Figma or wireframe)
3. **Development sprint** (2-3 weeks)
4. **Testing & QA** (1 week)
5. **Launch!**

---

**Document Owner:** @frontend / @marketing  
**Created:** 2026-05-17  
**Expected Launch:** 2026-06-07 (3 weeks)

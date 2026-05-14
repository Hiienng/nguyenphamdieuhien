# Business Rules — EtseeMate SaaS
> @product đọc file này trước khi đưa ra khuyến nghị về chiến lược sản phẩm, định giá, hoặc go-to-market.
> Cập nhật lần cuối: 2026-05-13

---

## Core Value Proposition

**"Biết listing nào đang thật sự kiếm tiền — và phải làm gì tiếp theo."**

Seller được phục vụ một vòng lặp hoàn chỉnh mà không tool nào trên thị trường có:

```
Thị trường đang cần gì?          ← market data (crawler)
        ↓
Listing của tôi đang chạy thế nào?   ← ads performance (OCR)
        ↓
Tôi phải làm gì ngay bây giờ?        ← scenario engine (keep/improve/scale)
```

**3 thứ EtseeMate có mà không đối thủ nào có:**

| # | Capability | Tại sao đối thủ không có |
|---|---|---|
| 1 | **Ads ROAS/CTR/CR per listing** | Data chỉ có trong Etsy Ads dashboard — không có API public, không crawl được; EtseeMate lấy qua OCR screenshot do seller upload |
| 2 | **Live market data từ Etsy** | eRank/Marmalead dùng Google Keyword Planner stale 1–2 tháng; EtseeMate crawl trực tiếp Etsy bằng Chrome CDP — data fresh theo tuần |
| 3 | **Scenario engine (keep/improve/scale)** | Toàn bộ thị trường dừng lại ở "đây là số liệu"; EtseeMate nói thêm "đây là việc bạn cần làm" dựa trên ma trận ROAS × CTR × CR |

**Vòng lặp hoàn chỉnh — không tool nào có:**
```
Thị trường đang cần gì?              ← market data (crawler, live)
        ↓
Listing của tôi đang chạy thế nào?  ← ads performance (OCR, per listing)
        ↓
Tôi phải làm gì ngay bây giờ?       ← scenario engine (keep/improve/scale)
```

---

## Mô Hình Kinh Doanh

- **Loại sản phẩm:** SaaS B2B, multi-tenant
- **ICP:** Etsy seller cá nhân / shop nhỏ đang chạy Etsy Ads, cần hiểu ROAS/CTR/CR/CPC để ra quyết định nhanh hơn
- **Positioning anchor:** *"The only Etsy tool that tells you whether your ads are making you money — per listing."*
- **Data hiện tại trong DB** là của 1 seller pilot (reference account) — không phải product scope cuối
- **Target giai đoạn 1:** 20 user trả tiền

---

## Competitive Landscape

| Tool | Giá | Focus | Điểm yếu chính |
|---|---|---|---|
| eRank | Free / $9.99/mo | Keyword SEO | Grading không tương quan sales thực; data stale 1–2 tháng từ Google KP |
| Marmalead | $19/mo | Keyword SEO | Không free tier; chỉ keyword, hoàn toàn thiếu ads analytics |
| Sale Samurai | $9.99/mo | Keyword + bulk tag | Trial 3 ngày quá ngắn; thiếu ads/ROAS analytics |
| HeyEtsy | $19–$149/mo | Product spy (Chrome ext) | Không có keyword SEO, không có ads analytics; ít traction trên review độc lập |
| EverBee | Free / $7.99–$29.99/mo | Product research | Yếu về keyword depth; không có ads analytics |
| EtsyHunt | Free / $3.99–$59.99/mo | Product database lớn | Không có historical data; không có ads analytics |
| Alura | Free / $19.99–$49.99/mo | SEO + Pinterest automation | Đắt; không có ads performance data |
| Koalanda | $5.99–$11.99/mo | Keyword tool giá rẻ | User base nhỏ, data hạn chế |

**Nhận xét quan trọng:** Toàn bộ thị trường đang cạnh tranh trên keyword SEO và product research. **Không một tool nào** có ads performance data (ROAS/CTR/CR per listing) + scenario engine. Đây là khoảng trống thực sự.

**Gap EtseeMate khai thác:** Ads performance per listing + live market data (không stale) + action recommendation — không ai có cả 3.

---

## Pricing Model

- **Mô hình:** Freemium + Subscription
- **Free tier:** 1 shop, data lookback 30 ngày — đủ thấy giá trị, không đủ vận hành chuyên nghiệp
- **Paid tier:** $12–$15/mo — full history, AI optimization, ads analytics đầy đủ, scenario engine
- **Annual plan:** ~$99–$108/năm (discount ~25%) để tăng retention
- **Không dùng:** Trial ngắn 3–7 ngày (quá ngắn để thấy trend data có ý nghĩa)
- **Ngưỡng kháng cự:** Trên $19/mo gặp resistance mạnh từ solo seller

---

## Feature Priority (MVP → Retain)

**Phải có để charge tiền (paid tier):**
1. Ads ROAS/CTR/CR dashboard per listing — differentiator duy nhất trên thị trường
2. Keyword performance per listing — kết hợp với ads data tạo ra insight thực
3. AI listing optimization (title/tags/description) — high perceived value, low cost

**Giữ chân user (paid tier):**
4. Scenario-based action recommendation (keep/improve/scale) — "so what" layer
5. Market trend research — lý do subscribe ongoing, không chỉ dùng 1 lần

**Defer sau MVP:**
- Multi-shop management → sau khi prove value single-shop
- Internal listing detail crawler → optional, seller tự quyết định rủi ro

---

## Hạ Tầng — Thiết Kế cho 20 User

**Chi phí theo mốc:**
| Mốc | Stack | Chi phí/tháng |
|---|---|---|
| 0 user (hiện tại) | Render Free + Neon Free | $0 |
| 1–5 user trả tiền | Render Starter + Neon Free | $7 |
| 10–20 user | Render Starter + Neon Free (hoặc Launch $19 nếu storage hết) | $7–26 |

**Breakeven:** 1 user trả $10 đã cover Render Starter. Neon Free (~0.5GB) đủ đến ~$100+/tháng revenue.

**ImageKit Free** (20GB bandwidth) đủ cho 20 user upload screenshot OCR — không cần mua.

**Market crawler:** Chạy trên Mac local với Chrome CDP — chi phí ~$0, đây là moat kỹ thuật, không thay đổi kiến trúc này cho đến 200+ user.

---

## Multi-Tenant Architecture

**Data công ty (shared):** `market.*` schema
- `market_listing`, `market_listing_details`, `market_listing_reviews`, `market_shop`
- `keyword_rank_snapshot`, `scenarios_rules`, `threshold_configs`
- Crawler Mac ghi vào đây, không bao giờ động vào data seller

**Data seller (per-tenant):** `app.*` schema + `tenant_id` + PostgreSQL RLS
- `listings`, `listing_report`, `keyword_report`
- `manual_listing_report`, `manual_keyword_report`, `import_batch`
- RLS enforce isolation ở tầng DB — không thể leak chéo dù thiếu WHERE clause

**1 Neon DB, 2 schema** — tách biệt rõ ràng về quyền ghi, không cần DB vật lý riêng đến giai đoạn enterprise.

---

## Acquisition & GTM

Kênh ưu tiên CAC thấp nhất cho team nhỏ:
1. **Reddit** (r/Etsy, r/EtsySellers) — value-first, không pitch thẳng
2. **Facebook Groups** Etsy seller — post "show don't sell" với screenshot insight thực
3. **YouTube SEO** — tutorial "how to analyze Etsy ads", EtseeMate là answer
4. **SEO blog** — "eRank grade sai vì sao", "so sánh eRank vs EtseeMate"
5. **Referral** — "give 1 month free, get 1 month free" (referred user LTV cao hơn 16%)

Không ưu tiên paid social giai đoạn đầu.

---

## Competitive Positioning

- **Khác eRank/Marmalead/Sale Samurai:** Họ focus keyword SEO — EtseeMate focus ads performance, quyết định ngân sách
- **Khác HeyEtsy/EverBee/EtsyHunt:** Họ focus product spy/research — EtseeMate focus performance listing đang chạy
- **Lợi thế duy nhất:** ROAS/CTR/CR per listing + live market data + scenario engine — không ai có cả 3
- **Không cạnh tranh:** Keyword research volume (eRank đã dominate, không đáng đánh trực diện)
- **Positioning ngắn gọn:** *"Trong khi mọi tool khác cho bạn biết keyword nào tốt, EtseeMate cho bạn biết listing nào đang kiếm tiền và phải làm gì tiếp theo."*

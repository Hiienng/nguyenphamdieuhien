# UX Principles — EtseeMate Frontend
> Đọc file này khi làm task liên quan đến Landing Page, Portal layout, onboarding, customer journey, hoặc thiết kế component mới.
> Không đọc khi task chỉ sửa logic JS hoặc bind data.

---

## 1. AIDA — Landing Page Structure

Mọi landing page đi qua 4 lớp từ trên xuống:

**A — Attention (above the fold)**
- 1 headline nói thẳng vấn đề seller, không nói tính năng
  - ❌ "AI-powered Etsy analytics platform"
  - ✅ "Biết listing nào đang thật sự kiếm tiền — và phải làm gì tiếp theo"
- 1 số liệu hoặc screenshot dashboard thực ngay hero
- Chỉ: headline + sub + 1 CTA — không navigation nặng, không form

**I — Interest (scroll đầu tiên)**
- 3 pain points ngắn bằng ngôn ngữ seller:
  - "Chạy Etsy Ads nhưng không biết listing nào có lãi"
  - "eRank cho A nhưng vẫn không bán — vì họ không đo ROAS"

**D — Desire (giữa trang)**
- Before/After hoặc "Với/Không có EtseeMate"
- Social proof: số liệu cụ thể, không dùng "nhiều seller đã..."
- 3 differentiators từ `business_rules.md`

**A — Action (cuối + sticky)**
- 1 CTA duy nhất: "Dùng thử miễn phí"
- Ngay dưới CTA: "Không cần thẻ tín dụng · Miễn phí 30 ngày · Hủy bất cứ lúc nào"
- Sticky bar xuất hiện sau khi scroll qua hero

---

## 2. Hook Model (Nir Eyal) — Portal & Retention Design

Mỗi session dùng app phải kích hoạt vòng lặp 4 bước để tạo habit:

```
Trigger → Action → Variable Reward → Investment
   ↑                                      |
   └──────────────────────────────────────┘
```

**Trigger**
- *External*: Email "listing X đang drop ROAS", notification "market trend mới"
- *Internal*: Cảm giác lo lắng khi chạy ads mà không biết hiệu quả → seller tự mở app
- **Áp dụng:** Dashboard email digest hàng tuần. Empty state luôn có trigger rõ ràng.

**Action** — phải đơn giản nhất có thể (Fogg: Motivation × Ability)
- Giảm friction tối đa cho activation event: upload báo cáo → xem dashboard
- Không quá 3 click từ login đến insight đầu tiên
- **Áp dụng:** Upload flow tối đa 2 bước. Auto-detect file format.

**Variable Reward** — phần thưởng không đoán trước được tạo ra engagement
- *Reward of the Hunt*: "Listing nào đang có cơ hội scale?" — user muốn khám phá
- *Reward of the Self*: Cảm giác làm chủ data, ra quyết định đúng
- **Áp dụng:** Highlight insight bất ngờ ("Listing này tăng ROAS 40% tuần này"). Không show tất cả — tạo curiosity gap.

**Investment** — user bỏ công sức → tăng giá trị của app với họ
- Upload data → app càng có nhiều history → càng khó bỏ
- Config threshold theo shop riêng → personalized experience
- **Áp dụng:** Sau mỗi action quan trọng, nhắc user về data họ đã tích lũy ("Bạn đã có 3 tháng data — trend analysis giờ chính xác hơn").

---

## 3. Jobs-to-be-Done (JTBD) — Thiết kế giải pháp, không thiết kế tính năng

| Job của seller | Navigation label đúng |
|---|---|
| "Listing nào đang lãi?" | ✅ "Listing nào đang lãi?" — ❌ "Performance Analytics" |
| "Sản phẩm nào đang trending?" | ✅ "Thị trường đang cần gì?" — ❌ "Market Research" |
| "Cải thiện listing này" | ✅ "Cải thiện listing này" — ❌ "AI Optimization" |

**Empty state:** Không để trắng — luôn hướng dẫn job tiếp theo
- ❌ "No data available"
- ✅ "Upload báo cáo Etsy Ads để xem listing nào đang có lãi"

**Activation event quan trọng nhất:** User upload báo cáo và thấy dashboard có data thực. Nếu không đến bước này trong session đầu → churn cao. Mọi onboarding flow phải hướng về đây.

---

## 4. Atomic Design — Kiến trúc Component

Tư duy đồng thời ở 2 cấp: **chi tiết nhỏ nhất** và **hệ thống tổng thể**. Không phải quy trình tuyến tính — là mental model.

```
Atoms → Molecules → Organisms → Templates → Pages
```

**Atoms** — thành phần không thể chia nhỏ hơn
- Button, input, label, icon, color swatch, typography style
- Định nghĩa trong `:root` CSS vars — không hardcode
- *EtseeMate atoms:* `--terracotta` button, score badge, status chip (on/off), caret icon

**Molecules** — atoms kết hợp, 1 nhiệm vụ duy nhất (Single Responsibility)
- Search form = label + input + button
- Metric card = label + số liệu + trend indicator
- *EtseeMate molecules:* ROAS metric card, keyword chip, upload dropzone, score row

**Organisms** — section UI hoàn chỉnh, bắt đầu có bản sắc riêng
- Header = logo + nav + search
- Performance table = filter bar + data table + pagination
- *EtseeMate organisms:* Intelligence Hub chat shell, import pipeline stepper, listing detail accordion, thumbnail eval card

**Templates** — layout xương sống, chưa có nội dung thật
- Định nghĩa vùng, spacing, grid — không phải content
- Test với tiêu đề dài/ngắn, ảnh tỷ lệ khác nhau trước khi fill content
- *EtseeMate templates:* Hub panel layout (2 cột: main + aside), import flow (stepper + preview)

**Pages** — template + nội dung thật, lộ ra edge cases
- Cùng template → test với 0 listing, 1 listing, 500 listings
- Đây là cấp stakeholder hiểu được → demo ở đây

**Rule khi build component mới:**
1. Kiểm tra atom/molecule đã tồn tại chưa — không tạo duplicate
2. Đặt tên theo chức năng, không theo vị trí: `MetricCard` không phải `LeftPanelBox`
3. Khi sửa atom → tự động propagate lên toàn hệ thống — test kỹ trước khi sửa

---

## 5. Baymard Checklist — Dashboard & Portal UX

**Onboarding**
- [ ] Value thấy được ngay lần đầu — không delay sau setup
- [ ] Tối đa 3 bước, mỗi bước ra output có giá trị
- [ ] Demo data realistic nếu chưa có data thật

**Data Table**
- [ ] Số liệu quan trọng nhất: góc trên trái (F-pattern scan)
- [ ] Column header có sort — ROAS và revenue sort mặc định
- [ ] Màu chỉ dùng cho status: đỏ = cần chú ý, xanh = tốt — không dùng trang trí
- [ ] Empty state có action rõ ràng

**Form & Upload**
- [ ] Inline validation — báo lỗi ngay khi blur, không đợi submit
- [ ] Error message nói cách fix: ❌ "Invalid file" → ✅ "File phải là .csv — bạn upload .pdf"
- [ ] Progress indicator cho upload/processing — không spinner vô thời hạn
- [ ] Confirmation trước action không thể undo

**Navigation**
- [ ] Max 2 cấp — không menu lồng 3 cấp
- [ ] Active state rõ ràng — user biết đang ở đâu
- [ ] Breadcrumb cho multi-step flow (upload → extract → review → confirm)

---

## 6. Microcopy Rules

| Element | Sai | Đúng |
|---|---|---|
| Button | "Submit" | "Xem kết quả phân tích" |
| Button | "Upload" | "Upload báo cáo Etsy Ads" |
| Tooltip | "ROAS = Revenue / Spend" | "ROAS < 2.0 = bạn đang lỗ trên listing này" |
| Loading | spinner | "Đang phân tích 47 listings..." |
| Empty | "No data" | "Upload báo cáo để xem listing nào đang lãi" |

# Hướng dẫn sử dụng — GetifyCo Listing Portal

Tài liệu này đi theo đúng **3 nhu cầu của bạn**. Mỗi nhu cầu trả lời 3 câu: **(1) Nhu cầu là gì → (2) Kết quả xem ở đâu → (3) Phải vận hành thế nào để ra kết quả đó.**

> Trước tiên: dữ liệu trong app đến từ **extension** quét trang Etsy Ads rồi ghi thẳng vào **Neon DB của bạn**. App không tự lấy dữ liệu — bạn phải quét định kỳ (vd mỗi tuần). Không có dữ liệu thì không phần nào hiển thị.

---

## Nhu cầu 1 — "Listing / keyword nào đang lời, đang lỗ?"

**▸ Kết quả xem ở đâu**
- Tab **Action Recommendations**: mỗi listing là 1 thẻ, hàng chỉ số ngay đầu thẻ — **ROAS · Rev-Spend($) · Revenue · Spend · Orders · Views · Clicks · CTR · CR · CPC · CPP**.
- **Chấm màu** ở cuối hàng tiêu đề thẻ = lời/lỗ tức thì: 🟢 đang lời · 🟠 cần cải thiện · 🔴 lỗ / nên dừng (rê vào xem chữ).
- Bung thẻ (▸) → bảng **Keywords**: chỉ số của **từng keyword** trong listing.

**▸ Vận hành thế nào**
1. Cài extension (Firefox) → vào *Settings* của extension, dán **Database connection (Neon)** của bạn.
2. Mở trang **Etsy Ads** → extension quét → bấm **Add to DB** (listing) và **Add Keywords to DB** (keyword).
3. Về app → tab **Action Recommendations** → **Refresh** → các thẻ hiện chỉ số.

---

## Nhu cầu 2 — "Keyword nào nên tắt / mở, vì sao?"

**▸ Kết quả xem ở đâu**
- Trong bảng **Keywords** của mỗi listing:
  - cột **Currently** = đang chạy thật (theo lần quét gần nhất).
  - cột **Suggestion** = đề xuất hệ thống: **on** (keyword từng ra doanh thu → nên giữ) / **off** (chưa từng ra doanh thu → nên tắt).
- **🔔 Chuông** trên thẻ = listing này **có keyword đang ON nhưng Suggestion OFF** → có cái nên xem lại để tắt. Bung ra, dòng lệch được tô nền cam.
- Bung **Details** → **Nguyên nhân · Fix Listing · Fix Ads** (vì sao + nên sửa gì).

**▸ Vận hành thế nào**
1. Sau khi đã có dữ liệu (Nhu cầu 1), bung thẻ listing.
2. So cột **Currently** vs **Suggestion**: chỗ `Currently = on` mà `Suggestion = off` chính là keyword đang đốt tiền nhưng chưa ra đơn.
3. Muốn đổi ngưỡng đánh giá lời/lỗ → tab **Configure Thresholds**.

---

## Nhu cầu 3 — "Tôi tắt / mở keyword rồi, việc đó có tác động đến performance không?"

**▸ Kết quả xem ở đâu**
- Trong thẻ listing, phần **Keyword Track change** (biểu đồ):
  - đường mặc định **Rev-Spend($) = Revenue − Spend** theo ngày (đổi chỉ số ở góc phải: Spend / Clicks / ROAS…).
  - **▲ cờ đỏ = mốc bạn đổi keyword** (rê vào xem đổi gì, ngày nào).
  - So đường biểu đồ **trước vs sau cờ** → biết thay đổi có tác động hay không.
- Danh sách thao tác liệt kê bên dưới biểu đồ (✕ để xoá 1 dòng).

**▸ Vận hành thế nào**
1. Khi quyết định tắt/mở 1 keyword → trong bảng Keywords gạt nút **Commit** (on ↔ off). Thao tác này **ghi 1 mốc vào lịch sử** và **cắm cờ ▲** lên biểu đồ tại ngày hôm đó.
2. Qua **Etsy** tắt/mở keyword đó **thật** (Commit chỉ ghi nhận, không tự thao tác trên Etsy).
3. **Tuần sau quét lại dữ liệu** → quay lại **Keyword Track change**, nhìn đường **Rev-Spend($)** quanh cờ ▲ để đánh giá hiệu quả.

> Ví dụ (theo ảnh đính kèm): ngày **8/6** bạn gạt Commit *"Tắt keyword berry first birthday onesie"* → cờ ▲ đỏ hiện tại 8/6. Tuần sau quét lại, so đường Rev-Spend($) trước/sau 8/6 để biết việc tắt keyword đó có cải thiện lãi ròng không.

---

## Lưu ý quan trọng
- Dữ liệu **không real-time** — chỉ đổi **sau mỗi lần quét** bằng extension.
- Tắt/mở trên Etsy → **tuần sau quét mới thấy** cột `Currently` đổi theo.
- **Commit không tự tắt ad trên Etsy** — chỉ ghi nhận quyết định + đo tác động.
- Tìm nhanh: ô **search** (ID/title) · lọc **Product / ROAS / VM** · sắp xếp bằng dropdown + nút ↑/↓.

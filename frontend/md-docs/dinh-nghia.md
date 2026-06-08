# Định nghĩa: Suggestion · Commit · Chuông

## Suggestion (đề xuất bật/tắt keyword)
- **on** — keyword **từng tạo doanh thu (Revenue > 0)** ở bất kỳ listing / kỳ nào trong **toàn bộ lịch sử** → nên **giữ bật**.
- **off** — **chưa từng** tạo doanh thu → nên **cân nhắc tắt** (đang đốt budget mà chưa ra đơn).
- Tính trên **toàn lịch sử**, độc lập với kỳ đang xem.

## Currently (trạng thái hiện tại)
- Trạng thái **on/off thực tế** của keyword tại **lần quét gần nhất** — không phải real-time.

## Commit (nút toggle) — quyết định của bạn
- Là **quyết định**: gạt để xác nhận *"tôi sẽ bật/tắt ad keyword này trên Etsy"*.
- **Mặc định = Currently**.
- Mỗi lần gạt → **ghi 1 dòng vào lịch sử tối ưu** (kèm thời gian) + cắm **cờ ▲** lên biểu đồ **Keyword Track change**.
- **Không tự thao tác trên Etsy** — bạn vẫn phải qua Etsy tắt/mở thật. Commit để **ghi nhận + đo tác động** (so trước/sau cờ).
- **Khi nào bấm:** thường khi `Suggestion = off` nhưng `Currently = on` (keyword đốt tiền, chưa ra đơn) → gạt Commit về **off** để đánh dấu sẽ tắt. Hoặc ngược lại khi muốn bật lại.

## 🔔 Chuông (cảnh báo keyword)
- Hiện trên thẻ listing khi **có keyword đang ON nhưng Suggestion = OFF**.
- Ý nghĩa: listing này có keyword **nên xem lại để tắt**. Bung ra, các dòng lệch được **tô nền cam nhạt**.

## Trạng thái listing (chấm màu cuối hàng)
- 🟢 **Keep Running** — có sales & đang lời.
- 🟠 **Improve** — cần cải thiện.
- 🔴 **Improve / Pause** — cân nhắc cải thiện hoặc tạm dừng.

## Công thức chỉ số
| Chỉ số | Công thức |
|---|---|
| ROAS | Revenue / Spend |
| CTR | Clicks / Views |
| CR | Orders / Clicks |
| CPC | Spend / Clicks |
| CPP | Spend / Orders |
| **Rev-Spend($)** | **Revenue − Spend** (mặc định của biểu đồ Keyword Track change) |

# TODO — Multi-Tenant · FRONTEND
> Generated: 2026-05-14 | Assignee: Frontend Developer Agent
> Depends on: todo_auth_payment_fe.md (auth/login phải hoàn chỉnh trước)

> ⚠️ Đọc `.claude/knowledge/DESIGN.md` trước khi viết bất kỳ CSS/HTML nào.
> Mọi font, màu, spacing phải follow Design System — không được tự suy đoán.
> File chính: `frontend/EtseeMate.html` — KHÔNG tạo lại, KHÔNG xóa

---

## Context
Sau khi multi-tenant BE hoàn thành, mỗi API call đã tự động scoped theo tenant (JWT token chứa tenant_id). Frontend không cần truyền tenant_id thủ công — chỉ cần đảm bảo `Authorization: Bearer <token>` header trên mọi request.

---

### MT-FE-1: Auth Headers trên mọi fetch

- [ ] Kiểm tra tất cả `fetch('/api/v1/...')` trong `EtseeMate.html` và các file JS
- [ ] Đảm bảo 100% các call đều dùng `getAuthHeaders()` — không có call nào thiếu header
- [ ] Đặc biệt kiểm tra: upload form (FormData), multipart requests cũng phải có Authorization header

---

### MT-FE-2: Shop/Tenant Identity Display

- [ ] Sau khi login, gọi `GET /api/v1/auth/me` → lấy `full_name` + subscription status
- [ ] Hiển thị shop name / user name ở header (đã có trong todo_auth_payment_fe — verify đã done)
- [ ] Nếu user là admin (`is_admin=true` trong response me): hiển thị badge "Admin" màu đặc biệt

---

### MT-FE-3: Data Isolation UX

- [ ] Tất cả data hiển thị (listings, reports, keywords) là của tenant đang login — không cần thay đổi UI logic vì BE đã filter
- [ ] Khi switching account (logout → login account khác): clear toàn bộ local state / cached data trong JS variables trước khi fetch lại
- [ ] Thêm loading state khi fetch data lần đầu sau login (tránh flash data cũ)

---

### MT-FE-4: Admin Panel (nếu is_admin=true)

- [ ] Thêm tab hoặc dropdown "Admin" chỉ visible khi `user.is_admin === true`
- [ ] Admin view: `GET /api/v1/admin/tenants` → hiển thị danh sách tenants + stats cơ bản
- [ ] Style: follow Design System, không tạo separate page — dùng modal hoặc side panel

---

## Mock API (để FE có thể dev song song với BE)

Trong khi BE chưa xong MT-BE-4/5, dùng mock data sau:

```javascript
// Mock GET /api/v1/auth/me response
const MOCK_ME = {
  id: "uuid-tenant-1",
  email: "seller@example.com",
  full_name: "My Etsy Shop",
  is_admin: false,
  subscription: { status: "active", period_end: "2026-06-14" },
  credit_balance: 10
};
```

Tất cả data endpoints (`/listings`, `/performance/listings`, etc.) vẫn dùng auth header bình thường — BE sẽ tự filter đúng tenant từ token.

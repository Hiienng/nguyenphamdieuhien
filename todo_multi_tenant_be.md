# TODO — Multi-Tenant · BACKEND
> Generated: 2026-05-14 | Assignee: Backend Developer Agent
> Depends on: todo_auth_payment_be.md (users table phải tồn tại trước)

---

## Chiến lược
Row-level isolation — shared schema. Mỗi tenant = 1 `users.id`. Mọi data table thêm `tenant_id UUID NOT NULL FK → users.id`. Query toàn bộ filter `WHERE tenant_id = :tenant_id`.

`thumbnail_knowledge` là **global shared** — không thêm tenant_id.

---

### MT-BE-1: Migration — Thêm `tenant_id` vào data tables

Tạo migration script `backend/migrations/add_tenant_id.sql` (hoặc Alembic revision):

**Bước 1 — Add column NULLABLE + backfill:**
```sql
-- Tạo seed tenant từ admin account (hoặc hardcoded UUID cho data pilot hiện tại)
-- Backfill tất cả rows hiện có với seed tenant ID
ALTER TABLE listings           ADD COLUMN tenant_id UUID REFERENCES users(id);
ALTER TABLE listing_report     ADD COLUMN tenant_id UUID REFERENCES users(id);
ALTER TABLE keyword_report     ADD COLUMN tenant_id UUID REFERENCES users(id);
ALTER TABLE manual_listing_report   ADD COLUMN tenant_id UUID REFERENCES users(id);
ALTER TABLE manual_keyword_report   ADD COLUMN tenant_id UUID REFERENCES users(id);
ALTER TABLE import_batch       ADD COLUMN tenant_id UUID REFERENCES users(id);
ALTER TABLE threshold_configs  ADD COLUMN tenant_id UUID REFERENCES users(id);
ALTER TABLE scenarios_rules    ADD COLUMN tenant_id UUID REFERENCES users(id);
ALTER TABLE listings_int_ext   ADD COLUMN tenant_id UUID;
ALTER TABLE listings_int_hist  ADD COLUMN tenant_id UUID;
ALTER TABLE keywords           ADD COLUMN tenant_id UUID;
ALTER TABLE refresh_state      ADD COLUMN tenant_id UUID;

-- Backfill với seed tenant (admin user tạo khi chạy migrate)
UPDATE listings              SET tenant_id = (SELECT id FROM users WHERE is_admin = true LIMIT 1);
-- ... tương tự cho tất cả tables
```

**Bước 2 — Set NOT NULL sau khi backfill:**
```sql
ALTER TABLE listings               ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE listing_report         ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE keyword_report         ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE manual_listing_report  ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE manual_keyword_report  ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE import_batch           ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE threshold_configs      ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE scenarios_rules        ALTER COLUMN tenant_id SET NOT NULL;
```

**Bước 3 — Index:**
```sql
CREATE INDEX idx_listings_tenant              ON listings(tenant_id);
CREATE INDEX idx_listing_report_tenant        ON listing_report(tenant_id);
CREATE INDEX idx_keyword_report_tenant        ON keyword_report(tenant_id);
CREATE INDEX idx_manual_listing_report_tenant ON manual_listing_report(tenant_id);
CREATE INDEX idx_manual_keyword_report_tenant ON manual_keyword_report(tenant_id);
CREATE INDEX idx_import_batch_tenant          ON import_batch(tenant_id);
CREATE INDEX idx_threshold_configs_tenant     ON threshold_configs(tenant_id);
CREATE INDEX idx_scenarios_rules_tenant       ON scenarios_rules(tenant_id);
CREATE INDEX idx_listings_int_ext_tenant      ON listings_int_ext(tenant_id);
CREATE INDEX idx_listings_int_hist_tenant     ON listings_int_hist(tenant_id);
CREATE INDEX idx_keywords_tenant              ON keywords(tenant_id);
```

**Bước 4 — `refresh_state` đổi từ singleton sang per-tenant:**
```sql
-- Drop PK cũ (id=1 singleton), thêm PK mới
ALTER TABLE refresh_state DROP CONSTRAINT refresh_state_pkey;
ALTER TABLE refresh_state ADD PRIMARY KEY (tenant_id);
```

- [ ] Viết và test toàn bộ migration script trên
- [ ] Tạo script `backend/scripts/seed_admin_tenant.py` — tạo admin user nếu chưa có, backfill tenant_id

---

### MT-BE-2: SQLAlchemy Models — Thêm `tenant_id`

Sửa các model sau, thêm column `tenant_id`:

- [ ] `backend/app/models/listing.py` — thêm `tenant_id = Column(UUID, ForeignKey('users.id'), nullable=False, index=True)`
- [ ] `backend/app/models/listing_report.py` — thêm `tenant_id`
- [ ] `backend/app/models/keyword_report.py` — thêm `tenant_id`
- [ ] `backend/app/models/manual_listing_report.py` — thêm `tenant_id`
- [ ] `backend/app/models/manual_keyword_report.py` — thêm `tenant_id`
- [ ] `backend/app/models/import_batch.py` — thêm `tenant_id`
- [ ] `backend/app/models/threshold.py` — thêm `tenant_id`
- [ ] `backend/app/models/scenario.py` — thêm `tenant_id`
- [ ] **KHÔNG sửa** `thumbnail_knowledge.py` — global shared

---

### MT-BE-3: Tenant Context Dependency

- [ ] Tạo `backend/app/core/tenant.py`
  ```python
  def get_tenant_id(current_user: User = Depends(get_current_active_user)) -> UUID:
      return current_user.id
  ```
  - Inject `tenant_id` vào mọi route cần data isolation
  - Admin user có thể override với query param `?tenant_id=xxx` (check `is_admin=true`)

---

### MT-BE-4: Services — Thêm `tenant_id` filter

Sửa từng service, thêm `tenant_id: UUID` param vào mọi query method:

- [ ] `backend/app/services/listing_service.py`
  - Tất cả SELECT: thêm `.where(Listing.tenant_id == tenant_id)`
  - INSERT: set `tenant_id = tenant_id`
- [ ] `backend/app/services/performance_service.py`
  - `get_listings_dashboard(tenant_id)` — filter `listings_int_ext.tenant_id`
- [ ] `backend/app/services/internal_service.py`
  - Upload/confirm batch: set `import_batch.tenant_id`
  - Tất cả queries: filter theo `tenant_id`
- [ ] `backend/app/services/reporting_etl.py`
  - `rebuild_reporting(tenant_id)` — rebuild chỉ cho tenant đó
  - Materialized tables (`listings_int_ext`, `listings_int_hist`, `keywords`) filter + write theo `tenant_id`
  - `refresh_state` lookup theo `tenant_id` thay vì `id=1`
- [ ] `backend/app/services/references_service.py` — filter theo `tenant_id` nếu applicable

---

### MT-BE-5: Routes — Inject `tenant_id`

Sửa từng router, inject `tenant_id = Depends(get_tenant_id)`:

- [ ] `backend/app/api/routes/listings.py` — tất cả endpoints
- [ ] `backend/app/api/routes/performance.py` — `/listings`, `/refresh`
- [ ] `backend/app/api/routes/internal.py` — upload, extract, confirm, discard, rollback, history
- [ ] `backend/app/api/routes/thresholds.py` — CRUD
- [ ] `backend/app/api/routes/scenarios.py` — CRUD
- [ ] `backend/app/api/routes/references.py` — list, refresh
- [ ] `backend/app/api/routes/intelligence.py` — thumbnail-eval (đã có credit gate từ auth_payment)
- [ ] **KHÔNG sửa** `backend/app/api/routes/market.py` — market data là global

---

### MT-BE-6: Admin Tenant Override (optional nhưng cần cho ops)

- [ ] Tạo `backend/app/api/routes/admin.py`
  - `GET /api/v1/admin/tenants` — list tất cả tenants (is_admin only)
  - `GET /api/v1/admin/tenants/{tenant_id}/stats` — xem stats của 1 tenant
- [ ] Admin middleware: `require_admin(user)` → raise 403 nếu `is_admin=false`
- [ ] Include `admin.router` trong `main.py`

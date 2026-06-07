from pydantic import BaseModel


# ── Report rows (pushed by the browser extension) ────────
class ListingReportRow(BaseModel):
    listing_id: str
    title: str | None = None
    no_vm: str | None = None
    price: float | None = None
    stock: int | None = None
    category: str | None = None
    lifetime_orders: int | None = None
    lifetime_revenue: float | None = None
    period: str
    views: int = 0
    clicks: int = 0
    orders: int = 0
    revenue: float = 0
    spend: float = 0
    roas: float = 0


class KeywordReportRow(BaseModel):
    listing_id: str
    keyword: str
    no_vm: str | None = None
    relevant: str | None = None
    period: str
    roas: float = 0
    orders: int = 0
    spend: float = 0
    revenue: float = 0
    clicks: int = 0
    click_rate: str | None = None
    views: int = 0


# ── Extension ingest ─────────────────────────────────────
class IngestListingRequest(BaseModel):
    rows: list[ListingReportRow]
    importer: str | None = None  # VM name e.g. "VM08"


class IngestKeywordRequest(BaseModel):
    rows: list[KeywordReportRow]
    importer: str | None = None


class IngestResponse(BaseModel):
    inserted: int

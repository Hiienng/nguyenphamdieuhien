from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class ListingDashboardItem(BaseModel):
    listing_id: str | None = None
    url: str | None = None
    image_url: str | None = None
    title: str | None = None
    product: str | None = None
    no_vm: str | None = None
    period: str | None = None
    reference_date: datetime | None = None
    # performance (from listing_report latest)
    ctr: Decimal | None = None
    cr: Decimal | None = None
    roas: Decimal | None = None
    views: int | None = None
    clicks: int | None = None
    orders: int | None = None
    revenue: Decimal | None = None
    spend: Decimal | None = None
    cpc: Decimal | None = None
    cpp: Decimal | None = None
    # scenario (from scenarios_rules JOIN)
    scenario_action: str | None = None
    scenario_label: str | None = None
    scenario_cause: str | None = None
    scenario_fix_listing: str | None = None
    scenario_fix_ads: str | None = None
    # keywords: list of dicts from keyword_report at latest import_time
    keywords: list[dict] | None = None
    # history: daily internal metrics per listing
    history: list[dict] | None = None

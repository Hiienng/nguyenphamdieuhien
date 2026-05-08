from datetime import datetime
from pydantic import BaseModel


class ScenarioRuleOut(BaseModel):
    id: int
    roas_band: str
    cr_level: str
    ctr_level: str
    case_name: str
    action: str
    cause: str | None = None
    fix_listing: str | None = None
    fix_ads: str | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScenarioRuleIn(BaseModel):
    roas_band: str
    cr_level: str
    ctr_level: str
    case_name: str
    action: str
    cause: str | None = None
    fix_listing: str | None = None
    fix_ads: str | None = None

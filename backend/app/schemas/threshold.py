from datetime import datetime
from pydantic import BaseModel, Field


class ThresholdConfigOut(BaseModel):
    id:         int
    roas_be:    float
    cr_high:    float
    ctr_high:   float
    note:       str | None = None
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ThresholdConfigIn(BaseModel):
    roas_be:    float = Field(gt=0)
    cr_high:    float = Field(gt=0)
    ctr_high:   float = Field(gt=0)
    note:       str | None = None
    created_by: str = "user"

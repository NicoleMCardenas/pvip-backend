from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SurveyBase(BaseModel):
    visit_id: UUID
    client_id: UUID


class SurveyCreate(SurveyBase):
    pass


class SurveyResponseUpdate(BaseModel):
    satisfaction_score: Optional[int] = Field(
        default=None,
        ge=1,
        le=5
    )

    nps_score: Optional[int] = Field(
        default=None,
        ge=0,
        le=10
    )

    rebook_intent: Optional[
        Literal["yes", "no", "unsure"]
    ] = None

    comment: Optional[str] = Field(
        default=None,
        max_length=2000
    )

    status: Optional[str] = "completed"


class SurveyResponse(BaseModel):
    id: UUID

    business_id: UUID
    visit_id: UUID
    client_id: UUID

    status: str

    satisfaction_score: Optional[int] = None
    nps_score: Optional[int] = None

    rebook_intent: Optional[str] = None
    comment: Optional[str] = None

    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
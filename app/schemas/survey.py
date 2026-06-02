from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SurveyBase(BaseModel):
    visit_id: UUID
    client_id: UUID


class SurveyCreate(SurveyBase):
    pass


class SurveyResponseUpdate(BaseModel):
    satisfaction_score: Optional[int] = None
    nps_score: Optional[int] = None

    rebook_intent: Optional[str] = None

    comment: Optional[str] = None

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

    class Config:
        from_attributes = True
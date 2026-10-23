
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


RetentionStatus = Literal["pending", "in_progress", "resolved"]
RetentionPriority = Literal["low", "medium", "high"]

ActivityType = Literal["call", "email", "message", "other"]
ActivityOutcome = Literal[
    "contacted",
    "no_response",
    "follow_up_needed",
    "other",
]


class RetentionCaseCreate(BaseModel):
    client_id: UUID
    reason: str = Field(min_length=1, max_length=2000)
    priority: RetentionPriority = "medium"


class RetentionCaseUpdate(BaseModel):
    status: Optional[RetentionStatus] = None
    priority: Optional[RetentionPriority] = None


class RetentionCaseResponse(BaseModel):
    id: UUID
    business_id: UUID
    client_id: UUID
    reason: str
    status: RetentionStatus
    priority: RetentionPriority
    created_at: datetime
    updated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RetentionActivityCreate(BaseModel):
    activity_type: ActivityType
    outcome: Optional[ActivityOutcome] = None
    notes: Optional[str] = Field(default=None, max_length=2000)


class RetentionActivityResponse(BaseModel):
    id: UUID
    case_id: UUID
    activity_type: ActivityType
    outcome: Optional[ActivityOutcome] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

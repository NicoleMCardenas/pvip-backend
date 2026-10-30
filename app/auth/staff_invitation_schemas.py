
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class CreateStaffInvitationRequest(BaseModel):
    staff_id: UUID
    email: EmailStr
    language: Literal["es", "en"] = "es"


class AcceptStaffInvitationRequest(BaseModel):
    token: str = Field(min_length=1)
    password: str = Field(min_length=8)


class StaffInvitationResponse(BaseModel):
    message: str


class AcceptStaffInvitationResponse(BaseModel):
    message: str

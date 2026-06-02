from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class StaffBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class StaffCreate(StaffBase):
    role: Optional[str] = "staff"


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    role: Optional[str] = None
    status: Optional[str] = None


class StaffResponse(StaffBase):
    id: UUID
    business_id: UUID

    role: str
    status: str

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
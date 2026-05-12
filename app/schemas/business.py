from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime


class BusinessBase(BaseModel):
    name: str
    industry: str
    email: EmailStr
    phone: str | None = None


class BusinessCreate(BusinessBase):
    pass


class BusinessResponse(BusinessBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
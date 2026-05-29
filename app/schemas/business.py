from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional

class BusinessBase(BaseModel):
    name: str
    industry: str
    email: EmailStr
    phone: Optional[str] = None


class BusinessCreate(BusinessBase):
    pass

class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

class BusinessResponse(BusinessBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
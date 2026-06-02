from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ServiceBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None

    duration_minutes: int
    price: Decimal


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None

    duration_minutes: Optional[int] = None
    price: Optional[Decimal] = None

    status: Optional[str] = None


class ServiceResponse(ServiceBase):
    id: UUID
    business_id: UUID

    status: str

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
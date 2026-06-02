from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class VisitBase(BaseModel):
    client_id: UUID
    service_id: UUID
    staff_id: UUID

    visit_date: datetime
    amount: Decimal
    notes: Optional[str] = None


class VisitCreate(VisitBase):
    pass


class VisitUpdate(BaseModel):
    visit_date: Optional[datetime] = None
    amount: Optional[Decimal] = None
    notes: Optional[str] = None


class VisitResponse(VisitBase):
    id: UUID
    business_id: UUID

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
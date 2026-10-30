
from datetime import datetime
from decimal import Decimal
from typing import Optional, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr


class ClientBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status: Optional[
        Literal["new", "active", "at_risk"]
    ] = None


class ClientResponse(ClientBase):
    id: UUID
    business_id: UUID

    status: str
    previous_status: Optional[str] = None

    lifetime_value: Decimal
    total_visits: int

    last_visit: Optional[datetime] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ClientStaffResponse(ClientBase):
    id: UUID
    status: str
    last_visit: Optional[datetime] = None

    class Config:
        from_attributes = True

from pydantic import BaseModel, EmailStr, field_validator
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

    @field_validator("name", "industry")
    @classmethod
    def validate_required_text(cls, value: Optional[str]):
        if value is None:
            raise ValueError("Este campo no puede estar vacío.")

        value = value.strip()

        if not value:
            raise ValueError("Este campo no puede estar vacío.")

        return value

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: Optional[str]):
        if value is None:
            return None

        return value.strip() or None


class BusinessResponse(BusinessBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True

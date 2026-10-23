
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator


ServiceStatus = Literal["active", "inactive"]


class ServiceBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)
    category: Optional[str] = Field(default=None, max_length=100)

    duration_minutes: int = Field(gt=0)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Service name cannot be empty.")

        return value


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=150,
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
    )
    category: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    duration_minutes: Optional[int] = Field(
        default=None,
        gt=0,
    )
    price: Optional[Decimal] = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )

    status: Optional[ServiceStatus] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        value = value.strip()

        if not value:
            raise ValueError("Service name cannot be empty.")

        return value


class ServiceResponse(ServiceBase):
    id: UUID
    business_id: UUID

    status: ServiceStatus

    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)


def validate_visit_date(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "Visit date must include a timezone."
        )

    if value > datetime.now(timezone.utc):
        raise ValueError(
            "Visit date cannot be in the future."
        )

    return value


def validate_visit_amount(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError(
            "Visit amount must be a finite number."
        )

    if value < 0:
        raise ValueError(
            "Visit amount cannot be negative."
        )

    return value


class VisitBase(BaseModel):
    client_id: UUID
    service_id: UUID
    staff_id: UUID

    visit_date: datetime
    amount: Decimal
    notes: Optional[str] = None


class VisitCreate(VisitBase):
    @field_validator("visit_date")
    @classmethod
    def check_visit_date(cls, value: datetime) -> datetime:
        return validate_visit_date(value)

    @field_validator("amount")
    @classmethod
    def check_amount(cls, value: Decimal) -> Decimal:
        return validate_visit_amount(value)


class VisitUpdate(BaseModel):
    visit_date: Optional[datetime] = None
    amount: Optional[Decimal] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError(
                "At least one field must be provided."
            )

        if "visit_date" in self.model_fields_set:
            if self.visit_date is None:
                raise ValueError(
                    "Visit date cannot be null."
                )

            self.visit_date = validate_visit_date(
                self.visit_date
            )

        if "amount" in self.model_fields_set:
            if self.amount is None:
                raise ValueError(
                    "Visit amount cannot be null."
                )

            self.amount = validate_visit_amount(
                self.amount
            )

        return self


class VisitResponse(VisitBase):
    id: UUID
    business_id: UUID

    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

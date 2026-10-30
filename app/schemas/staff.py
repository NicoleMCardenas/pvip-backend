
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    field_validator,
    model_validator,
)


class StaffBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Staff name cannot be empty.")

        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        value = value.strip()
        return value or None


class StaffCreate(StaffBase):
    role: str = "staff"

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Staff role cannot be empty.")

        return value


class StaffUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")

        if "name" in self.model_fields_set:
            if self.name is None or not self.name.strip():
                raise ValueError("Staff name cannot be empty.")
            self.name = self.name.strip()

        if "role" in self.model_fields_set:
            if self.role is None or not self.role.strip():
                raise ValueError("Staff role cannot be empty.")
            self.role = self.role.strip()

        if "phone" in self.model_fields_set and self.phone is not None:
            self.phone = self.phone.strip() or None

        if "status" in self.model_fields_set:
            if self.status not in ("active", "inactive"):
                raise ValueError(
                    "Staff status must be active or inactive."
                )

        return self


class StaffResponse(StaffBase):
    id: UUID
    business_id: UUID
    role: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class StaffOperationalResponse(BaseModel):
    id: UUID
    name: str
    role: str
    status: str

    model_config = ConfigDict(from_attributes=True)

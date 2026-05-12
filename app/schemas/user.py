from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime


class UserBase(BaseModel):
    name: str
    email: EmailStr


class UserCreate(UserBase):
    password: str
    business_id: UUID


class UserResponse(UserBase):
    id: UUID
    business_id: UUID
    role: str
    created_at: datetime

    class Config:
        from_attributes = True
from pydantic import BaseModel, EmailStr
from typing import Optional


class RegisterRequest(BaseModel):
    business_name: str
    industry: str
    business_email: EmailStr
    business_phone: Optional[str] = None

    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
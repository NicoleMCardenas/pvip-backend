from typing import Optional
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    business_name: str
    industry: str
    business_email: EmailStr
    business_phone: Optional[str] = None

    name: str
    email: EmailStr
    password: str
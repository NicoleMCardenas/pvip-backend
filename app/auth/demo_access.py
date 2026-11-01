
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.demo_read_only import DEMO_BUSINESS_ID
from app.core.jwt import create_access_token
from app.models.user import User


DEMO_USER_EMAIL = "demo-user@example.com"


def create_demo_access_token(db: Session) -> dict:
    user = (
        db.query(User)
        .filter(
            User.business_id == DEMO_BUSINESS_ID,
            User.email == DEMO_USER_EMAIL,
            User.is_active.is_(True),
        )
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El acceso a KAIRO Demo no está disponible.",
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "token_version": user.token_version,
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

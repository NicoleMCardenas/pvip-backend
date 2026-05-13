from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.business import Business
from app.models.user import User

from app.auth.schemas import RegisterRequest
from app.core.security import hash_password


def register_user(data: RegisterRequest, db: Session):

    existing_user = db.query(User).filter(
        User.email == data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo electrónico ya está registrado."
        )

    existing_business = db.query(Business).filter(
        Business.email == data.business_email
    ).first()

    if existing_business:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El correo del negocio ya está registrado."
        )

    business = Business(
        name=data.business_name,
        industry=data.industry,
        email=data.business_email,
        phone=data.business_phone
    )

    db.add(business)
    db.flush()

    user = User(
        business_id=business.id,
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role="owner"
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user
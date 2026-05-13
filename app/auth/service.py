from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.business import Business
from app.models.user import User

from app.auth.schemas import RegisterRequest
from app.core.security import hash_password

from app.auth.schemas import LoginRequest
from app.core.security import verify_password
from app.core.jwt import create_access_token

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

def login_user(data: LoginRequest, db: Session):

    user = db.query(User).filter(
        User.email == data.email
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas."
        )

    valid_password = verify_password(
        data.password,
        user.password_hash
    )

    if not valid_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas."
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user.role
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
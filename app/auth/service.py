from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.user import User

from app.auth.schemas import RegisterRequest
from app.core.security import hash_password


def register_user(data: RegisterRequest, db: Session):

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
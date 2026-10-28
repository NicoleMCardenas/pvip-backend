
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.business import Business


def get_business_by_id(business_id: str, db: Session):
    return db.query(Business).filter(
        Business.id == business_id
    ).first()


def update_business(business: Business, data: dict, db: Session):
    if "email" in data and data["email"] != business.email:
        existing_business = db.query(Business).filter(
            Business.email == data["email"],
            Business.id != business.id,
        ).first()

        if existing_business:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este correo electrónico ya está registrado.",
            )

    for key, value in data.items():
        if value is not None or key == "phone":
            setattr(business, key, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se pudieron guardar los cambios porque existe un conflicto con los datos registrados.",
        )

    db.refresh(business)
    return business

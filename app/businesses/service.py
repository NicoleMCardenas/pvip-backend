from sqlalchemy.orm import Session

from app.models.business import Business


def get_business_by_id(business_id: str, db: Session):
    return db.query(Business).filter(
        Business.id == business_id
    ).first()


def update_business(business: Business, data: dict, db: Session):
    for key, value in data.items():
        if value is not None:
            setattr(business, key, value)

    db.commit()
    db.refresh(business)

    return business
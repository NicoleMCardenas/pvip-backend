from sqlalchemy.orm import Session

from app.models.visit import Visit
from app.schemas.visit import VisitCreate, VisitUpdate


def create_visit(data: VisitCreate, business_id: str, db: Session):
    visit = Visit(
        business_id=business_id,
        client_id=data.client_id,
        service_id=data.service_id,
        staff_id=data.staff_id,
        visit_date=data.visit_date,
        amount=data.amount,
        notes=data.notes
    )

    db.add(visit)
    db.commit()
    db.refresh(visit)

    return visit


def get_visits(business_id: str, db: Session):
    return db.query(Visit).filter(
        Visit.business_id == business_id
    ).all()


def get_visit_by_id(visit_id: str, business_id: str, db: Session):
    return db.query(Visit).filter(
        Visit.id == visit_id,
        Visit.business_id == business_id
    ).first()


def update_visit(visit: Visit, data: VisitUpdate, db: Session):
    update_data = data.dict(exclude_unset=True)

    for key, value in update_data.items():
        setattr(visit, key, value)

    db.commit()
    db.refresh(visit)

    return visit


def delete_visit(visit: Visit, db: Session):
    db.delete(visit)
    db.commit()
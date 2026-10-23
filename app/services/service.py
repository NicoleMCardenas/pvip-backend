
from sqlalchemy.orm import Session

from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceUpdate


def create_service(data: ServiceCreate, business_id: str, db: Session):
    service = Service(
        business_id=business_id,
        name=data.name,
        description=data.description,
        category=data.category,
        duration_minutes=data.duration_minutes,
        price=data.price,
        status="active",
    )

    db.add(service)
    db.commit()
    db.refresh(service)

    return service


def get_services(business_id: str, db: Session):
    return (
        db.query(Service)
        .filter(Service.business_id == business_id)
        .all()
    )


def get_service_by_id(service_id: str, business_id: str, db: Session):
    return (
        db.query(Service)
        .filter(
            Service.id == service_id,
            Service.business_id == business_id,
        )
        .first()
    )


def update_service(service: Service, data: ServiceUpdate, db: Session):
    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(service, key, value)

    db.commit()
    db.refresh(service)

    return service


def delete_service(service: Service, db: Session):
    """
    Soft delete: deactivate the service while preserving
    historical visits and their service references.
    """
    service.status = "inactive"

    db.commit()
    db.refresh(service)

    return service

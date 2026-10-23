from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.retention_case import RetentionCase
from app.models.revenue_recovery import RevenueRecovery
from app.models.service import Service
from app.models.staff import Staff
from app.models.visit import Visit
from app.schemas.visit import VisitCreate, VisitUpdate


def validate_visit_references(
    data: VisitCreate,
    business_id: UUID,
    db: Session,
):
    client = (
        db.query(Client)
        .filter(
            Client.id == data.client_id,
            Client.business_id == business_id,
        )
        .first()
    )

    if not client or client.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Customer is unavailable for new visits.",
        )

    service = (
        db.query(Service)
        .filter(
            Service.id == data.service_id,
            Service.business_id == business_id,
        )
        .first()
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Service does not belong to this business.",
        )

    if service.status != "active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Service is unavailable for new visits.",
        )

    staff_member = (
        db.query(Staff)
        .filter(
            Staff.id == data.staff_id,
            Staff.business_id == business_id,
        )
        .first()
    )

    if not staff_member or staff_member.status != "active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Staff member is unavailable for new visits.",
        )

    return client


def recalculate_client_metrics(
    client: Client,
    db: Session,
):
    total_visits, lifetime_value, last_visit = (
        db.query(
            func.count(Visit.id),
            func.coalesce(func.sum(Visit.amount), 0),
            func.max(Visit.visit_date),
        )
        .filter(
            Visit.client_id == client.id,
            Visit.business_id == client.business_id,
        )
        .one()
    )

    client.total_visits = total_visits
    client.lifetime_value = lifetime_value
    client.last_visit = last_visit


def create_visit(
    data: VisitCreate,
    business_id: UUID,
    db: Session,
):
    client = validate_visit_references(
        data,
        business_id,
        db,
    )

    visit = Visit(
        business_id=business_id,
        client_id=data.client_id,
        service_id=data.service_id,
        staff_id=data.staff_id,
        visit_date=data.visit_date,
        amount=data.amount,
        notes=data.notes,
    )

    try:
        db.add(visit)
        db.flush()

        recalculate_client_metrics(client, db)

        if client.status == "new":
            client.status = "active"

        db.commit()
        db.refresh(visit)

        return visit

    except Exception:
        db.rollback()
        raise


def get_visits(business_id: UUID, db: Session):
    return (
        db.query(Visit)
        .filter(Visit.business_id == business_id)
        .order_by(
            Visit.visit_date.desc(),
            Visit.id.desc(),
        )
        .all()
    )


def get_visit_by_id(
    visit_id: UUID,
    business_id: UUID,
    db: Session,
):
    return (
        db.query(Visit)
        .filter(
            Visit.id == visit_id,
            Visit.business_id == business_id,
        )
        .first()
    )


def validate_recovery_visit_date(
    visit: Visit,
    new_visit_date,
    db: Session,
):
    recovery = (
        db.query(RevenueRecovery)
        .filter(
            RevenueRecovery.visit_id == visit.id,
        )
        .first()
    )

    if not recovery:
        return

    retention_case = (
        db.query(RetentionCase)
        .filter(
            RetentionCase.id == recovery.case_id,
            RetentionCase.business_id == visit.business_id,
            RetentionCase.client_id == visit.client_id,
        )
        .first()
    )

    if not retention_case:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recovery attribution references an invalid retention case.",
        )

    if new_visit_date < retention_case.created_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Attributed visit cannot occur before the retention case.",
        )

    if (
        retention_case.resolved_at is not None
        and new_visit_date > retention_case.resolved_at
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Attributed visit cannot occur after case resolution.",
        )


def update_visit(
    visit: Visit,
    data: VisitUpdate,
    db: Session,
):
    update_data = data.model_dump(exclude_unset=True)

    try:
        if "visit_date" in update_data:
            validate_recovery_visit_date(
                visit,
                update_data["visit_date"],
                db,
            )

        if "amount" in update_data:
            recovery = (
                db.query(RevenueRecovery)
                .filter(
                    RevenueRecovery.visit_id == visit.id,
                )
                .first()
            )

            if recovery and update_data["amount"] <= 0:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Attributed visit amount must be greater than zero.",
                )

        for key, value in update_data.items():
            setattr(visit, key, value)

        db.flush()

        client = (
            db.query(Client)
            .filter(
                Client.id == visit.client_id,
                Client.business_id == visit.business_id,
            )
            .first()
        )

        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer associated with visit was not found.",
            )

        recalculate_client_metrics(client, db)

        db.commit()
        db.refresh(visit)

        return visit

    except Exception:
        db.rollback()
        raise


def delete_visit(visit: Visit, db: Session):
    try:
        client = (
            db.query(Client)
            .filter(
                Client.id == visit.client_id,
                Client.business_id == visit.business_id,
            )
            .first()
        )

        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer associated with visit was not found.",
            )

        recovery = (
            db.query(RevenueRecovery)
            .filter(
                RevenueRecovery.visit_id == visit.id,
            )
            .first()
        )

        if recovery:
            db.delete(recovery)
            db.flush()

        db.delete(visit)
        db.flush()

        recalculate_client_metrics(client, db)

        db.commit()

    except Exception:
        db.rollback()
        raise
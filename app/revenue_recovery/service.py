from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.retention_case import RetentionCase
from app.models.revenue_recovery import RevenueRecovery
from app.models.visit import Visit


def get_revenue_recoveries(
    business_id: UUID,
    db: Session,
):
    return (
        db.query(RevenueRecovery)
        .join(
            RetentionCase,
            RevenueRecovery.case_id == RetentionCase.id,
        )
        .filter(
            RetentionCase.business_id == business_id,
        )
        .order_by(
            RevenueRecovery.created_at.desc(),
            RevenueRecovery.id.desc(),
        )
        .all()
    )


def attribute_recovered_revenue(
    case_id: UUID,
    visit_id: UUID,
    business_id: UUID,
    db: Session,
):
    retention_case = (
        db.query(RetentionCase)
        .filter(
            RetentionCase.id == case_id,
            RetentionCase.business_id == business_id,
        )
        .first()
    )

    if not retention_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Retention case not found.",
        )

    visit = (
        db.query(Visit)
        .filter(
            Visit.id == visit_id,
            Visit.business_id == business_id,
        )
        .first()
    )

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found.",
        )

    if visit.client_id != retention_case.client_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Visit and retention case must belong "
                "to the same customer."
            ),
        )

    if visit.visit_date < retention_case.created_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Visit must occur after the retention case was created.",
        )

    if (
        retention_case.resolved_at is not None
        and visit.visit_date > retention_case.resolved_at
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Visit cannot occur after the case was resolved.",
        )

    if Decimal(visit.amount) <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Recovered revenue must be greater than zero.",
        )

    existing = (
        db.query(RevenueRecovery)
        .filter(RevenueRecovery.visit_id == visit_id)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Visit has already been attributed to a recovery.",
        )

    recovery = RevenueRecovery(
        case_id=retention_case.id,
        visit_id=visit.id,
    )

    try:
        db.add(recovery)
        db.commit()
        db.refresh(recovery)
        return recovery

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Visit has already been attributed to a recovery.",
        )

    except Exception:
        db.rollback()
        raise


def remove_revenue_attribution(
    recovery_id: UUID,
    business_id: UUID,
    db: Session,
):
    recovery = (
        db.query(RevenueRecovery)
        .join(
            RetentionCase,
            RevenueRecovery.case_id == RetentionCase.id,
        )
        .filter(
            RevenueRecovery.id == recovery_id,
            RetentionCase.business_id == business_id,
        )
        .first()
    )

    if not recovery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Revenue recovery attribution not found.",
        )

    try:
        db.delete(recovery)
        db.commit()

    except Exception:
        db.rollback()
        raise
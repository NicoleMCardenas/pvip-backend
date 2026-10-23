
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.retention_activity import RetentionActivity
from app.models.retention_case import RetentionCase
from app.schemas.retention import (
    RetentionActivityCreate,
    RetentionCaseCreate,
    RetentionCaseUpdate,
)


OPEN_STATUSES = ("pending", "in_progress")


def get_retention_cases(business_id: UUID, db: Session):
    return (
        db.query(RetentionCase)
        .filter(RetentionCase.business_id == business_id)
        .order_by(RetentionCase.created_at.desc())
        .all()
    )


def get_retention_case_by_id(
    case_id: UUID,
    business_id: UUID,
    db: Session,
):
    return (
        db.query(RetentionCase)
        .filter(
            RetentionCase.id == case_id,
            RetentionCase.business_id == business_id,
        )
        .first()
    )


def create_retention_case(
    data: RetentionCaseCreate,
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

    if not client:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Customer does not belong to this business.",
        )

    if client.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cannot create a retention case for an archived customer.",
        )

    existing_case = (
        db.query(RetentionCase)
        .filter(
            RetentionCase.business_id == business_id,
            RetentionCase.client_id == client.id,
            RetentionCase.status.in_(OPEN_STATUSES),
        )
        .first()
    )

    if existing_case:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An open retention case already exists for this customer.",
        )

    retention_case = RetentionCase(
        business_id=business_id,
        client_id=client.id,
        reason=data.reason.strip(),
        priority=data.priority,
        status="pending",
    )

    try:
        db.add(retention_case)
        db.commit()
        db.refresh(retention_case)
        return retention_case
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An open retention case already exists for this customer.",
        )
    except Exception:
        db.rollback()
        raise


def update_retention_case(
    retention_case: RetentionCase,
    data: RetentionCaseUpdate,
    db: Session,
):
    changes = data.model_dump(exclude_unset=True)

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided.",
        )

    if any(value is None for value in changes.values()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Status and priority cannot be null.",
        )

    if retention_case.status == "resolved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resolved retention cases cannot be modified.",
        )

    new_status = changes.get("status", retention_case.status)

    if new_status == "resolved":
        retention_case.resolved_at = datetime.now(timezone.utc)

    for field, value in changes.items():
        setattr(retention_case, field, value)

    try:
        db.commit()
        db.refresh(retention_case)
        return retention_case
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to update this retention case.",
        )
    except Exception:
        db.rollback()
        raise


def get_retention_activities(
    retention_case: RetentionCase,
    db: Session,
):
    return (
        db.query(RetentionActivity)
        .filter(RetentionActivity.case_id == retention_case.id)
        .order_by(
            RetentionActivity.created_at.desc(),
            RetentionActivity.id.desc(),
        )
        .all()
    )


def create_retention_activity(
    retention_case: RetentionCase,
    data: RetentionActivityCreate,
    db: Session,
):
    if retention_case.status == "resolved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot add activities to a resolved retention case.",
        )

    activity = RetentionActivity(
        case_id=retention_case.id,
        activity_type=data.activity_type,
        outcome=data.outcome,
        notes=data.notes.strip() if data.notes else None,
    )

    try:
        db.add(activity)
        db.commit()
        db.refresh(activity)
        return activity
    except Exception:
        db.rollback()
        raise


from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User

from app.schemas.retention import (
    RetentionActivityCreate,
    RetentionActivityResponse,
    RetentionCaseCreate,
    RetentionCaseResponse,
    RetentionCaseUpdate,
)

from app.retention.service import (
    create_retention_activity,
    create_retention_case,
    get_retention_activities,
    get_retention_case_by_id,
    get_retention_cases,
    update_retention_case,
)


router = APIRouter(
    prefix="/retention",
    tags=["Retention"],
)


@router.get("/", response_model=list[RetentionCaseResponse])
def list_my_retention_cases(
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    return get_retention_cases(current_user.business_id, db)


@router.post(
    "/",
    response_model=RetentionCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_my_retention_case(
    data: RetentionCaseCreate,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    return create_retention_case(
        data,
        current_user.business_id,
        db,
    )


@router.get(
    "/{case_id}",
    response_model=RetentionCaseResponse,
)
def get_my_retention_case(
    case_id: UUID,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    retention_case = get_retention_case_by_id(
        case_id,
        current_user.business_id,
        db,
    )

    if not retention_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Retention case not found.",
        )

    return retention_case


@router.patch(
    "/{case_id}",
    response_model=RetentionCaseResponse,
)
def update_my_retention_case(
    case_id: UUID,
    data: RetentionCaseUpdate,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    retention_case = get_retention_case_by_id(
        case_id,
        current_user.business_id,
        db,
    )

    if not retention_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Retention case not found.",
        )

    return update_retention_case(retention_case, data, db)


@router.get(
    "/{case_id}/activities",
    response_model=list[RetentionActivityResponse],
)
def list_my_retention_activities(
    case_id: UUID,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    retention_case = get_retention_case_by_id(
        case_id,
        current_user.business_id,
        db,
    )

    if not retention_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Retention case not found.",
        )

    return get_retention_activities(retention_case, db)


@router.post(
    "/{case_id}/activities",
    response_model=RetentionActivityResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_my_retention_activity(
    case_id: UUID,
    data: RetentionActivityCreate,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    retention_case = get_retention_case_by_id(
        case_id,
        current_user.business_id,
        db,
    )

    if not retention_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Retention case not found.",
        )

    return create_retention_activity(retention_case, data, db)

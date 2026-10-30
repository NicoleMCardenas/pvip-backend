from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User

from app.schemas.revenue_recovery import (
    RevenueRecoveryCreate,
    RevenueRecoveryResponse,
    RevenueRecoveryMetricsResponse,
)

from app.revenue_recovery.metrics import (
    get_revenue_recovery_metrics,
)

from app.revenue_recovery.service import (
    attribute_recovered_revenue,
    get_revenue_recoveries,
    remove_revenue_attribution,
)


router = APIRouter(
    prefix="/revenue-recovery",
    tags=["Revenue Recovery"],
)


@router.get(
    "/metrics",
    response_model=RevenueRecoveryMetricsResponse,
)
def get_my_revenue_recovery_metrics(
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    return get_revenue_recovery_metrics(
        business_id=current_user.business_id,
        db=db,
    )


@router.get(
    "/",
    response_model=list[RevenueRecoveryResponse],
)
def list_my_revenue_recoveries(
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    return get_revenue_recoveries(
        current_user.business_id,
        db,
    )


@router.post(
    "/",
    response_model=RevenueRecoveryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_my_revenue_recovery(
    data: RevenueRecoveryCreate,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    return attribute_recovered_revenue(
        case_id=data.case_id,
        visit_id=data.visit_id,
        business_id=current_user.business_id,
        db=db,
    )


@router.delete(
    "/{recovery_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_my_revenue_recovery(
    recovery_id: UUID,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    remove_revenue_attribution(
        recovery_id=recovery_id,
        business_id=current_user.business_id,
        db=db,
    )

    return None
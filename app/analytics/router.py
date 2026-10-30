from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User

from app.analytics.service import (
    get_dashboard_metrics,
    get_risk_clients,
    get_recovery_queue,
)
from app.analytics.segmentation import get_customer_segments
from app.analytics.trends import get_experience_trends


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
)


@router.get("/dashboard")
def dashboard_metrics(
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    return get_dashboard_metrics(
        current_user.business_id,
        db,
    )


@router.get("/risk-clients")
def risk_clients(
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    return get_risk_clients(
        current_user.business_id,
        db,
    )


@router.get("/recovery-queue")
def recovery_queue(
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    return get_recovery_queue(
        current_user.business_id,
        db,
    )


@router.get("/customer-segments")
def customer_segments(
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    return get_customer_segments(
        current_user.business_id,
        db,
    )


@router.get("/experience-trends")
def experience_trends(
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    return get_experience_trends(
        current_user.business_id,
        db,
    )
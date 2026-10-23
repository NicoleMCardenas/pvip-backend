from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.retention_case import RetentionCase
from app.models.revenue_recovery import RevenueRecovery
from app.models.visit import Visit


OPEN_STATUSES = ("pending", "in_progress")


def get_revenue_recovery_metrics(
    business_id: UUID,
    db: Session,
    as_of: datetime = None,
):
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    open_cases = (
        db.query(RetentionCase)
        .join(
            Client,
            Client.id == RetentionCase.client_id,
        )
        .filter(
            RetentionCase.business_id == business_id,
            Client.business_id == business_id,
            Client.status != "archived",
            RetentionCase.status.in_(OPEN_STATUSES),
            RetentionCase.created_at <= as_of,
        )
        .all()
    )

    open_case_ids = [
        retention_case.id
        for retention_case in open_cases
    ]

    client_ids = list({
        retention_case.client_id
        for retention_case in open_cases
    })

    visit_history = {}

    if client_ids:
        rows = (
            db.query(
                Visit.client_id,
                func.count(Visit.id),
                func.sum(Visit.amount),
            )
            .filter(
                Visit.business_id == business_id,
                Visit.client_id.in_(client_ids),
                Visit.visit_date <= as_of,
            )
            .group_by(Visit.client_id)
            .all()
        )

        visit_history = {
            client_id: {
                "count": count,
                "total": Decimal(total),
            }
            for client_id, count, total in rows
        }

    estimated_at_risk = Decimal("0")
    estimated_cases = 0
    insufficient_data_cases = 0

    opportunities = []

    for retention_case in open_cases:
        history = visit_history.get(
            retention_case.client_id
        )

        estimated_value = None

        if history and history["count"] > 0:
            estimated_value = (
                history["total"] / history["count"]
            )

            estimated_at_risk += estimated_value
            estimated_cases += 1

        else:
            insufficient_data_cases += 1

        opportunities.append({
            "case_id": retention_case.id,
            "client_id": retention_case.client_id,
            "priority": retention_case.priority,
            "status": retention_case.status,
            "estimated_revenue_at_risk": (
                round(estimated_value, 2)
                if estimated_value is not None
                else None
            ),
        })

    recovered_revenue = (
        db.query(
            func.coalesce(func.sum(Visit.amount), 0)
        )
        .join(
            RevenueRecovery,
            RevenueRecovery.visit_id == Visit.id,
        )
        .join(
            RetentionCase,
            RetentionCase.id == RevenueRecovery.case_id,
        )
        .filter(
            RetentionCase.business_id == business_id,
            Visit.business_id == business_id,
            Visit.client_id == RetentionCase.client_id,
            Visit.visit_date <= as_of,
            RevenueRecovery.created_at <= as_of,
        )
        .scalar()
    )

    attributed_visits = (
        db.query(RevenueRecovery)
        .join(
            RetentionCase,
            RetentionCase.id == RevenueRecovery.case_id,
        )
        .join(
            Visit,
            Visit.id == RevenueRecovery.visit_id,
        )
        .filter(
            RetentionCase.business_id == business_id,
            Visit.business_id == business_id,
            Visit.client_id == RetentionCase.client_id,
            Visit.visit_date <= as_of,
            RevenueRecovery.created_at <= as_of,
        )
        .count()
    )

    resolved_cases = (
        db.query(RetentionCase)
        .filter(
            RetentionCase.business_id == business_id,
            RetentionCase.status == "resolved",
            RetentionCase.resolved_at <= as_of,
        )
        .count()
    )

    return {
        "as_of": as_of,
        "open_opportunities": len(open_case_ids),
        "resolved_cases": resolved_cases,
        "estimated_revenue_at_risk": round(
            estimated_at_risk,
            2,
        ),
        "estimated_cases": estimated_cases,
        "insufficient_data_cases": insufficient_data_cases,
        "recovered_revenue": round(
            Decimal(recovered_revenue),
            2,
        ),
        "attributed_visits": attributed_visits,
        "opportunities": opportunities,
    }
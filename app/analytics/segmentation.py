from __future__ import annotations
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.visit import Visit


INACTIVITY_DAYS = 90


def get_customer_segments(
    business_id: UUID,
    db: Session,
    as_of: datetime | None = None,
) -> dict:
    """
    Classify non-archived customers using actual visit history.

    Segments are mutually exclusive:
    - new: no completed visits
    - one_time: one visit within the activity window
    - returning: multiple visits within the activity window
    - inactive: at least one visit, last visit >= 90 days ago

    Future visits are excluded.
    """

    if as_of is None:
        as_of = datetime.now(timezone.utc)

    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")

    cutoff = as_of - timedelta(days=INACTIVITY_DAYS)

    visit_summary = (
        select(
            Visit.client_id.label("client_id"),
            func.count(Visit.id).label("visit_count"),
            func.max(Visit.visit_date).label("last_visit"),
        )
        .where(
            Visit.business_id == business_id,
            Visit.visit_date <= as_of,
        )
        .group_by(Visit.client_id)
        .subquery()
    )

    visit_count = func.coalesce(
        visit_summary.c.visit_count,
        0,
    )

    segment = case(
        (
            visit_count == 0,
            "new",
        ),
        (
            visit_summary.c.last_visit <= cutoff,
            "inactive",
        ),
        (
            visit_count == 1,
            "one_time",
        ),
        else_="returning",
    )

    statement = (
        select(
            segment.label("segment"),
            func.count(Client.id).label("total"),
        )
        .select_from(Client)
        .outerjoin(
            visit_summary,
            and_(
                Client.id == visit_summary.c.client_id,
                Client.business_id == business_id,
            ),
        )
        .where(
            Client.business_id == business_id,
            Client.status != "archived",
        )
        .group_by(segment)
    )

    rows = db.execute(statement).all()

    counts = {
        "new": 0,
        "one_time": 0,
        "returning": 0,
        "inactive": 0,
    }

    for segment_name, total in rows:
        counts[segment_name] = int(total)

    total_clients = sum(counts.values())

    return {
        "total_clients": total_clients,
        "inactivity_threshold_days": INACTIVITY_DAYS,
        "as_of": as_of.isoformat(),
        "segments": counts,
    }
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.survey import Survey


def get_experience_trends(
    business_id: UUID,
    db: Session,
    as_of: datetime = None,
):
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware.")

    as_of = as_of.astimezone(timezone.utc)

    current_month = datetime(
        as_of.year,
        as_of.month,
        1,
        tzinfo=timezone.utc,
    )

    def shift_months(date, offset):
        month_index = date.year * 12 + date.month - 1 + offset

        return datetime(
            month_index // 12,
            month_index % 12 + 1,
            1,
            tzinfo=timezone.utc,
        )

    start_date = shift_months(current_month, -11)
    end_date = shift_months(current_month, 1)

    monthly_surveys = (
        db.query(
            func.date_trunc(
                "month",
                func.timezone("UTC", Survey.completed_at),
            ).label("month"),
            Survey.satisfaction_score,
            Survey.nps_score,
        )
        .filter(
            Survey.business_id == business_id,
            Survey.status == "completed",
            Survey.completed_at.isnot(None),
            Survey.completed_at >= start_date,
            Survey.completed_at < end_date,
            Survey.completed_at <= as_of,
        )
        .all()
    )

    months = {}

    for offset in range(12):
        month = shift_months(start_date, offset)
        key = month.strftime("%Y-%m")

        months[key] = {
            "month": key,
            "satisfaction_total": 0,
            "satisfaction_responses": 0,
            "nps_responses": 0,
            "promoters": 0,
            "detractors": 0,
        }

    for survey in monthly_surveys:
        month_key = survey.month.strftime("%Y-%m")
        bucket = months[month_key]

        satisfaction = survey.satisfaction_score

        if satisfaction is not None and 1 <= satisfaction <= 5:
            bucket["satisfaction_total"] += satisfaction
            bucket["satisfaction_responses"] += 1

        nps = survey.nps_score

        if nps is not None and 0 <= nps <= 10:
            bucket["nps_responses"] += 1

            if nps >= 9:
                bucket["promoters"] += 1
            elif nps <= 6:
                bucket["detractors"] += 1

    trends = []

    for bucket in months.values():
        satisfaction_count = bucket["satisfaction_responses"]
        nps_count = bucket["nps_responses"]

        average_satisfaction = (
            round(
                bucket["satisfaction_total"] / satisfaction_count,
                2,
            )
            if satisfaction_count
            else None
        )

        nps_score = (
            round(
                (
                    (bucket["promoters"] - bucket["detractors"])
                    / nps_count
                ) * 100,
                2,
            )
            if nps_count
            else None
        )

        trends.append({
            "month": bucket["month"],
            "average_satisfaction": average_satisfaction,
            "satisfaction_responses": satisfaction_count,
            "nps_score": nps_score,
            "nps_responses": nps_count,
        })

    return {
        "period_months": 12,
        "timezone": "UTC",
        "as_of": as_of.isoformat(),
        "trends": trends,
    }
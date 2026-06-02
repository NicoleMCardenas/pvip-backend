from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy import func, or_

from app.models.survey import Survey
from app.models.client import Client


def get_dashboard_metrics(business_id: str, db: Session):
    total_surveys = db.query(Survey).filter(
        Survey.business_id == business_id
    ).count()

    completed_surveys = db.query(Survey).filter(
        Survey.business_id == business_id,
        Survey.status == "completed"
    ).count()

    pending_surveys = db.query(Survey).filter(
        Survey.business_id == business_id,
        Survey.status == "pending"
    ).count()

    avg_satisfaction = db.query(
        func.avg(Survey.satisfaction_score)
    ).filter(
        Survey.business_id == business_id,
        Survey.status == "completed"
    ).scalar()

    promoters = db.query(Survey).filter(
        Survey.business_id == business_id,
        Survey.status == "completed",
        Survey.nps_score >= 9
    ).count()

    detractors = db.query(Survey).filter(
        Survey.business_id == business_id,
        Survey.status == "completed",
        Survey.nps_score <= 6
    ).count()

    nps_score = 0

    if completed_surveys > 0:
        nps_score = ((promoters - detractors) / completed_surveys) * 100

    total_clients = db.query(Client).filter(
        Client.business_id == business_id
    ).count()

    at_risk_clients = db.query(Client).join(
    Survey,
    Survey.client_id == Client.id
    ).filter(
    Client.business_id == business_id
    ).filter(
    or_(
        Client.status == "at_risk",
        Survey.satisfaction_score <= 2,
        Survey.nps_score <= 6
    )
).distinct().count()

    return {
        "total_surveys": total_surveys,
        "completed_surveys": completed_surveys,
        "pending_surveys": pending_surveys,
        "average_satisfaction": round(avg_satisfaction or 0, 2),
        "nps_score": round(nps_score, 2),
        "total_clients": total_clients,
        "at_risk_clients": at_risk_clients
    }
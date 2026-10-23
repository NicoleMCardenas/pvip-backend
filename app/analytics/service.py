from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.survey import Survey


def get_dashboard_metrics(business_id: UUID, db: Session):
    base_surveys = db.query(Survey).filter(
        Survey.business_id == business_id
    )

    total_surveys = base_surveys.count()

    completed_surveys = base_surveys.filter(
        Survey.status == "completed"
    ).count()

    pending_surveys = base_surveys.filter(
        Survey.status == "pending"
    ).count()

    avg_satisfaction = db.query(
        func.avg(Survey.satisfaction_score)
    ).filter(
        Survey.business_id == business_id,
        Survey.status == "completed",
        Survey.satisfaction_score >= 1,
        Survey.satisfaction_score <= 5,
    ).scalar()

    valid_nps = db.query(Survey).filter(
        Survey.business_id == business_id,
        Survey.status == "completed",
        Survey.nps_score >= 0,
        Survey.nps_score <= 10,
    )

    nps_responses = valid_nps.count()

    promoters = valid_nps.filter(
        Survey.nps_score >= 9
    ).count()

    detractors = valid_nps.filter(
        Survey.nps_score <= 6
    ).count()

    nps_score = (
        round(
            ((promoters - detractors) / nps_responses) * 100,
            2,
        )
        if nps_responses > 0
        else None
    )

    total_clients = db.query(Client).filter(
        Client.business_id == business_id,
        Client.status != "archived",
    ).count()

    at_risk_clients = db.query(Client).filter(
        Client.business_id == business_id,
        Client.status == "at_risk",
    ).count()

    return {
        "total_surveys": total_surveys,
        "completed_surveys": completed_surveys,
        "pending_surveys": pending_surveys,
        "average_satisfaction": (
            round(float(avg_satisfaction), 2)
            if avg_satisfaction is not None
            else None
        ),
        "nps_score": nps_score,
        "total_clients": total_clients,
        "at_risk_clients": at_risk_clients,
    }


def get_risk_clients(business_id: UUID, db: Session):
    return (
        db.query(Client)
        .filter(
            Client.business_id == business_id,
            Client.status == "at_risk",
        )
        .order_by(
            Client.created_at.desc(),
            Client.id.desc(),
        )
        .all()
    )


def get_recovery_queue(business_id: UUID, db: Session):
    risk_clients = get_risk_clients(business_id, db)

    if not risk_clients:
        return []

    risk_client_ids = [
        client.id for client in risk_clients
    ]

    ranked_surveys = (
        db.query(
            Survey.id.label("survey_id"),
            Survey.client_id.label("client_id"),
            func.row_number()
            .over(
                partition_by=Survey.client_id,
                order_by=(
                    Survey.completed_at.desc().nullslast(),
                    Survey.created_at.desc().nullslast(),
                    Survey.id.desc(),
                ),
            )
            .label("survey_rank"),
        )
        .filter(
            Survey.business_id == business_id,
            Survey.client_id.in_(risk_client_ids),
            Survey.status == "completed",
        )
        .subquery()
    )

    latest_surveys = (
        db.query(Survey)
        .join(
            ranked_surveys,
            Survey.id == ranked_surveys.c.survey_id,
        )
        .filter(
            ranked_surveys.c.survey_rank == 1,
            Survey.business_id == business_id,
        )
        .all()
    )

    surveys_by_client = {
        survey.client_id: survey
        for survey in latest_surveys
    }

    recovery_queue = []

    for client in risk_clients:
        latest_survey = surveys_by_client.get(client.id)

        recovery_queue.append({
            "client_id": client.id,
            "client_name": client.name,
            "client_email": client.email,
            "risk_status": client.status,
            "latest_nps": (
                latest_survey.nps_score
                if latest_survey
                else None
            ),
            "latest_satisfaction": (
                latest_survey.satisfaction_score
                if latest_survey
                else None
            ),
            "recommended_action": (
                "Contact client and offer recovery follow-up"
            ),
        })

    return recovery_queue
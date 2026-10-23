from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.survey import Survey
from app.models.visit import Visit
from app.schemas.survey import SurveyCreate, SurveyResponseUpdate


def create_survey(data: SurveyCreate, business_id: UUID, db: Session):
    visit = (
        db.query(Visit)
        .filter(
            Visit.id == data.visit_id,
            Visit.business_id == business_id,
        )
        .first()
    )

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Visit does not belong to this business.",
        )

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

    if visit.client_id != client.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Visit does not belong to the selected customer.",
        )

    existing_survey = (
        db.query(Survey)
        .filter(
            Survey.business_id == business_id,
            Survey.visit_id == visit.id,
        )
        .first()
    )

    if existing_survey:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A survey already exists for this visit.",
        )

    survey = Survey(
        business_id=business_id,
        visit_id=visit.id,
        client_id=client.id,
    )

    try:
        db.add(survey)
        db.commit()
        db.refresh(survey)
        return survey
    except Exception:
        db.rollback()
        raise


def get_surveys(business_id: UUID, db: Session):
    return (
        db.query(Survey)
        .filter(Survey.business_id == business_id)
        .order_by(Survey.created_at.desc())
        .all()
    )


def get_survey_by_id(survey_id: UUID, business_id: UUID, db: Session):
    return (
        db.query(Survey)
        .filter(
            Survey.id == survey_id,
            Survey.business_id == business_id,
        )
        .first()
    )


def update_survey_response(
    survey: Survey,
    data: SurveyResponseUpdate,
    db: Session,
):
    # Determine whether this is the first completion.
    was_completed = survey.status == "completed"

    update_data = data.model_dump(
        exclude_unset=True,
        exclude={"status"},
    )

    allowed_fields = {
        "satisfaction_score",
        "nps_score",
        "rebook_intent",
        "comment",
    }

    for key, value in update_data.items():
        if key in allowed_fields:
            setattr(survey, key, value)

    has_response = (
        survey.satisfaction_score is not None
        or survey.nps_score is not None
        or survey.rebook_intent is not None
        or bool(survey.comment and survey.comment.strip())
    )

    if not has_response:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one survey response is required.",
        )

    survey.status = "completed"

    if survey.completed_at is None:
        survey.completed_at = datetime.now(timezone.utc)

    is_negative_feedback = (
        (
            survey.satisfaction_score is not None
            and survey.satisfaction_score <= 2
        )
        or (
            survey.nps_score is not None
            and survey.nps_score <= 6
        )
    )

    try:
        # Only the initial completion may trigger automatic risk.
        if not was_completed and is_negative_feedback:
            client = (
                db.query(Client)
                .filter(
                    Client.id == survey.client_id,
                    Client.business_id == survey.business_id,
                )
                .first()
            )

            if client and client.status != "archived":
                client.status = "at_risk"

        db.commit()
        db.refresh(survey)
        return survey

    except Exception:
        db.rollback()
        raise
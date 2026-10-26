
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.survey import Survey
from app.models.visit import Visit
from app.schemas.survey import (
    PublicSurveySubmission,
    SurveyCreate,
    SurveyResponseUpdate,
)


def create_survey(
    data: SurveyCreate,
    business_id: UUID,
    db: Session,
):
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
            status_code=422,
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
            status_code=422,
            detail="Customer does not belong to this business.",
        )

    if visit.client_id != client.id:
        raise HTTPException(
            status_code=422,
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
            status_code=409,
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


def get_surveys(
    business_id: UUID,
    db: Session,
):
    return (
        db.query(Survey)
        .filter(Survey.business_id == business_id)
        .order_by(Survey.created_at.desc())
        .all()
    )


def get_survey_by_id(
    survey_id: UUID,
    business_id: UUID,
    db: Session,
):
    return (
        db.query(Survey)
        .filter(
            Survey.id == survey_id,
            Survey.business_id == business_id,
        )
        .first()
    )


def apply_negative_feedback_risk(
    survey: Survey,
    db: Session,
):
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

    if not is_negative_feedback:
        return

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


def update_survey_response(
    survey: Survey,
    data: SurveyResponseUpdate,
    db: Session,
):
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
            status_code=422,
            detail="At least one survey response is required.",
        )

    survey.status = "completed"

    if survey.completed_at is None:
        survey.completed_at = datetime.now(timezone.utc)

    try:
        if not was_completed:
            apply_negative_feedback_risk(survey, db)

        db.commit()
        db.refresh(survey)
        return survey

    except Exception:
        db.rollback()
        raise


def get_public_survey(
    token: str,
    db: Session,
):
    survey = (
        db.query(Survey)
        .filter(Survey.public_token == token)
        .first()
    )

    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey not found.",
        )

    return survey


def submit_public_survey_response(
    token: str,
    data: PublicSurveySubmission,
    db: Session,
):
    try:
        survey = (
            db.query(Survey)
            .filter(Survey.public_token == token)
            .with_for_update()
            .first()
        )

        if not survey:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Survey not found.",
            )

        if survey.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This survey has already been completed.",
            )

        if survey.status not in {"pending", "sent"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This survey is not available.",
            )

        survey.satisfaction_score = data.satisfaction_score
        survey.nps_score = data.nps_score
        survey.rebook_intent = data.rebook_intent
        survey.comment = data.comment

        survey.status = "completed"
        survey.completed_at = datetime.now(timezone.utc)

        apply_negative_feedback_risk(survey, db)

        db.commit()
        db.refresh(survey)

        return survey

    except Exception:
        db.rollback()
        raise

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.survey import Survey
from app.schemas.survey import SurveyCreate, SurveyResponseUpdate


def create_survey(data: SurveyCreate, business_id: str, db: Session):
    survey = Survey(
        business_id=business_id,
        visit_id=data.visit_id,
        client_id=data.client_id
    )

    db.add(survey)
    db.commit()
    db.refresh(survey)

    return survey


def get_surveys(business_id: str, db: Session):
    return db.query(Survey).filter(
        Survey.business_id == business_id
    ).all()


def get_survey_by_id(survey_id: str, business_id: str, db: Session):
    return db.query(Survey).filter(
        Survey.id == survey_id,
        Survey.business_id == business_id
    ).first()


def update_survey_response(
    survey: Survey,
    data: SurveyResponseUpdate,
    db: Session
):
    update_data = data.dict(exclude_unset=True)

    for key, value in update_data.items():
        setattr(survey, key, value)

    survey.status = "completed"
    survey.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(survey)

    return survey
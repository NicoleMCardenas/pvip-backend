from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User

from app.schemas.survey import (
    SurveyCreate,
    SurveyResponse,
    SurveyResponseUpdate
)

from app.surveys.service import (
    create_survey,
    get_surveys,
    get_survey_by_id,
    update_survey_response
)


router = APIRouter(
    prefix="/surveys",
    tags=["Surveys"]
)


@router.post("/", response_model=SurveyResponse)
def create_my_survey(
    data: SurveyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return create_survey(data, current_user.business_id, db)


@router.get("/", response_model=List[SurveyResponse])
def list_my_surveys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_surveys(current_user.business_id, db)


@router.get("/{survey_id}", response_model=SurveyResponse)
def get_my_survey(
    survey_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    survey = get_survey_by_id(
        survey_id,
        current_user.business_id,
        db
    )

    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encuesta no encontrada."
        )

    return survey


@router.patch("/{survey_id}/response", response_model=SurveyResponse)
def submit_survey_response(
    survey_id: UUID,
    data: SurveyResponseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    survey = get_survey_by_id(
        survey_id,
        current_user.business_id,
        db
    )

    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encuesta no encontrada."
        )

    return update_survey_response(
        survey,
        data,
        db
    )
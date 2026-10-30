
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User
from app.schemas.survey import (
    PublicSurveyResponse,
    PublicSurveySubmission,
    SurveyCreate,
    SurveyResponse,
    SurveyResponseUpdate,
)
from app.surveys.service import (
    create_survey,
    get_public_survey,
    get_survey_by_id,
    get_surveys,
    submit_public_survey_response,
    update_survey_response,
)


router = APIRouter(
    prefix="/surveys",
    tags=["Surveys"],
)


@router.post(
    "/",
    response_model=SurveyResponse,
)
def create_my_survey(
    data: SurveyCreate,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    return create_survey(
        data,
        current_user.business_id,
        db,
    )


@router.get(
    "/",
    response_model=List[SurveyResponse],
)
def list_my_surveys(
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    return get_surveys(
        current_user.business_id,
        db,
    )


# Public routes must be registered before /{survey_id}
# to avoid route matching conflicts.


@router.get(
    "/public/{token}",
    response_model=PublicSurveyResponse,
)
def get_survey_publicly(
    token: str,
    db: Session = Depends(get_db),
):
    return get_public_survey(token, db)


@router.post(
    "/public/{token}/responses",
    response_model=PublicSurveyResponse,
)
def submit_survey_publicly(
    token: str,
    data: PublicSurveySubmission,
    db: Session = Depends(get_db),
):
    return submit_public_survey_response(
        token,
        data,
        db,
    )


@router.get(
    "/{survey_id}",
    response_model=SurveyResponse,
)
def get_my_survey(
    survey_id: UUID,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    survey = get_survey_by_id(
        survey_id,
        current_user.business_id,
        db,
    )

    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encuesta no encontrada.",
        )

    return survey


@router.patch(
    "/{survey_id}/response",
    response_model=SurveyResponse,
)
def submit_survey_response(
    survey_id: UUID,
    data: SurveyResponseUpdate,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    survey = get_survey_by_id(
        survey_id,
        current_user.business_id,
        db,
    )

    if not survey:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encuesta no encontrada.",
        )

    return update_survey_response(
        survey,
        data,
        db,
    )

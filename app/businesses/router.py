from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.business import BusinessResponse, BusinessUpdate
from app.businesses.service import get_business_by_id, update_business


router = APIRouter(
    prefix="/business",
    tags=["Business"]
)


@router.get("/me", response_model=BusinessResponse)
def get_my_business(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    business = get_business_by_id(current_user.business_id, db)

    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Negocio no encontrado."
        )

    return business


@router.patch("/me", response_model=BusinessResponse)
def update_my_business(
    data: BusinessUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    business = get_business_by_id(current_user.business_id, db)

    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Negocio no encontrado."
        )

    return update_business(
        business,
        data.dict(exclude_unset=True),
        db
    )
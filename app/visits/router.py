from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User

from app.schemas.visit import (
    VisitCreate,
    VisitUpdate,
    VisitResponse
)

from app.visits.service import (
    create_visit,
    get_visits,
    get_visit_by_id,
    update_visit,
    delete_visit
)


router = APIRouter(
    prefix="/visits",
    tags=["Visits"]
)


@router.post("/", response_model=VisitResponse)
def create_my_visit(
    data: VisitCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return create_visit(data, current_user.business_id, db)


@router.get("/", response_model=List[VisitResponse])
def list_my_visits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_visits(current_user.business_id, db)


@router.get("/{visit_id}", response_model=VisitResponse)
def get_my_visit(
    visit_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    visit = get_visit_by_id(
        visit_id,
        current_user.business_id,
        db
    )

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visita no encontrada."
        )

    return visit


@router.patch("/{visit_id}", response_model=VisitResponse)
def update_my_visit(
    visit_id: UUID,
    data: VisitUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    visit = get_visit_by_id(
        visit_id,
        current_user.business_id,
        db
    )

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visita no encontrada."
        )

    return update_visit(visit, data, db)


@router.delete("/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_visit(
    visit_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    visit = get_visit_by_id(
        visit_id,
        current_user.business_id,
        db
    )

    if not visit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visita no encontrada."
        )

    delete_visit(visit, db)

    return None
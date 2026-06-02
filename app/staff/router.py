from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User

from app.schemas.staff import (
    StaffCreate,
    StaffUpdate,
    StaffResponse
)

from app.staff.service import (
    create_staff_member,
    get_staff_members,
    get_staff_member_by_id,
    update_staff_member,
    delete_staff_member
)


router = APIRouter(
    prefix="/staff",
    tags=["Staff"]
)


@router.post("/", response_model=StaffResponse)
def create_my_staff_member(
    data: StaffCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return create_staff_member(data, current_user.business_id, db)


@router.get("/", response_model=List[StaffResponse])
def list_my_staff_members(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_staff_members(current_user.business_id, db)


@router.get("/{staff_id}", response_model=StaffResponse)
def get_my_staff_member(
    staff_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    staff_member = get_staff_member_by_id(
        staff_id,
        current_user.business_id,
        db
    )

    if not staff_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff no encontrado."
        )

    return staff_member


@router.patch("/{staff_id}", response_model=StaffResponse)
def update_my_staff_member(
    staff_id: UUID,
    data: StaffUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    staff_member = get_staff_member_by_id(
        staff_id,
        current_user.business_id,
        db
    )

    if not staff_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff no encontrado."
        )

    return update_staff_member(staff_member, data, db)


@router.delete("/{staff_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_staff_member(
    staff_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    staff_member = get_staff_member_by_id(
        staff_id,
        current_user.business_id,
        db
    )

    if not staff_member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff no encontrado."
        )

    delete_staff_member(staff_member, db)

    return None
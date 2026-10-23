
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.staff import Staff
from app.schemas.staff import StaffCreate, StaffUpdate


def create_staff_member(
    data: StaffCreate,
    business_id: UUID,
    db: Session,
):
    staff_member = Staff(
        business_id=business_id,
        name=data.name,
        email=data.email,
        phone=data.phone,
        role=data.role,
        status="active",
    )

    db.add(staff_member)
    db.commit()
    db.refresh(staff_member)

    return staff_member


def get_staff_members(business_id: UUID, db: Session):
    return (
        db.query(Staff)
        .filter(Staff.business_id == business_id)
        .order_by(Staff.name.asc(), Staff.id.asc())
        .all()
    )


def get_staff_member_by_id(
    staff_id: UUID,
    business_id: UUID,
    db: Session,
):
    return (
        db.query(Staff)
        .filter(
            Staff.id == staff_id,
            Staff.business_id == business_id,
        )
        .first()
    )


def update_staff_member(
    staff_member: Staff,
    data: StaffUpdate,
    db: Session,
):
    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(staff_member, key, value)

    db.commit()
    db.refresh(staff_member)

    return staff_member


def delete_staff_member(staff_member: Staff, db: Session):
    # Preserve the employee and their historical visits.
    staff_member.status = "inactive"

    db.commit()
    db.refresh(staff_member)

    return staff_member

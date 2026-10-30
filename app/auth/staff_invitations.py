
import hashlib
import secrets

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password

from app.models.staff import Staff
from app.models.staff_invitation import StaffInvitation
from app.models.user import User


def generate_staff_invitation_token() -> str:
    return secrets.token_urlsafe(32)


def hash_staff_invitation_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def get_staff_invitation_expiration() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        hours=settings.staff_invitation_token_expire_hours
    )


def create_staff_invitation(
    db: Session,
    business_id,
    staff_id,
    email: str,
) -> str:
    normalized_email = email.strip().lower()

    if not normalized_email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El correo electrónico es obligatorio.",
        )

    staff = (
        db.query(Staff)
        .filter(
            Staff.id == staff_id,
            Staff.business_id == business_id,
        )
        .with_for_update()
        .first()
    )

    if staff is None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profesional no encontrado.",
        )

    if staff.status != "active":
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El profesional no está activo.",
        )

    existing_account = (
        db.query(User)
        .filter(
            (User.staff_id == staff.id)
            | (User.email == normalized_email)
        )
        .first()
    )

    if existing_account is not None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El profesional o el correo ya tiene una cuenta.",
        )

    now = datetime.now(timezone.utc)

    existing_invitations = (
        db.query(StaffInvitation)
        .filter(
            StaffInvitation.business_id == business_id,
            StaffInvitation.staff_id == staff.id,
            StaffInvitation.used_at.is_(None),
        )
        .all()
    )

    for invitation in existing_invitations:
        invitation.used_at = now

    raw_token = generate_staff_invitation_token()

    invitation = StaffInvitation(
        business_id=business_id,
        staff_id=staff.id,
        email=normalized_email,
        token_hash=hash_staff_invitation_token(raw_token),
        expires_at=get_staff_invitation_expiration(),
    )

    db.add(invitation)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No fue posible crear la invitación.",
        )

    return raw_token


def accept_staff_invitation(
    db: Session,
    token: str,
    password: str,
) -> bool:
    if not token or not token.strip():
        return False

    if len(password) < 8:
        return False

    invitation = (
        db.query(StaffInvitation)
        .filter(
            StaffInvitation.token_hash
            == hash_staff_invitation_token(token)
        )
        .with_for_update()
        .first()
    )

    if invitation is None:
        db.rollback()
        return False

    now = datetime.now(timezone.utc)

    if (
        invitation.used_at is not None
        or invitation.expires_at.tzinfo is None
        or invitation.expires_at <= now
    ):
        db.rollback()
        return False

    staff = (
        db.query(Staff)
        .filter(
            Staff.id == invitation.staff_id,
            Staff.business_id == invitation.business_id,
        )
        .with_for_update()
        .first()
    )

    if staff is None or staff.status != "active":
        db.rollback()
        return False

    existing_account = (
        db.query(User)
        .filter(
            (User.staff_id == staff.id)
            | (User.email == invitation.email)
        )
        .first()
    )

    if existing_account is not None:
        db.rollback()
        return False

    user = User(
        business_id=invitation.business_id,
        staff_id=staff.id,
        name=staff.name,
        email=invitation.email,
        password_hash=hash_password(password),
        role="staff",
        is_active=True,
    )

    db.add(user)
    invitation.used_at = now

    (
        db.query(StaffInvitation)
        .filter(
            StaffInvitation.staff_id == staff.id,
            StaffInvitation.id != invitation.id,
            StaffInvitation.used_at.is_(None),
        )
        .update(
            {"used_at": now},
            synchronize_session=False,
        )
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False

    return True

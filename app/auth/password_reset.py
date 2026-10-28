import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User


def generate_reset_token() -> str:
    """Generate a cryptographically secure password reset token."""
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """Hash a reset token before storing or looking it up."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_reset_token_expiration() -> datetime:
    """Calculate the expiration time in UTC."""
    return datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )


def is_reset_token_expired(expires_at: datetime) -> bool:
    """Check whether a reset token has expired."""
    if expires_at.tzinfo is None:
        raise ValueError(
            "Reset token expiration must include a timezone."
        )

    return expires_at <= datetime.now(timezone.utc)


def create_password_reset_token(
    db: Session,
    email: str,
) -> str | None:
    """
    Create a reset token for an existing user.

    Returns None for unknown emails or requests within cooldown.
    Existing reset links remain valid until used or expired.
    """

    normalized_email = email.strip().lower()
    now = datetime.now(timezone.utc)

    user = (
        db.query(User)
        .filter(User.email == normalized_email)
        .with_for_update()
        .first()
    )

    if user is None:
        db.rollback()
        return None

    latest_token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id)
        .order_by(
            PasswordResetToken.created_at.desc(),
            PasswordResetToken.id.desc(),
        )
        .first()
    )

    if latest_token is not None:
        cooldown_until = latest_token.created_at + timedelta(
            seconds=settings.password_reset_request_cooldown_seconds
        )

        if now < cooldown_until:
            db.rollback()
            return None

    raw_token = generate_reset_token()

    reset_record = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_reset_token(raw_token),
        expires_at=get_reset_token_expiration(),
    )

    db.add(reset_record)
    db.commit()

    return raw_token


def reset_password(
    db: Session,
    token: str,
    new_password: str,
) -> bool:
    """
    Consume a valid token and change the password atomically.

    Returns False for invalid, expired, or previously used tokens.
    """

    if not token or not token.strip():
        return False

    if len(new_password) < 8:
        return False

    token_hash = hash_reset_token(token)

    reset_record = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
        .first()
    )

    if reset_record is None:
        db.rollback()
        return False

    now = datetime.now(timezone.utc)

    if (
        reset_record.used_at is not None
        or is_reset_token_expired(reset_record.expires_at)
    ):
        db.rollback()
        return False

    user = (
        db.query(User)
        .filter(User.id == reset_record.user_id)
        .with_for_update()
        .first()
    )

    if user is None:
        db.rollback()
        return False

    user.password_hash = hash_password(new_password)
    user.token_version += 1

    reset_record.used_at = now

    (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != reset_record.id,
            PasswordResetToken.used_at.is_(None),
        )
        .update(
            {"used_at": now},
            synchronize_session=False,
        )
    )

    db.commit()

    return True
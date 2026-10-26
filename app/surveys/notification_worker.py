
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.survey import Survey
from app.models.survey_notification import SurveyNotification


LOCK_DURATION = timedelta(minutes=5)
MAX_DELIVERY_ATTEMPTS = 5
RETRY_BASE_DELAY = timedelta(minutes=2)


def claim_pending_notification(db: Session) -> SurveyNotification | None:
    """Reserve one eligible notification. Caller must commit before delivery."""
    now = datetime.now(timezone.utc)

    notification = (
        db.query(SurveyNotification)
        .filter(
            SurveyNotification.status == "pending",
            SurveyNotification.attempts < MAX_DELIVERY_ATTEMPTS,
            or_(
                SurveyNotification.next_attempt_at.is_(None),
                SurveyNotification.next_attempt_at <= now,
            ),
            or_(
                SurveyNotification.locked_until.is_(None),
                SurveyNotification.locked_until <= now,
            ),
        )
        .order_by(SurveyNotification.created_at, SurveyNotification.id)
        .with_for_update(skip_locked=True)
        .first()
    )

    if notification is None:
        return None

    notification.locked_until = now + LOCK_DURATION
    notification.lock_token = uuid.uuid4()
    notification.attempts += 1

    db.flush()
    return notification


def validate_notification(
    notification: SurveyNotification,
    db: Session,
) -> tuple[Survey, Client] | None:
    """Validate eligibility. Does not send email or commit."""
    survey = (
        db.query(Survey)
        .filter(Survey.id == notification.survey_id)
        .first()
    )

    if survey is None or survey.status != "pending" or not survey.public_token:
        notification.status = "cancelled"
        notification.locked_until = None
        notification.lock_token = None
        db.flush()
        return None

    client = (
        db.query(Client)
        .filter(
            Client.id == survey.client_id,
            Client.business_id == survey.business_id,
        )
        .first()
    )

    if client is None or client.status == "archived" or not client.email:
        notification.status = "cancelled"
        notification.locked_until = None
        notification.lock_token = None
        db.flush()
        return None

    try:
        validated_email = TypeAdapter(EmailStr).validate_python(client.email)
    except ValidationError:
        notification.status = "cancelled"
        notification.locked_until = None
        notification.lock_token = None
        db.flush()
        return None

    if notification.recipient_email != validated_email:
        notification.recipient_email = validated_email
        db.flush()

    return survey, client


def verify_notification_lock(
    notification_id: uuid.UUID,
    lock_token: uuid.UUID,
    db: Session,
) -> SurveyNotification:
    """Lock row and verify current reservation ownership until transaction end."""
    notification = (
        db.query(SurveyNotification)
        .filter(SurveyNotification.id == notification_id)
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )

    if notification is None:
        raise ValueError("Notification not found.")

    if notification.status not in {"pending", "sending"}:
        raise ValueError(
            "Notification is not in an active delivery state."
        )

    if notification.lock_token is None or notification.lock_token != lock_token:
        raise ValueError("Notification reservation token is invalid.")

    now = datetime.now(timezone.utc)

    if notification.locked_until is None or notification.locked_until <= now:
        raise ValueError("Notification reservation has expired.")

    return notification


def mark_notification_sent(
    notification_id: uuid.UUID,
    lock_token: uuid.UUID,
    provider_message_id: str,
    db: Session,
) -> None:
    """Record provider acceptance only for current reservation; does not commit."""
    notification = verify_notification_lock(
        notification_id,
        lock_token,
        db,
    )

    if not provider_message_id or not provider_message_id.strip():
        raise ValueError("A provider message ID is required.")

    notification.status = "sent"
    notification.provider_message_id = provider_message_id
    notification.sent_at = datetime.now(timezone.utc)
    notification.locked_until = None
    notification.lock_token = None
    notification.next_attempt_at = None
    notification.last_error = None

    db.flush()


def calculate_next_retry(
    attempts: int,
    now: datetime | None = None,
) -> datetime:
    """Exponential backoff for attempts 1 through 4."""
    if attempts < 1 or attempts >= MAX_DELIVERY_ATTEMPTS:
        raise ValueError(
            "Retry calculation requires an eligible attempt count."
        )

    if now is None:
        now = datetime.now(timezone.utc)

    return now + RETRY_BASE_DELAY * (2 ** (attempts - 1))


def mark_notification_failed(
    notification_id: uuid.UUID,
    lock_token: uuid.UUID,
    error: str,
    db: Session,
    permanent: bool = False,
) -> None:
    """Record failure only for current reservation; does not commit."""
    notification = verify_notification_lock(
        notification_id,
        lock_token,
        db,
    )

    if not error or not error.strip():
        raise ValueError("A delivery error description is required.")

    if notification.attempts < 1:
        raise ValueError(
            "A delivery attempt must be reserved first."
        )

    notification.last_error = error.strip()
    notification.locked_until = None
    notification.lock_token = None

    if permanent or notification.attempts >= MAX_DELIVERY_ATTEMPTS:
        notification.status = "failed"
        notification.next_attempt_at = None
    else:
        notification.status = "pending"
        notification.next_attempt_at = calculate_next_retry(
            notification.attempts
        )

    db.flush()


def mark_notification_uncertain(
    notification_id: uuid.UUID,
    lock_token: uuid.UUID,
    error: str,
    db: Session,
) -> None:
    """
    Record an uncertain provider outcome.

    An uncertain notification must not be retried automatically
    because the provider may already have accepted the email.

    Requires ownership of the current active reservation.
    Does not commit the transaction.
    """
    notification = verify_notification_lock(
        notification_id,
        lock_token,
        db,
    )

    if not error or not error.strip():
        raise ValueError(
            "An uncertainty description is required."
        )

    if notification.attempts < 1:
        raise ValueError(
            "A delivery attempt must be reserved first."
        )

    notification.status = "uncertain"
    notification.last_error = error.strip()
    notification.locked_until = None
    notification.lock_token = None
    notification.next_attempt_at = None

    db.flush()


def mark_notification_sending(
    notification_id: uuid.UUID,
    lock_token: uuid.UUID,
    db: Session,
) -> None:
    """
    Mark a reserved notification as sending before contacting
    the external email provider.

    The caller must commit this transition before the HTTP request.
    Sending notifications are not eligible for automatic claiming.
    """
    notification = verify_notification_lock(
        notification_id,
        lock_token,
        db,
    )

    if notification.status != "pending":
        raise ValueError(
            "Notification must be pending before sending."
        )

    if notification.attempts < 1:
        raise ValueError(
            "A delivery attempt must be reserved first."
        )

    notification.status = "sending"
    notification.next_attempt_at = None

    db.flush()

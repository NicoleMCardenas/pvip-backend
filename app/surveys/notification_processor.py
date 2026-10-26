
import uuid
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.survey_notification import SurveyNotification
from app.surveys.email_provider import (
    EmailDeliveryStatus,
    build_survey_url,
    send_survey_email,
)
from app.surveys.notification_worker import (
    claim_pending_notification,
    mark_notification_failed,
    mark_notification_sending,
    mark_notification_sent,
    mark_notification_uncertain,
    validate_notification,
)


class ProcessingStatus(str, Enum):
    DISABLED = "disabled"
    EMPTY = "empty"
    CANCELLED = "cancelled"
    SENT = "sent"
    FAILED = "failed"
    RETRY_SCHEDULED = "retry_scheduled"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class ProcessingResult:
    status: ProcessingStatus
    notification_id: uuid.UUID | None = None


def process_one_notification(
    *,
    db_factory=SessionLocal,
    email_sender=send_survey_email,
) -> ProcessingResult:
    """
    Process at most one notification.

    The sending state is committed before calling the provider.
    Unconfirmed deliveries are never retried automatically.
    """

    if not settings.email_sending_enabled:
        return ProcessingResult(ProcessingStatus.DISABLED)

    required_settings = {
        "RESEND_API_KEY": settings.resend_api_key,
        "EMAIL_FROM": settings.email_from,
        "SURVEY_PUBLIC_BASE_URL": settings.survey_public_base_url,
    }

    missing = [
        name
        for name, value in required_settings.items()
        if not value or not value.strip()
    ]

    if missing:
        raise RuntimeError(
            "Missing email configuration: " + ", ".join(missing)
        )

    notification_id = None
    lock_token = None
    recipient_email = None
    survey_url = None

    # Phase 1: reserve and validate.
    with db_factory() as db:
        try:
            notification = claim_pending_notification(db)

            if notification is None:
                db.rollback()
                return ProcessingResult(ProcessingStatus.EMPTY)

            notification_id = notification.id
            lock_token = notification.lock_token

            validated = validate_notification(notification, db)

            if validated is None:
                db.commit()
                return ProcessingResult(
                    ProcessingStatus.CANCELLED,
                    notification_id,
                )

            survey, client = validated

            recipient_email = notification.recipient_email
            survey_url = build_survey_url(
                settings.survey_public_base_url,
                str(survey.public_token),
            )

            # This commit makes the reservation visible to other workers.
            db.commit()

        except Exception:
            db.rollback()
            raise

    # Phase 2: record sending BEFORE contacting Resend.
    with db_factory() as db:
        try:
            mark_notification_sending(
                notification_id,
                lock_token,
                db,
            )
            db.commit()

        except Exception:
            db.rollback()
            raise

    # Phase 3: call the provider.
    # The key remains stable across attempts for this notification.
    idempotency_key = f"kairo-survey-{notification_id}"

    try:
        delivery = email_sender(
            api_key=settings.resend_api_key,
            email_from=settings.email_from,
            recipient_email=recipient_email,
            survey_url=survey_url,
            idempotency_key=idempotency_key,
        )
    except Exception:
        # The request might have reached the provider.
        # Leave the committed 'sending' state untouched.
        # It is excluded from automatic claiming.
        raise

    # Phase 4: persist the provider result.
    with db_factory() as db:
        try:
            if delivery.status == EmailDeliveryStatus.ACCEPTED:
                mark_notification_sent(
                    notification_id,
                    lock_token,
                    delivery.provider_message_id,
                    db,
                )
                result = ProcessingStatus.SENT

            elif delivery.status == EmailDeliveryStatus.REJECTED:
                mark_notification_failed(
                    notification_id,
                    lock_token,
                    delivery.error or "Provider rejected the email.",
                    db,
                    permanent=delivery.permanent,
                )

                updated = db.get(
                    SurveyNotification,
                    notification_id,
                )

                result = (
                    ProcessingStatus.FAILED
                    if updated.status == "failed"
                    else ProcessingStatus.RETRY_SCHEDULED
                )

            else:
                mark_notification_uncertain(
                    notification_id,
                    lock_token,
                    delivery.error or "Unknown provider outcome.",
                    db,
                )
                result = ProcessingStatus.UNCERTAIN

            db.commit()

            return ProcessingResult(
                result,
                notification_id,
            )

        except Exception:
            db.rollback()
            raise

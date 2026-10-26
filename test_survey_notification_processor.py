
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from app.surveys.email_provider import (
    EmailDeliveryResult,
    EmailDeliveryStatus,
)
from app.surveys.notification_processor import (
    ProcessingStatus,
    process_one_notification,
)


@dataclass
class FakeNotification:
    id: uuid.UUID
    lock_token: uuid.UUID
    recipient_email: str = "customer@example.com"
    status: str = "pending"
    attempts: int = 1
    public_token: str = "test-public-token"


class FakeSession:
    def __init__(self, notification):
        self.notification = notification
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def get(self, model, notification_id):
        return self.notification


class FakeDatabaseFactory:
    def __init__(self, notification):
        self.notification = notification
        self.sessions = []

    def __call__(self):
        session = FakeSession(self.notification)
        self.sessions.append(session)
        return session


def run_tests():
    notification = FakeNotification(
        id=uuid.uuid4(),
        lock_token=uuid.uuid4(),
    )

    factory = FakeDatabaseFactory(notification)

    settings = SimpleNamespace(
        email_sending_enabled=True,
        resend_api_key="test-api-key",
        email_from="KAIRO <test@example.com>",
        survey_public_base_url="https://example.com",
    )

    def claim(db):
        return notification

    def validate(item, db):
        return (
            SimpleNamespace(public_token=item.public_token),
            SimpleNamespace(email=item.recipient_email),
        )

    def sending(notification_id, lock_token, db):
        assert notification_id == notification.id
        assert lock_token == notification.lock_token
        notification.status = "sending"

    def sent(notification_id, lock_token, message_id, db):
        assert notification.status == "sending"
        assert message_id == "provider-message-123"
        notification.status = "sent"

    def failed(notification_id, lock_token, error, db, permanent=False):
        assert notification.status == "sending"
        notification.status = "failed" if permanent else "pending"

    def uncertain(notification_id, lock_token, error, db):
        assert notification.status == "sending"
        notification.status = "uncertain"

    patches = [
        patch(
            "app.surveys.notification_processor.settings",
            settings,
        ),
        patch(
            "app.surveys.notification_processor.claim_pending_notification",
            claim,
        ),
        patch(
            "app.surveys.notification_processor.validate_notification",
            validate,
        ),
        patch(
            "app.surveys.notification_processor.mark_notification_sending",
            sending,
        ),
        patch(
            "app.surveys.notification_processor.mark_notification_sent",
            sent,
        ),
        patch(
            "app.surveys.notification_processor.mark_notification_failed",
            failed,
        ),
        patch(
            "app.surveys.notification_processor.mark_notification_uncertain",
            uncertain,
        ),
    ]

    @contextmanager
    def mocked_environment():
        started = []
        try:
            for item in patches:
                item.start()
                started.append(item)
            yield
        finally:
            for item in reversed(started):
                item.stop()

    with mocked_environment():

        # TEST 1: Successful delivery.
        notification.status = "pending"
        factory.sessions.clear()

        def accepted_sender(**kwargs):
            assert notification.status == "sending"
            assert factory.sessions[1].commits == 1
            assert kwargs["idempotency_key"] == (
                f"kairo-survey-{notification.id}"
            )
            return EmailDeliveryResult(
                status=EmailDeliveryStatus.ACCEPTED,
                provider_message_id="provider-message-123",
            )

        result = process_one_notification(
            db_factory=factory,
            email_sender=accepted_sender,
        )

        assert result.status == ProcessingStatus.SENT
        assert notification.status == "sent"
        print("PASS: Successful provider delivery recorded")

        # TEST 2: Permanent rejection.
        notification.status = "pending"

        result = process_one_notification(
            db_factory=factory,
            email_sender=lambda **kwargs: EmailDeliveryResult(
                status=EmailDeliveryStatus.REJECTED,
                error="Invalid recipient",
                permanent=True,
            ),
        )

        assert result.status == ProcessingStatus.FAILED
        assert notification.status == "failed"
        print("PASS: Permanent provider rejection recorded")

        # TEST 3: Temporary rejection.
        notification.status = "pending"

        result = process_one_notification(
            db_factory=factory,
            email_sender=lambda **kwargs: EmailDeliveryResult(
                status=EmailDeliveryStatus.REJECTED,
                error="Temporary rejection",
                permanent=False,
            ),
        )

        assert result.status == ProcessingStatus.RETRY_SCHEDULED
        assert notification.status == "pending"
        print("PASS: Temporary rejection schedules retry")

        # TEST 4: Uncertain provider response.
        notification.status = "pending"

        result = process_one_notification(
            db_factory=factory,
            email_sender=lambda **kwargs: EmailDeliveryResult(
                status=EmailDeliveryStatus.UNCERTAIN,
                error="Provider timeout",
            ),
        )

        assert result.status == ProcessingStatus.UNCERTAIN
        assert notification.status == "uncertain"
        print("PASS: Uncertain provider outcome recorded")

        # TEST 5: Unexpected interruption.
        notification.status = "pending"

        def interrupted_sender(**kwargs):
            assert notification.status == "sending"
            raise RuntimeError("Simulated worker interruption")

        try:
            process_one_notification(
                db_factory=factory,
                email_sender=interrupted_sender,
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Interruption must propagate")

        assert notification.status == "sending"
        print("PASS: Interrupted sending remains protected")

    # TEST 6: Disabled sending.
    disabled_settings = SimpleNamespace(
        email_sending_enabled=False,
        resend_api_key=None,
        email_from=None,
        survey_public_base_url=None,
    )

    with patch(
        "app.surveys.notification_processor.settings",
        disabled_settings,
    ):
        result = process_one_notification(
            db_factory=factory,
            email_sender=lambda **kwargs: (
                (_ for _ in ()).throw(
                    AssertionError("Email must not be sent")
                )
            ),
        )

        assert result.status == ProcessingStatus.DISABLED
        print("PASS: Disabled email sending makes no provider request")

    print()
    print("ALL 6 SURVEY PROCESSOR TESTS PASSED")
    print("No real emails were sent.")


if __name__ == "__main__":
    run_tests()

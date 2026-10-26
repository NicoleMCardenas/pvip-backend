
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.business import Business
from app.models.client import Client
from app.models.service import Service
from app.models.staff import Staff
from app.models.survey import Survey
from app.models.survey_notification import SurveyNotification
from app.models.visit import Visit
from app.surveys.email_provider import (
    EmailDeliveryResult,
    EmailDeliveryStatus,
)
from app.surveys.notification_processor import (
    ProcessingStatus,
    process_one_notification,
)


def run_tests():
    database_url = os.environ.get("DATABASE_URL", "")

    if database_url.rsplit("/", 1)[-1] != "kairo_test":
        raise RuntimeError(
            "Integration test requires the kairo_test database."
        )

    engine = create_engine(database_url)
    SessionFactory = sessionmaker(bind=engine)

    business_id = uuid.uuid4()
    client_id = uuid.uuid4()
    service_id = uuid.uuid4()
    staff_id = uuid.uuid4()
    visit_id = uuid.uuid4()
    survey_id = uuid.uuid4()
    notification_id = uuid.uuid4()

    try:
        with SessionFactory.begin() as db:
            business = Business(
                id=business_id,
                name="KAIRO Integration Test",
            )
            db.add(business)
            db.flush()

            client = Client(
                id=client_id,
                business_id=business_id,
                name="Integration Client",
                email="integration@example.com",
                status="new",
            )
            db.add(client)

            service = Service(
                id=service_id,
                business_id=business_id,
                name="Integration Service",
            )
            db.add(service)

            staff = Staff(
                id=staff_id,
                business_id=business_id,
                name="Integration Staff",
            )
            db.add(staff)
            db.flush()

            visit = Visit(
                id=visit_id,
                business_id=business_id,
                client_id=client_id,
                service_id=service_id,
                staff_id=staff_id,
                visit_date=datetime.now(timezone.utc),
            )
            db.add(visit)
            db.flush()

            survey = Survey(
                id=survey_id,
                business_id=business_id,
                client_id=client_id,
                visit_id=visit_id,
                status="pending",
                public_token="integration-test-token",
            )
            db.add(survey)
            db.flush()

            notification = SurveyNotification(
                id=notification_id,
                survey_id=survey_id,
                recipient_email="integration@example.com",
                status="pending",
                attempts=0,
            )
            db.add(notification)

        print("PASS: Isolated PostgreSQL test records created")

        def fake_sender(**kwargs):
            assert kwargs["recipient_email"] == (
                "integration@example.com"
            )
            assert kwargs["idempotency_key"] == (
                f"kairo-survey-{notification_id}"
            )

            with SessionFactory() as db:
                current = db.get(
                    SurveyNotification,
                    notification_id,
                )
                assert current.status == "sending"

            print("PASS: Sending state committed before provider call")

            return EmailDeliveryResult(
                status=EmailDeliveryStatus.ACCEPTED,
                provider_message_id="integration-provider-123",
            )

        with patch(
            "app.surveys.notification_processor.settings.email_sending_enabled",
            True,
        ), patch(
            "app.surveys.notification_processor.settings.resend_api_key",
            "test-key",
        ), patch(
            "app.surveys.notification_processor.settings.email_from",
            "KAIRO <test@example.com>",
        ), patch(
            "app.surveys.notification_processor.settings.survey_public_base_url",
            "https://example.com",
        ):
            result = process_one_notification(
                db_factory=SessionFactory,
                email_sender=fake_sender,
            )

        assert result.status == ProcessingStatus.SENT
        assert result.notification_id == notification_id

        with SessionFactory() as db:
            stored = db.get(
                SurveyNotification,
                notification_id,
            )

            assert stored.status == "sent"
            assert stored.provider_message_id == (
                "integration-provider-123"
            )
            assert stored.sent_at is not None
            assert stored.lock_token is None
            assert stored.locked_until is None
            assert stored.next_attempt_at is None
            assert stored.attempts == 1

        print("PASS: Delivery persisted in PostgreSQL")
        print("PASS: Reservation released correctly")
        print("PASS: Delivery attempt recorded")
        print()
        print("ALL DATABASE INTEGRATION CHECKS PASSED")

    finally:
        with SessionFactory.begin() as db:
            db.query(SurveyNotification).filter_by(
                id=notification_id
            ).delete()
            db.query(Survey).filter_by(
                id=survey_id
            ).delete()
            db.query(Visit).filter_by(
                id=visit_id
            ).delete()
            db.query(Staff).filter_by(
                id=staff_id
            ).delete()
            db.query(Service).filter_by(
                id=service_id
            ).delete()
            db.query(Client).filter_by(
                id=client_id
            ).delete()
            db.query(Business).filter_by(
                id=business_id
            ).delete()

        engine.dispose()
        print("Temporary test records cleaned up.")
        print("No real emails were sent.")


if __name__ == "__main__":
    run_tests()

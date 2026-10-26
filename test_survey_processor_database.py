import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from app.db.session import SessionLocal, engine
from app.models.business import Business
from app.models.client import Client
from app.models.service import Service
from app.models.staff import Staff
from app.models.visit import Visit
from app.models.survey import Survey
from app.models.survey_notification import SurveyNotification
from app.schemas.visit import VisitCreate
from app.visits.service import create_visit
from app.surveys.email_provider import EmailDeliveryResult, EmailDeliveryStatus
from app.surveys.notification_processor import ProcessingStatus, process_one_notification


def run_tests():
    if engine.url.database != "kairo_test" or os.environ.get(
        "DATABASE_URL", ""
    ).rsplit("/", 1)[-1] != "kairo_test":
        raise RuntimeError("SAFETY STOP: This test requires kairo_test.")

    business_id = None
    service_id = None
    staff_id = None
    client_id = None
    visit_id = None
    survey_id = None
    notification_id = None

    try:
        with SessionLocal() as db:
            # The isolated database must start without pending notifications.
            assert db.query(SurveyNotification).count() == 0, (
                "Expected an empty notification table in kairo_test."
            )

            business = Business(
                name="KAIRO Integration Test",
                industry="Testing",
                email=f"integration-{uuid.uuid4().hex}@example.com",
            )
            db.add(business)
            db.flush()
            business_id = business.id

            service = Service(
                business_id=business_id,
                name="Integration Test Service",
                duration_minutes=30,
                price=Decimal("100"),
                status="active",
            )
            staff = Staff(
                business_id=business_id,
                name="Integration Test Staff",
                role="staff",
                status="active",
            )
            client = Client(
                business_id=business_id,
                name="Integration Test Client",
                email="integration-client@example.com",
                status="new",
                lifetime_value=Decimal("0"),
                total_visits=0,
            )
            db.add_all([service, staff, client])
            db.flush()
            service_id, staff_id, client_id = service.id, staff.id, client.id

            visit = create_visit(
                VisitCreate(
                    client_id=client_id,
                    service_id=service_id,
                    staff_id=staff_id,
                    visit_date=datetime.now(timezone.utc),
                    amount=Decimal("100"),
                ),
                business_id,
                db,
            )
            visit_id = visit.id

            survey = db.query(Survey).filter(
                Survey.visit_id == visit_id
            ).one()
            survey_id = survey.id

            notification = db.query(SurveyNotification).filter(
                SurveyNotification.survey_id == survey_id
            ).one()
            notification_id = notification.id

            assert notification.status == "pending"
            db.commit()

        print("PASS: Isolated business, visit, survey and notification created")

        calls = []

        def fake_sender(**kwargs):
            calls.append(kwargs)
            assert kwargs["recipient_email"] == "integration-client@example.com"
            assert kwargs["idempotency_key"] == f"kairo-survey-{notification_id}"
            assert kwargs["survey_url"].startswith("https://example.com/survey/")

            # A different database session must see the committed sending state.
            with SessionLocal() as db:
                current = db.get(SurveyNotification, notification_id)
                assert current.status == "sending"
                assert current.lock_token is not None
                assert current.locked_until is not None

            print("PASS: Sending state committed before provider invocation")

            return EmailDeliveryResult(
                status=EmailDeliveryStatus.ACCEPTED,
                provider_message_id="kairo-integration-test-message",
            )

        with patch(
            "app.surveys.notification_processor.settings.email_sending_enabled",
            True,
        ), patch(
            "app.surveys.notification_processor.settings.resend_api_key",
            "test-only-key",
        ), patch(
            "app.surveys.notification_processor.settings.email_from",
            "KAIRO <test@example.com>",
        ), patch(
            "app.surveys.notification_processor.settings.survey_public_base_url",
            "https://example.com",
        ):
            result = process_one_notification(
                db_factory=SessionLocal,
                email_sender=fake_sender,
            )

        assert result.status == ProcessingStatus.SENT
        assert result.notification_id == notification_id
        assert len(calls) == 1
        print("PASS: Mock email provider invoked exactly once")

        with SessionLocal() as db:
            stored = db.get(SurveyNotification, notification_id)
            assert stored.status == "sent"
            assert stored.provider_message_id == "kairo-integration-test-message"
            assert stored.sent_at is not None
            assert stored.attempts == 1
            assert stored.lock_token is None
            assert stored.locked_until is None
            assert stored.next_attempt_at is None

        print("PASS: Sent state and provider ID persisted in PostgreSQL")
        print("PASS: Lock released and attempts recorded")
        print()
        print("ALL DATABASE INTEGRATION CHECKS PASSED")

    finally:
        # Clean only records created by this test.
        with SessionLocal() as db:
            if notification_id is not None:
                db.query(SurveyNotification).filter_by(
                    id=notification_id
                ).delete(synchronize_session=False)
            if survey_id is not None:
                db.query(Survey).filter_by(
                    id=survey_id
                ).delete(synchronize_session=False)
            if visit_id is not None:
                db.query(Visit).filter_by(
                    id=visit_id
                ).delete(synchronize_session=False)
            if client_id is not None:
                db.query(Client).filter_by(
                    id=client_id
                ).delete(synchronize_session=False)
            if staff_id is not None:
                db.query(Staff).filter_by(
                    id=staff_id
                ).delete(synchronize_session=False)
            if service_id is not None:
                db.query(Service).filter_by(
                    id=service_id
                ).delete(synchronize_session=False)
            if business_id is not None:
                db.query(Business).filter_by(
                    id=business_id
                ).delete(synchronize_session=False)
            db.commit()

        print("Temporary test records cleaned up. No real emails sent.")


if __name__ == "__main__":
    run_tests()

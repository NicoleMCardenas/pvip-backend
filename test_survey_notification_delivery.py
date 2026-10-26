
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.business import Business
from app.models.client import Client
from app.models.service import Service
from app.models.staff import Staff
from app.models.survey import Survey
from app.models.survey_notification import SurveyNotification
from app.schemas.visit import VisitCreate
from app.visits.service import create_visit
from app.surveys.notification_worker import (
    claim_pending_notification,
    mark_notification_sent,
)


def expect_rejected(notification_id, lock_token, provider_message_id, db):
    try:
        mark_notification_sent(
            notification_id=notification_id,
            lock_token=lock_token,
            provider_message_id=provider_message_id,
            db=db,
        )
    except ValueError:
        return

    raise AssertionError("Invalid delivery registration must be rejected.")


def run_tests():
    connection = engine.connect()
    transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        business = db.query(Business).first()
        assert business is not None, (
            "A business is required to run this test."
        )

        service = Service(
            business_id=business.id,
            name="KAIRO Delivery Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="KAIRO Delivery Test Staff",
            role="staff",
            status="active",
        )

        client = Client(
            business_id=business.id,
            name="KAIRO Delivery Test Client",
            email="delivery-test@example.com",
            status="new",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )

        db.add_all([service, staff, client])
        db.flush()

        visit = create_visit(
            VisitCreate(
                client_id=client.id,
                service_id=service.id,
                staff_id=staff.id,
                visit_date=datetime.now(timezone.utc),
                amount=Decimal("100"),
            ),
            business.id,
            db,
        )

        survey = (
            db.query(Survey)
            .filter(Survey.visit_id == visit.id)
            .one()
        )

        notification = (
            db.query(SurveyNotification)
            .filter(SurveyNotification.survey_id == survey.id)
            .one()
        )

        # TEST 1: Reserve notification.
        claimed = claim_pending_notification(db)

        assert claimed is not None
        assert claimed.id == notification.id
        assert isinstance(claimed.lock_token, uuid.UUID)
        assert claimed.locked_until is not None

        token = claimed.lock_token

        print("PASS: Notification reserved for delivery")

        # TEST 2: Reject an incorrect token.
        expect_rejected(
            notification.id,
            uuid.uuid4(),
            "incorrect-token-message",
            db,
        )

        assert notification.status == "pending"
        assert notification.provider_message_id is None

        print("PASS: Incorrect delivery token rejected")

        # TEST 3: Reject an expired reservation.
        notification.locked_until = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        db.flush()

        expect_rejected(
            notification.id,
            token,
            "expired-token-message",
            db,
        )

        assert notification.status == "pending"
        assert notification.provider_message_id is None

        print("PASS: Expired delivery reservation rejected")

        # Restore active reservation for remaining tests.
        notification.locked_until = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        )
        db.flush()

        # TEST 4: Reject an empty provider message ID.
        expect_rejected(notification.id, token, "", db)

        assert notification.status == "pending"
        assert notification.provider_message_id is None

        print("PASS: Empty provider message ID rejected")

        # TEST 5: Record successful provider acceptance.
        mark_notification_sent(
            notification_id=notification.id,
            lock_token=token,
            provider_message_id="test-provider-message-123",
            db=db,
        )

        assert notification.status == "sent"
        assert notification.provider_message_id == "test-provider-message-123"
        assert notification.sent_at is not None
        assert notification.locked_until is None
        assert notification.lock_token is None
        assert notification.next_attempt_at is None
        assert notification.last_error is None

        print("PASS: Successful delivery recorded and token released")

        # TEST 6: Reject duplicate success registration.
        expect_rejected(
            notification.id,
            token,
            "duplicate-message",
            db,
        )

        assert notification.status == "sent"
        assert notification.provider_message_id == "test-provider-message-123"

        print("PASS: Duplicate success registration rejected")

        # TEST 7: Reject a replaced reservation token.
        notification.status = "pending"
        notification.provider_message_id = None
        notification.sent_at = None
        notification.lock_token = uuid.uuid4()
        notification.locked_until = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        )
        db.flush()

        replacement_token = notification.lock_token

        assert replacement_token != token

        expect_rejected(
            notification.id,
            token,
            "stale-worker-message",
            db,
        )

        assert notification.status == "pending"
        assert notification.lock_token == replacement_token
        assert notification.provider_message_id is None

        print("PASS: Replaced delivery token rejected")

        print()
        print("ALL SURVEY DELIVERY TESTS PASSED")

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()
        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()

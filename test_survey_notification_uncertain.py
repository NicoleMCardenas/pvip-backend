
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
from app.surveys.notification_worker import (
    claim_pending_notification,
    mark_notification_uncertain,
)
from app.visits.service import create_visit


def run_tests():
    connection = engine.connect()
    transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        business = db.query(Business).first()
        assert business is not None, "A business is required."

        service = Service(
            business_id=business.id,
            name="KAIRO Uncertain Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="KAIRO Uncertain Test Staff",
            role="staff",
            status="active",
        )

        client = Client(
            business_id=business.id,
            name="KAIRO Uncertain Test Client",
            email="uncertain-test@example.com",
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

        notification_id = notification.id

        # TEST 1: Reserve notification.
        claimed = claim_pending_notification(db)

        assert claimed is not None
        assert claimed.id == notification_id

        lock_token = claimed.lock_token
        assert isinstance(lock_token, uuid.UUID)

        print("PASS: Notification reserved for uncertain processing")

        # TEST 2: Reject an incorrect token.
        try:
            mark_notification_uncertain(
                notification_id,
                uuid.uuid4(),
                "Simulated uncertain outcome",
                db,
            )
        except ValueError:
            print("PASS: Incorrect uncertainty token rejected")
        else:
            raise AssertionError("Incorrect token must be rejected")

        # TEST 3: Reject an empty error description.
        try:
            mark_notification_uncertain(
                notification_id,
                lock_token,
                "   ",
                db,
            )
        except ValueError:
            print("PASS: Empty uncertainty description rejected")
        else:
            raise AssertionError("Empty description must be rejected")

        # TEST 4: Reject an expired reservation.
        notification.locked_until = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        db.flush()

        try:
            mark_notification_uncertain(
                notification_id,
                lock_token,
                "Simulated timeout",
                db,
            )
        except ValueError:
            print("PASS: Expired uncertainty reservation rejected")
        else:
            raise AssertionError("Expired reservation must be rejected")

        # Restore reservation for the next tests.
        notification.locked_until = (
            datetime.now(timezone.utc) + timedelta(minutes=5)
        )
        db.flush()

        # TEST 5: Register an uncertain outcome.
        mark_notification_uncertain(
            notification_id,
            lock_token,
            "Provider response could not be confirmed",
            db,
        )

        db.refresh(notification)

        assert notification.status == "uncertain"
        assert notification.last_error == (
            "Provider response could not be confirmed"
        )
        assert notification.lock_token is None
        assert notification.locked_until is None
        assert notification.next_attempt_at is None
        assert notification.provider_message_id is None
        assert notification.sent_at is None

        print("PASS: Uncertain outcome recorded safely")

        # TEST 6: Uncertain notification cannot be claimed again.
        claimed_again = claim_pending_notification(db)

        assert claimed_again is None

        print("PASS: Uncertain notification excluded from automatic retry")

        # TEST 7: Old token cannot change uncertain notification.
        try:
            mark_notification_uncertain(
                notification_id,
                lock_token,
                "Second uncertain result",
                db,
            )
        except ValueError:
            print("PASS: Released uncertainty token rejected")
        else:
            raise AssertionError("Released token must be rejected")

        print()
        print("ALL 7 SURVEY UNCERTAINTY TESTS PASSED")

    finally:
        db.close()
        transaction.rollback()
        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()

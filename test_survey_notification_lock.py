
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
    verify_notification_lock,
)


def expect_lock_rejected(notification_id, token, db, message):
    try:
        verify_notification_lock(
            notification_id=notification_id,
            lock_token=token,
            db=db,
        )
    except ValueError:
        return

    raise AssertionError(message)


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
            name="KAIRO Lock Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="KAIRO Lock Test Staff",
            role="staff",
            status="active",
        )

        client = Client(
            business_id=business.id,
            name="KAIRO Lock Test Client",
            email="lock-test@example.com",
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
            .filter(
                SurveyNotification.survey_id == survey.id
            )
            .one()
        )

        # TEST 1: New notification has no lock token.
        assert notification.lock_token is None

        print("PASS: New notification has no lock token")

        # TEST 2: Reserving generates a valid UUID.
        claimed = claim_pending_notification(db)

        assert claimed is not None
        assert claimed.id == notification.id
        assert isinstance(claimed.lock_token, uuid.UUID)
        assert claimed.locked_until is not None
        assert claimed.attempts == 1

        print("PASS: Reservation generates a UUID lock token")

        # TEST 3: Token is stored in the database transaction.
        expected_token = claimed.lock_token

        db.flush()
        db.expire(claimed, ["lock_token"])

        assert claimed.lock_token == expected_token

        print("PASS: Lock token stored in database transaction")

        # TEST 4: A valid active reservation is accepted.
        verified = verify_notification_lock(
            notification_id=notification.id,
            lock_token=expected_token,
            db=db,
        )

        assert verified.id == notification.id
        assert verified.lock_token == expected_token
        assert verified.status == "pending"

        print("PASS: Valid active reservation accepted")

        # TEST 5: An incorrect token is rejected.
        invalid_token = uuid.uuid4()

        assert invalid_token != expected_token

        expect_lock_rejected(
            notification.id,
            invalid_token,
            db,
            "An incorrect token must be rejected.",
        )

        assert notification.lock_token == expected_token
        assert notification.status == "pending"

        print("PASS: Incorrect reservation token rejected")

        # TEST 6: An expired reservation is rejected.
        notification.locked_until = (
            datetime.now(timezone.utc)
            - timedelta(minutes=1)
        )
        db.flush()

        expect_lock_rejected(
            notification.id,
            expected_token,
            db,
            "An expired reservation must be rejected.",
        )

        assert notification.status == "pending"
        assert notification.lock_token == expected_token

        print("PASS: Expired reservation rejected")

        # TEST 7: A non-pending notification is rejected.
        notification.status = "sent"
        notification.locked_until = (
            datetime.now(timezone.utc)
            + timedelta(minutes=5)
        )
        db.flush()

        expect_lock_rejected(
            notification.id,
            expected_token,
            db,
            "A sent notification must be rejected.",
        )

        assert notification.status == "sent"

        print("PASS: Non-pending notification rejected")

        # TEST 8: An old token cannot use a new reservation.
        notification.status = "pending"
        notification.lock_token = uuid.uuid4()
        notification.locked_until = (
            datetime.now(timezone.utc)
            + timedelta(minutes=5)
        )
        db.flush()

        replacement_token = notification.lock_token

        assert replacement_token != expected_token

        expect_lock_rejected(
            notification.id,
            expected_token,
            db,
            "An old reservation token must be rejected.",
        )

        assert notification.lock_token == replacement_token
        assert notification.status == "pending"

        verified_replacement = verify_notification_lock(
            notification_id=notification.id,
            lock_token=replacement_token,
            db=db,
        )

        assert verified_replacement.id == notification.id

        print("PASS: Old reservation token rejected")

        # TEST 9: Exhausted notifications cannot be reserved.
        notification.attempts = 5
        notification.locked_until = None
        notification.lock_token = None
        notification.next_attempt_at = None
        db.flush()

        exhausted_claim = claim_pending_notification(db)

        assert exhausted_claim is None
        assert notification.attempts == 5
        assert notification.lock_token is None

        print("PASS: Notification with 5 attempts cannot be reserved")

        print()
        print("ALL SURVEY LOCK TESTS PASSED")

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()

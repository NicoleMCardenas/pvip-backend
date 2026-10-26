
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
    mark_notification_failed,
)


def expect_failure_rejected(
    notification_id,
    lock_token,
    error,
    db,
    permanent=False,
):
    try:
        mark_notification_failed(
            notification_id=notification_id,
            lock_token=lock_token,
            error=error,
            db=db,
            permanent=permanent,
        )
    except ValueError:
        return

    raise AssertionError(
        "Invalid failure registration must be rejected."
    )


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
            name="KAIRO Failure Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="KAIRO Failure Test Staff",
            role="staff",
            status="active",
        )

        client = Client(
            business_id=business.id,
            name="KAIRO Failure Test Client",
            email="failure-test@example.com",
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

        # TEST 1: Reserve a notification.
        claimed = claim_pending_notification(db)

        assert claimed is not None
        assert claimed.id == notification.id
        assert claimed.attempts == 1
        assert isinstance(claimed.lock_token, uuid.UUID)

        token = claimed.lock_token

        print("PASS: Notification reserved for failure processing")

        # TEST 2: Reject an incorrect token.
        expect_failure_rejected(
            notification.id,
            uuid.uuid4(),
            "Incorrect token",
            db,
        )

        assert notification.status == "pending"
        assert notification.lock_token == token

        print("PASS: Incorrect failure token rejected")

        # TEST 3: Reject an expired reservation.
        notification.locked_until = (
            datetime.now(timezone.utc)
            - timedelta(minutes=1)
        )
        db.flush()

        expect_failure_rejected(
            notification.id,
            token,
            "Expired reservation",
            db,
        )

        assert notification.status == "pending"
        assert notification.lock_token == token

        print("PASS: Expired failure reservation rejected")

        # Restore active reservation.
        notification.locked_until = (
            datetime.now(timezone.utc)
            + timedelta(minutes=5)
        )
        db.flush()

        # TEST 4: Reject an empty error description.
        expect_failure_rejected(
            notification.id,
            token,
            "   ",
            db,
        )

        assert notification.status == "pending"
        assert notification.last_error is None

        print("PASS: Empty error description rejected")

        # TEST 5: A reserved attempt is required.
        notification.attempts = 0
        db.flush()

        expect_failure_rejected(
            notification.id,
            token,
            "Provider error",
            db,
        )

        assert notification.status == "pending"
        assert notification.last_error is None

        print("PASS: Failure without reserved attempt rejected")

        # Restore first attempt.
        notification.attempts = 1
        db.flush()

        # TEST 6: Temporary failure schedules retry.
        before = datetime.now(timezone.utc)

        mark_notification_failed(
            notification_id=notification.id,
            lock_token=token,
            error="Temporary provider error",
            db=db,
        )

        after = datetime.now(timezone.utc)

        assert notification.status == "pending"
        assert notification.last_error == "Temporary provider error"
        assert notification.locked_until is None
        assert notification.lock_token is None
        assert notification.next_attempt_at is not None

        expected_delay = timedelta(minutes=2)

        assert (
            before + expected_delay
            <= notification.next_attempt_at
            <= after + expected_delay
        )

        print("PASS: Temporary failure schedules retry")

        # TEST 7: Reject reused token after failure.
        expect_failure_rejected(
            notification.id,
            token,
            "Another error",
            db,
        )

        assert notification.last_error == "Temporary provider error"

        print("PASS: Released failure token cannot be reused")

        # TEST 8: Permanent failure stops retries.
        notification.attempts = 2
        notification.next_attempt_at = None
        notification.lock_token = uuid.uuid4()
        notification.locked_until = (
            datetime.now(timezone.utc)
            + timedelta(minutes=5)
        )
        db.flush()

        permanent_token = notification.lock_token

        mark_notification_failed(
            notification_id=notification.id,
            lock_token=permanent_token,
            error="Permanent provider rejection",
            db=db,
            permanent=True,
        )

        assert notification.status == "failed"
        assert notification.last_error == (
            "Permanent provider rejection"
        )
        assert notification.next_attempt_at is None
        assert notification.locked_until is None
        assert notification.lock_token is None

        print("PASS: Permanent failure stops retries")

        # TEST 9: Failed notification rejects further updates.
        expect_failure_rejected(
            notification.id,
            permanent_token,
            "Another error",
            db,
        )

        assert notification.status == "failed"

        print("PASS: Failed notification rejects further updates")

        # TEST 10: Maximum attempts stop retries.
        notification.status = "pending"
        notification.attempts = 5
        notification.lock_token = uuid.uuid4()
        notification.locked_until = (
            datetime.now(timezone.utc)
            + timedelta(minutes=5)
        )
        db.flush()

        final_token = notification.lock_token

        mark_notification_failed(
            notification_id=notification.id,
            lock_token=final_token,
            error="Maximum attempts reached",
            db=db,
        )

        assert notification.status == "failed"
        assert notification.next_attempt_at is None
        assert notification.locked_until is None
        assert notification.lock_token is None

        print("PASS: Maximum attempts stop retries")

        # TEST 11: Replaced token cannot register failure.
        notification.status = "pending"
        notification.attempts = 2
        notification.last_error = None
        notification.lock_token = uuid.uuid4()
        notification.locked_until = (
            datetime.now(timezone.utc)
            + timedelta(minutes=5)
        )
        db.flush()

        replacement_token = notification.lock_token

        assert replacement_token != final_token

        expect_failure_rejected(
            notification.id,
            final_token,
            "Stale worker error",
            db,
        )

        assert notification.status == "pending"
        assert notification.lock_token == replacement_token
        assert notification.last_error is None

        print("PASS: Replaced failure token rejected")

        print()
        print("ALL SURVEY FAILURE TESTS PASSED")

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()

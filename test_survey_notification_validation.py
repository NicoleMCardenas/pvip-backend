
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
from app.surveys.notification_worker import validate_notification


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
            name="KAIRO Validation Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="KAIRO Validation Test Staff",
            role="staff",
            status="active",
        )

        client = Client(
            business_id=business.id,
            name="KAIRO Validation Test Client",
            email="validation-test@example.com",
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

        original_token = survey.public_token

        def reset_notification():
            survey.status = "pending"
            survey.public_token = original_token

            client.status = "new"
            client.email = "validation-test@example.com"

            notification.status = "pending"
            notification.recipient_email = client.email
            notification.locked_until = None
            notification.lock_token = None

            db.flush()

        def reserve_notification():
            notification.lock_token = uuid.uuid4()
            notification.locked_until = (
                datetime.now(timezone.utc)
                + timedelta(minutes=5)
            )
            db.flush()

        def assert_cancelled_and_released():
            assert notification.status == "cancelled"
            assert notification.locked_until is None
            assert notification.lock_token is None

        # TEST 1: Valid notification.
        result = validate_notification(notification, db)

        assert result is not None
        assert result[0].id == survey.id
        assert result[1].id == client.id
        assert notification.status == "pending"

        print("PASS: Valid notification accepted")

        # TEST 2: Completed survey.
        reset_notification()
        reserve_notification()

        survey.status = "completed"
        db.flush()

        result = validate_notification(notification, db)

        assert result is None
        assert_cancelled_and_released()

        print("PASS: Completed survey cancels and releases token")

        # TEST 3: Archived client.
        reset_notification()
        reserve_notification()

        client.status = "archived"
        db.flush()

        result = validate_notification(notification, db)

        assert result is None
        assert_cancelled_and_released()

        print("PASS: Archived client cancels and releases token")

        # TEST 4: Client without email.
        reset_notification()
        reserve_notification()

        client.email = None
        db.flush()

        result = validate_notification(notification, db)

        assert result is None
        assert_cancelled_and_released()

        print("PASS: Missing email cancels and releases token")

        # TEST 5: Invalid email.
        reset_notification()
        reserve_notification()

        client.email = "invalid-email"
        db.flush()

        result = validate_notification(notification, db)

        assert result is None
        assert_cancelled_and_released()

        print("PASS: Invalid email cancels and releases token")

        # TEST 6: Updated client email.
        reset_notification()

        client.email = "updated-test@example.com"
        db.flush()

        result = validate_notification(notification, db)

        assert result is not None
        assert notification.recipient_email == (
            "updated-test@example.com"
        )
        assert notification.status == "pending"

        print("PASS: Updated email replaces recipient")

        # TEST 7: Survey without public token.
        reset_notification()
        reserve_notification()

        survey.public_token = None
        db.flush()

        result = validate_notification(notification, db)

        assert result is None
        assert_cancelled_and_released()

        print("PASS: Missing public token cancels and releases token")

        print()
        print("ALL SURVEY VALIDATION TESTS PASSED")

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()

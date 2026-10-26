
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
from app.surveys.notification_worker import claim_pending_notification


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
            name="KAIRO Notification Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="KAIRO Notification Test Staff",
            role="staff",
            status="active",
        )

        client_with_email = Client(
            business_id=business.id,
            name="KAIRO Notification Test With Email",
            email="survey-test@example.com",
            status="new",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )

        client_without_email = Client(
            business_id=business.id,
            name="KAIRO Notification Test Without Email",
            email=None,
            status="new",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )

        db.add_all([
            service,
            staff,
            client_with_email,
            client_without_email,
        ])
        db.flush()

        # TEST 1: Visit with email creates a pending notification.
        visit_with_email = create_visit(
            VisitCreate(
                client_id=client_with_email.id,
                service_id=service.id,
                staff_id=staff.id,
                visit_date=datetime.now(timezone.utc),
                amount=Decimal("100"),
            ),
            business.id,
            db,
        )

        survey_with_email = (
            db.query(Survey)
            .filter(Survey.visit_id == visit_with_email.id)
            .one()
        )

        notification = (
            db.query(SurveyNotification)
            .filter(
                SurveyNotification.survey_id
                == survey_with_email.id
            )
            .one()
        )

        assert survey_with_email.status == "pending"
        assert survey_with_email.public_token is not None

        assert notification.recipient_email == (
            "survey-test@example.com"
        )
        assert notification.status == "pending"
        assert notification.attempts == 0
        assert notification.sent_at is None
        assert notification.provider_message_id is None

        assert (
            db.query(SurveyNotification)
            .filter(
                SurveyNotification.survey_id
                == survey_with_email.id
            )
            .count()
        ) == 1

        print("PASS: Visit with email creates pending notification")

        # TEST 2: Visit without email creates no notification.
        visit_without_email = create_visit(
            VisitCreate(
                client_id=client_without_email.id,
                service_id=service.id,
                staff_id=staff.id,
                visit_date=datetime.now(timezone.utc),
                amount=Decimal("100"),
            ),
            business.id,
            db,
        )

        survey_without_email = (
            db.query(Survey)
            .filter(Survey.visit_id == visit_without_email.id)
            .one()
        )

        assert survey_without_email.status == "pending"
        assert survey_without_email.public_token is not None

        assert (
            db.query(SurveyNotification)
            .filter(
                SurveyNotification.survey_id
                == survey_without_email.id
            )
            .count()
        ) == 0

        print("PASS: Visit without email creates no notification")

        # TEST 3: Reserve a pending notification.
        claimed = claim_pending_notification(db)

        assert claimed is not None
        assert claimed.id == notification.id
        assert claimed.status == "pending"
        assert claimed.attempts == 1
        assert claimed.locked_until is not None
        assert claimed.locked_until > datetime.now(timezone.utc)

        print("PASS: Pending notification reserved")

        # TEST 4: A reserved notification cannot be claimed again.
        second_claim = claim_pending_notification(db)

        assert second_claim is None

        print("PASS: Reserved notification not selected again")

        # TEST 5: A future retry is not eligible.
        notification.locked_until = None
        notification.next_attempt_at = (
            datetime.now(timezone.utc) + timedelta(hours=1)
        )
        db.flush()

        future_claim = claim_pending_notification(db)

        assert future_claim is None
        assert notification.attempts == 1

        print("PASS: Future retry not selected")

        print()
        print("ALL SURVEY NOTIFICATION TESTS PASSED")

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()

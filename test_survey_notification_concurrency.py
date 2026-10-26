
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text

from app.db.session import SessionLocal
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


def run_tests():
    setup_db = SessionLocal()
    worker_a = SessionLocal()
    worker_b = SessionLocal()

    service_id = None
    staff_id = None
    client_id = None
    visit_id = None
    survey_id = None
    notification_id = None

    try:
        business = setup_db.query(Business).first()
        assert business is not None, "A business is required."

        service = Service(
            business_id=business.id,
            name="KAIRO Concurrency Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="KAIRO Concurrency Test Staff",
            role="staff",
            status="active",
        )

        client = Client(
            business_id=business.id,
            name="KAIRO Concurrency Test Client",
            email="concurrency-test@example.com",
            status="new",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )

        setup_db.add_all([service, staff, client])
        setup_db.flush()

        service_id = service.id
        staff_id = staff.id
        client_id = client.id

        visit = create_visit(
            VisitCreate(
                client_id=client.id,
                service_id=service.id,
                staff_id=staff.id,
                visit_date=datetime.now(timezone.utc),
                amount=Decimal("100"),
            ),
            business.id,
            setup_db,
        )

        visit_id = visit.id

        survey = (
            setup_db.query(Survey)
            .filter(Survey.visit_id == visit.id)
            .one()
        )
        survey_id = survey.id

        notification = (
            setup_db.query(SurveyNotification)
            .filter(SurveyNotification.survey_id == survey.id)
            .one()
        )
        notification_id = notification.id

        setup_db.commit()

        # Restrict workers to the test notification.
        # Existing pending notifications must not be processed.
        worker_a.execute(
            text(
                "UPDATE survey_notifications "
                "SET next_attempt_at = NOW() + INTERVAL '1 hour' "
                "WHERE id = :notification_id"
            ),
            {"notification_id": notification_id},
        )
        worker_a.commit()

        worker_a.execute(
            text(
                "UPDATE survey_notifications "
                "SET next_attempt_at = NULL "
                "WHERE id = :notification_id"
            ),
            {"notification_id": notification_id},
        )
        worker_a.commit()

        # TEST 1: Worker A reserves notification.
        claimed_a = claim_pending_notification(worker_a)

        assert claimed_a is not None
        assert claimed_a.id == notification_id

        token_a = claimed_a.lock_token
        assert isinstance(token_a, uuid.UUID)

        print("PASS: Worker A reserved notification")

        # TEST 2: Worker B cannot claim row locked by A.
        worker_b.execute(
            text("SET LOCAL lock_timeout = '2s'")
        )

        claimed_b = claim_pending_notification(worker_b)

        assert claimed_b is None

        worker_b.rollback()

        print("PASS: Worker B cannot claim locked notification")

        # Commit A's reservation.
        worker_a.commit()

        # TEST 3: B cannot claim an active reservation.
        claimed_b = claim_pending_notification(worker_b)

        assert claimed_b is None

        worker_b.rollback()

        print("PASS: Active reservation prevents second claim")

        # Simulate expiration of A's reservation.
        worker_a.execute(
            text(
                "UPDATE survey_notifications "
                "SET locked_until = NOW() - INTERVAL '1 minute' "
                "WHERE id = :notification_id"
            ),
            {"notification_id": notification_id},
        )
        worker_a.commit()

        # TEST 4: B recovers expired reservation.
        claimed_b = claim_pending_notification(worker_b)

        assert claimed_b is not None
        assert claimed_b.id == notification_id

        token_b = claimed_b.lock_token

        assert token_b != token_a

        worker_b.commit()

        print("PASS: Worker B recovered expired reservation")

        # TEST 5: A's old token cannot register delivery.
        try:
            mark_notification_sent(
                notification_id=notification_id,
                lock_token=token_a,
                provider_message_id="stale-worker-message",
                db=worker_a,
            )
        except ValueError:
            worker_a.rollback()
        else:
            raise AssertionError(
                "Old worker token must be rejected."
            )

        print("PASS: Stale worker cannot register delivery")

        # TEST 6: B's current token can register delivery.
        mark_notification_sent(
            notification_id=notification_id,
            lock_token=token_b,
            provider_message_id="current-worker-message",
            db=worker_b,
        )

        worker_b.commit()

        worker_a.expire_all()

        final_notification = (
            worker_a.query(SurveyNotification)
            .filter(SurveyNotification.id == notification_id)
            .one()
        )

        assert final_notification.status == "sent"
        assert final_notification.provider_message_id == (
            "current-worker-message"
        )
        assert final_notification.lock_token is None
        assert final_notification.locked_until is None

        worker_a.rollback()

        print("PASS: Current worker safely recorded delivery")
        print()
        print("ALL SURVEY CONCURRENCY TESTS PASSED")

    finally:
        worker_a.rollback()
        worker_b.rollback()
        setup_db.rollback()

        worker_a.close()
        worker_b.close()

        if notification_id is not None:
            cleanup_db = SessionLocal()
            try:
                cleanup_db.query(SurveyNotification).filter(
                    SurveyNotification.id == notification_id
                ).delete(synchronize_session=False)

                if survey_id is not None:
                    cleanup_db.query(Survey).filter(
                        Survey.id == survey_id
                    ).delete(synchronize_session=False)

                if visit_id is not None:
                    from app.models.visit import Visit
                    cleanup_db.query(Visit).filter(
                        Visit.id == visit_id
                    ).delete(synchronize_session=False)

                if client_id is not None:
                    cleanup_db.query(Client).filter(
                        Client.id == client_id
                    ).delete(synchronize_session=False)

                if staff_id is not None:
                    cleanup_db.query(Staff).filter(
                        Staff.id == staff_id
                    ).delete(synchronize_session=False)

                if service_id is not None:
                    cleanup_db.query(Service).filter(
                        Service.id == service_id
                    ).delete(synchronize_session=False)

                cleanup_db.commit()

                print("Temporary test records cleaned up.")

            except Exception:
                cleanup_db.rollback()
                print(
                    "WARNING: Automatic cleanup failed. "
                    "Review temporary test records."
                )
                raise

            finally:
                cleanup_db.close()


if __name__ == "__main__":
    run_tests()

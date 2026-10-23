from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.analytics.service import (
    get_dashboard_metrics,
    get_recovery_queue,
    get_risk_clients,
)
from app.clients.service import (
    archive_client,
    restore_client,
    update_client,
)
from app.db.session import engine
from app.models.business import Business
from app.models.client import Client
from app.models.service import Service
from app.models.staff import Staff
from app.models.survey import Survey
from app.models.visit import Visit
from app.schemas.client import ClientUpdate
from app.schemas.survey import SurveyResponseUpdate
from app.surveys.service import update_survey_response


def run_tests():
    connection = engine.connect()
    outer_transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="rollback_only",
    )

    try:
        business = db.query(Business).first()

        assert business is not None, (
            "No business available for testing."
        )

        # Use an isolated business so existing business metrics
        # do not influence the test results.
        test_business = Business(
    name=f"KAIRO Analytics Test {uuid4().hex[:8]}",
    industry="Software Testing",
    email=f"kairo-analytics-{uuid4().hex}@example.com",
        )

        db.add(test_business)
        db.flush()

        business_id = test_business.id

        client = Client(
            business_id=business_id,
            name="KAIRO Analytics Test Customer",
            status="active",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )

        service = Service(
            business_id=business_id,
            name="KAIRO Analytics Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business_id,
            name="KAIRO Analytics Test Staff",
            role="staff",
            status="active",
        )

        db.add_all([client, service, staff])
        db.flush()

        now = datetime.now(timezone.utc)

        visit = Visit(
            business_id=business_id,
            client_id=client.id,
            service_id=service.id,
            staff_id=staff.id,
            visit_date=now - timedelta(days=3),
            amount=Decimal("100"),
        )

        db.add(visit)
        db.flush()

        # TEST 1: Initial dashboard metrics.
        metrics = get_dashboard_metrics(business_id, db)

        assert metrics["total_clients"] == 1
        assert metrics["at_risk_clients"] == 0
        assert metrics["total_surveys"] == 0
        assert metrics["average_satisfaction"] is None
        assert metrics["nps_score"] is None

        assert get_risk_clients(business_id, db) == []
        assert get_recovery_queue(business_id, db) == []

        print("PASS: Initial dashboard metrics")

        # TEST 2: Negative survey triggers risk.
        negative_survey = Survey(
            business_id=business_id,
            client_id=client.id,
            visit_id=visit.id,
            status="pending",
        )

        db.add(negative_survey)
        db.flush()

        update_survey_response(
            negative_survey,
            SurveyResponseUpdate(
                satisfaction_score=2,
                nps_score=3,
            ),
            db,
        )

        db.refresh(client)

        assert client.status == "at_risk"
        assert negative_survey.status == "completed"
        assert negative_survey.completed_at is not None

        metrics = get_dashboard_metrics(business_id, db)

        assert metrics["total_surveys"] == 1
        assert metrics["completed_surveys"] == 1
        assert metrics["at_risk_clients"] == 1
        assert metrics["average_satisfaction"] == 2
        assert metrics["nps_score"] == -100

        risk_clients = get_risk_clients(business_id, db)
        queue = get_recovery_queue(business_id, db)

        assert len(risk_clients) == 1
        assert risk_clients[0].id == client.id
        assert len(queue) == 1
        assert queue[0]["client_id"] == client.id
        assert queue[0]["latest_nps"] == 3
        assert queue[0]["latest_satisfaction"] == 2

        print("PASS: Negative survey triggers customer risk")

        # TEST 3: Manual recovery updates Analytics.
        update_client(
            client,
            ClientUpdate(status="active"),
            db,
        )

        metrics = get_dashboard_metrics(business_id, db)

        assert client.status == "active"
        assert metrics["at_risk_clients"] == 0
        assert get_risk_clients(business_id, db) == []
        assert get_recovery_queue(business_id, db) == []

        print("PASS: Manual recovery updates Analytics")

        # TEST 4: Editing historical feedback preserves recovery.
        original_completed_at = negative_survey.completed_at

        update_survey_response(
            negative_survey,
            SurveyResponseUpdate(
                satisfaction_score=1,
                nps_score=0,
            ),
            db,
        )

        db.refresh(client)

        assert client.status == "active"
        assert negative_survey.completed_at == original_completed_at
        assert get_dashboard_metrics(
            business_id, db
        )["at_risk_clients"] == 0

        print("PASS: Historical edits preserve recovery")

        # TEST 5: Positive survey does not change customer status.
        second_visit = Visit(
            business_id=business_id,
            client_id=client.id,
            service_id=service.id,
            staff_id=staff.id,
            visit_date=now - timedelta(days=1),
            amount=Decimal("100"),
        )

        db.add(second_visit)
        db.flush()

        positive_survey = Survey(
            business_id=business_id,
            client_id=client.id,
            visit_id=second_visit.id,
            status="pending",
        )

        db.add(positive_survey)
        db.flush()

        update_survey_response(
            positive_survey,
            SurveyResponseUpdate(
                satisfaction_score=5,
                nps_score=10,
            ),
            db,
        )

        db.refresh(client)

        assert client.status == "active"

        metrics = get_dashboard_metrics(business_id, db)

        assert metrics["total_surveys"] == 2
        assert metrics["completed_surveys"] == 2
        assert metrics["average_satisfaction"] == 3
        assert metrics["nps_score"] == 0
        assert metrics["at_risk_clients"] == 0

        print("PASS: Positive survey and historical metrics")

        # TEST 6: Latest survey appears in Recovery Queue.
        update_client(
            client,
            ClientUpdate(status="at_risk"),
            db,
        )

        queue = get_recovery_queue(business_id, db)

        assert len(queue) == 1
        assert queue[0]["latest_nps"] == 10
        assert queue[0]["latest_satisfaction"] == 5

        print("PASS: Recovery Queue uses latest survey")

        # TEST 7: Archived customers are excluded.
        archive_client(client, db)

        assert client.status == "archived"

        metrics = get_dashboard_metrics(business_id, db)

        assert metrics["total_clients"] == 0
        assert metrics["at_risk_clients"] == 0
        assert get_risk_clients(business_id, db) == []
        assert get_recovery_queue(business_id, db) == []

        print("PASS: Archived customers excluded")

        # TEST 8: Restore previous customer status.
        restore_client(client, db)

        assert client.status == "at_risk"

        metrics = get_dashboard_metrics(business_id, db)

        assert metrics["total_clients"] == 1
        assert metrics["at_risk_clients"] == 1

        print("PASS: Customer restoration preserves status")

        # TEST 9: Other business data remains isolated.
        other_business_metrics = get_dashboard_metrics(
            business.id,
            db,
        )

        assert other_business_metrics["total_clients"] >= 0

        other_business_queue = get_recovery_queue(
            business.id,
            db,
        )

        assert all(
            item["client_id"] != client.id
            for item in other_business_queue
        )

        print("PASS: Business isolation")

        print()
        print("ALL ANALYTICS TESTS PASSED")

    finally:
        db.close()

        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()

def check_analytics_sprint2():
    run_tests()
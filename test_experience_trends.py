from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.analytics.trends import get_experience_trends
from app.db.session import engine
from app.models.business import Business
from app.models.client import Client
from app.models.service import Service
from app.models.staff import Staff
from app.models.survey import Survey
from app.models.visit import Visit


AS_OF = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)


def run_tests():
    connection = engine.connect()
    transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="rollback_only",
    )

    try:
        business = Business(
            name=f"KAIRO Trends Test {uuid4().hex[:8]}",
            industry="Software Testing",
            email=f"trends-{uuid4().hex}@example.com",
        )

        other_business = Business(
            name=f"KAIRO Trends Isolation {uuid4().hex[:8]}",
            industry="Software Testing",
            email=f"trends-other-{uuid4().hex}@example.com",
        )

        db.add_all([business, other_business])
        db.flush()

        def create_references(target_business):
            client = Client(
                business_id=target_business.id,
                name="Trends Test Customer",
                status="active",
                total_visits=0,
                lifetime_value=0,
            )

            service = Service(
                business_id=target_business.id,
                name="Trends Test Service",
                duration_minutes=30,
                price=100,
                status="active",
            )

            staff = Staff(
                business_id=target_business.id,
                name="Trends Test Staff",
                role="staff",
                status="active",
            )

            db.add_all([client, service, staff])
            db.flush()

            return client, service, staff

        client, service, staff = create_references(business)

        other_client, other_service, other_staff = (
            create_references(other_business)
        )

        def create_survey(
            target_business,
            target_client,
            target_service,
            target_staff,
            completed_at,
            satisfaction,
            nps,
            survey_status="completed",
        ):
            visit = Visit(
                business_id=target_business.id,
                client_id=target_client.id,
                service_id=target_service.id,
                staff_id=target_staff.id,
                visit_date=completed_at,
                amount=100,
            )

            db.add(visit)
            db.flush()

            survey = Survey(
                business_id=target_business.id,
                visit_id=visit.id,
                client_id=target_client.id,
                status=survey_status,
                satisfaction_score=satisfaction,
                nps_score=nps,
                completed_at=completed_at,
            )

            db.add(survey)
            db.flush()

        # October: satisfaction 5 and 3 -> average 4.
        # NPS: one promoter (10), one detractor (4) -> 0.
        create_survey(
            business, client, service, staff,
            datetime(2026, 10, 5, tzinfo=timezone.utc),
            5, 10,
        )

        create_survey(
            business, client, service, staff,
            datetime(2026, 10, 10, tzinfo=timezone.utc),
            3, 4,
        )

        # September: one promoter -> NPS +100.
        create_survey(
            business, client, service, staff,
            datetime(2026, 9, 15, tzinfo=timezone.utc),
            4, 9,
        )

        # August: invalid scores must be ignored.
        create_survey(
            business, client, service, staff,
            datetime(2026, 8, 15, tzinfo=timezone.utc),
            8, 15,
        )

        # July: pending surveys must be excluded.
        create_survey(
            business, client, service, staff,
            datetime(2026, 7, 15, tzinfo=timezone.utc),
            1, 0,
            survey_status="pending",
        )

        # June: satisfaction is valid, NPS is missing.
        create_survey(
            business, client, service, staff,
            datetime(2026, 6, 15, tzinfo=timezone.utc),
            2, None,
        )

        # May: NPS is valid, satisfaction is missing.
        create_survey(
            business, client, service, staff,
            datetime(2026, 5, 15, tzinfo=timezone.utc),
            None, 7,
        )

        # Future survey in current month must be excluded.
        create_survey(
            business, client, service, staff,
            datetime(2026, 10, 25, tzinfo=timezone.utc),
            1, 0,
        )

        # Older than the 12-month reporting window.
        create_survey(
            business, client, service, staff,
            datetime(2025, 10, 15, tzinfo=timezone.utc),
            1, 0,
        )

        # Different business must not affect the results.
        create_survey(
            other_business,
            other_client,
            other_service,
            other_staff,
            datetime(2026, 10, 6, tzinfo=timezone.utc),
            1,
            0,
        )

        result = get_experience_trends(
            business.id,
            db,
            as_of=AS_OF,
        )

        assert result["period_months"] == 12
        assert result["timezone"] == "UTC"
        assert len(result["trends"]) == 12

        assert result["trends"][0]["month"] == "2025-11"
        assert result["trends"][-1]["month"] == "2026-10"

        months = {
            item["month"]: item
            for item in result["trends"]
        }

        october = months["2026-10"]

        assert october["average_satisfaction"] == 4.0
        assert october["satisfaction_responses"] == 2
        assert october["nps_score"] == 0.0
        assert october["nps_responses"] == 2

        print("PASS: Satisfaction and NPS calculations")

        september = months["2026-09"]

        assert september["average_satisfaction"] == 4.0
        assert september["nps_score"] == 100.0

        print("PASS: Monthly grouping")

        august = months["2026-08"]

        assert august["average_satisfaction"] is None
        assert august["satisfaction_responses"] == 0
        assert august["nps_score"] is None
        assert august["nps_responses"] == 0

        print("PASS: Invalid scores excluded")

        july = months["2026-07"]

        assert july["average_satisfaction"] is None
        assert july["nps_score"] is None

        print("PASS: Pending surveys excluded")

        june = months["2026-06"]

        assert june["average_satisfaction"] == 2.0
        assert june["satisfaction_responses"] == 1
        assert june["nps_score"] is None
        assert june["nps_responses"] == 0

        may = months["2026-05"]

        assert may["average_satisfaction"] is None
        assert may["satisfaction_responses"] == 0
        assert may["nps_score"] == 0.0
        assert may["nps_responses"] == 1

        print("PASS: Independent metric response counts")

        april = months["2026-04"]

        assert april["average_satisfaction"] is None
        assert april["nps_score"] is None

        print("PASS: Empty months use null values")

        other_result = get_experience_trends(
            other_business.id,
            db,
            as_of=AS_OF,
        )

        other_october = other_result["trends"][-1]

        assert other_october["average_satisfaction"] == 1.0
        assert other_october["nps_score"] == -100.0

        print("PASS: Business isolation")
        print("PASS: Future and out-of-range surveys excluded")
        print("PASS: Twelve-month reporting window")

        print()
        print("ALL EXPERIENCE TRENDS TESTS PASSED")

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()
        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()

def check_experience_trends():
    run_tests()

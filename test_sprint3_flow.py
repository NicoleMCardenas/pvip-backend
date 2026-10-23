
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.business import Business
from app.models.client import Client
from app.models.service import Service
from app.models.staff import Staff
from app.models.visit import Visit
from app.schemas.retention import RetentionCaseCreate
from app.schemas.survey import SurveyCreate, SurveyResponseUpdate
from app.surveys.service import create_survey, update_survey_response
from app.retention.service import create_retention_case
from app.revenue_recovery.service import attribute_recovered_revenue


def test_sprint3_flow():
    connection = engine.connect()
    transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="rollback_only",
    )

    try:
        now = datetime.now(timezone.utc)

        business = Business(
            name=f"KAIRO Sprint 3 Test {uuid4().hex[:8]}",
            industry="Software Testing",
            email=f"sprint3-{uuid4().hex}@example.com",
        )
        db.add(business)
        db.flush()

        client = Client(
            business_id=business.id,
            name="Sprint 3 Test Customer",
            status="active",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )
        db.add(client)
        db.flush()

        service = Service(
            business_id=business.id,
            name="Sprint 3 Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="Sprint 3 Test Staff",
            role="staff",
            status="active",
        )

        db.add_all([service, staff])
        db.flush()

        # 1. Create an initial customer visit.
        initial_visit = Visit(
            business_id=business.id,
            client_id=client.id,
            service_id=service.id,
            staff_id=staff.id,
            visit_date=now - timedelta(days=10),
            amount=Decimal("100"),
        )
        db.add(initial_visit)
        db.flush()

        # 2. Create and complete a negative survey.
        survey = create_survey(
            SurveyCreate(
                visit_id=initial_visit.id,
                client_id=client.id,
            ),
            business.id,
            db,
        )

        completed_survey = update_survey_response(
            survey,
            SurveyResponseUpdate(
                satisfaction_score=2,
                nps_score=4,
                rebook_intent="no",
                comment="Unsatisfied with the experience.",
            ),
            db,
        )

        assert completed_survey.status == "completed"
        assert completed_survey.satisfaction_score == 2
        assert completed_survey.nps_score == 4

        db.refresh(client)
        assert client.status == "at_risk"

        print("PASS: Negative feedback identifies an at-risk customer")

        # 3. Create a retention case for that customer.
        retention_case = create_retention_case(
            RetentionCaseCreate(
                client_id=client.id,
                reason="Negative feedback requires follow-up.",
                priority="high",
            ),
            business.id,
            db,
        )

        assert retention_case.client_id == client.id
        assert retention_case.status == "pending"
        assert retention_case.priority == "high"

        print("PASS: Retention case created for at-risk customer")

        # 4. Record a later visit after opening the case.
        db.refresh(retention_case)

        follow_up_visit = Visit(
            business_id=business.id,
            client_id=client.id,
            service_id=service.id,
            staff_id=staff.id,
            visit_date=retention_case.created_at + timedelta(days=1),
            amount=Decimal("250"),
        )
        db.add(follow_up_visit)
        db.flush()

        # 5. Attribute the visit to recovered revenue.
        recovery = attribute_recovered_revenue(
            retention_case.id,
            follow_up_visit.id,
            business.id,
            db,
        )

        assert recovery.case_id == retention_case.id
        assert recovery.visit_id == follow_up_visit.id

        print("PASS: Recovered revenue attributed to a real visit")

        # 6. Ensure the same visit cannot be attributed twice.
        try:
            attribute_recovered_revenue(
                retention_case.id,
                follow_up_visit.id,
                business.id,
                db,
            )
        except HTTPException as error:
            assert error.status_code == 409
        else:
            raise AssertionError(
                "Duplicate revenue attribution was incorrectly allowed."
            )

        print("PASS: Duplicate revenue attribution rejected")
        print()
        print("ALL SPRINT 3 FLOW TESTS PASSED")

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    test_sprint3_flow()


from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.business import Business
from app.models.client import Client
from app.models.service import Service
from app.models.staff import Staff
from app.models.survey import Survey
from app.models.visit import Visit
from app.schemas.visit import VisitCreate
from app.visits.service import create_visit, delete_visit


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

        client = Client(
            business_id=business.id,
            name="KAIRO Survey Flow Test Customer",
            status="new",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )

        service = Service(
            business_id=business.id,
            name="KAIRO Survey Flow Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="KAIRO Survey Flow Test Staff",
            role="staff",
            status="active",
        )

        db.add_all([client, service, staff])
        db.flush()

        visit_data = VisitCreate(
            client_id=client.id,
            service_id=service.id,
            staff_id=staff.id,
            visit_date=datetime.now(timezone.utc),
            amount=Decimal("100"),
        )

        # TEST 1: Automatic survey creation
        visit = create_visit(
            visit_data,
            business.id,
            db,
        )

        survey = (
            db.query(Survey)
            .filter(Survey.visit_id == visit.id)
            .one()
        )

        assert survey.status == "pending"
        assert survey.public_token is not None
        assert len(survey.public_token) >= 32

        assert survey.business_id == business.id
        assert survey.client_id == client.id
        assert survey.visit_id == visit.id

        assert (
            db.query(Survey)
            .filter(Survey.visit_id == visit.id)
            .count()
        ) == 1

        print("PASS: Automatic survey creation")

        # TEST 2: Customer metrics
        db.refresh(client)

        assert client.total_visits == 1
        assert client.lifetime_value == Decimal("100")
        assert client.status == "active"

        print("PASS: Customer metrics preserved")

        # TEST 3: Delete pending survey with visit
        first_visit_id = visit.id
        first_survey_id = survey.id

        delete_visit(visit, db)

        assert (
            db.query(Visit)
            .filter(Visit.id == first_visit_id)
            .first()
        ) is None

        assert (
            db.query(Survey)
            .filter(Survey.id == first_survey_id)
            .first()
        ) is None

        print("PASS: Pending survey deleted with visit")

        # TEST 4: Protect completed survey
        second_visit = create_visit(
            visit_data,
            business.id,
            db,
        )

        completed_survey = (
            db.query(Survey)
            .filter(Survey.visit_id == second_visit.id)
            .one()
        )

        completed_survey.status = "completed"
        completed_survey.satisfaction_score = 5
        completed_survey.nps_score = 10
        completed_survey.rebook_intent = "yes"

        db.commit()

        try:
            delete_visit(second_visit, db)

        except HTTPException as error:
            assert error.status_code == 409

            assert (
                db.query(Visit)
                .filter(Visit.id == second_visit.id)
                .first()
            ) is not None

            assert (
                db.query(Survey)
                .filter(Survey.id == completed_survey.id)
                .first()
            ) is not None

            print("PASS: Completed survey protected")

        else:
            raise AssertionError(
                "A visit with a completed survey was deleted."
            )

        print()
        print("ALL SURVEY VISIT FLOW TESTS PASSED")

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()

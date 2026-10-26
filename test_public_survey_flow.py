
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
from app.schemas.survey import PublicSurveySubmission
from app.schemas.visit import VisitCreate
from app.surveys.service import (
    get_public_survey,
    submit_public_survey_response,
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

        assert business is not None, (
            "A business is required to run this test."
        )

        client = Client(
            business_id=business.id,
            name="KAIRO Public Survey Test Customer",
            status="new",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )

        service = Service(
            business_id=business.id,
            name="KAIRO Public Survey Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="KAIRO Public Survey Test Staff",
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

        token = survey.public_token

        assert token is not None

        # TEST 1: Public survey lookup
        public_survey = get_public_survey(token, db)

        assert public_survey.id == survey.id
        assert public_survey.status == "pending"

        print("PASS: Public survey lookup")

        # TEST 2: Public survey submission
        response_data = PublicSurveySubmission(
            satisfaction_score=2,
            nps_score=4,
            rebook_intent="no",
            comment="Test feedback",
        )

        completed_survey = submit_public_survey_response(
            token,
            response_data,
            db,
        )

        assert completed_survey.status == "completed"
        assert completed_survey.satisfaction_score == 2
        assert completed_survey.nps_score == 4
        assert completed_survey.rebook_intent == "no"
        assert completed_survey.comment == "Test feedback"
        assert completed_survey.completed_at is not None

        print("PASS: Public survey submission")

        # TEST 3: Negative feedback updates customer risk
        db.refresh(client)

        assert client.status == "at_risk"

        print("PASS: Negative feedback updates customer risk")

        # TEST 4: Duplicate submission protection
        try:
            submit_public_survey_response(
                token,
                response_data,
                db,
            )

        except HTTPException as error:
            assert error.status_code == 409

            print("PASS: Duplicate submission blocked")

        else:
            raise AssertionError(
                "Completed survey accepted a second response."
            )

        # TEST 5: Invalid public token
        try:
            get_public_survey(
                "invalid-public-survey-token",
                db,
            )

        except HTTPException as error:
            assert error.status_code == 404

            print("PASS: Invalid token rejected")

        else:
            raise AssertionError(
                "Invalid token was accepted."
            )

        print()
        print("ALL PUBLIC SURVEY FLOW TESTS PASSED")

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()


from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import engine, get_db
from app.main import app
from app.models.business import Business
from app.models.client import Client
from app.models.service import Service
from app.models.staff import Staff
from app.models.survey import Survey
from app.schemas.visit import VisitCreate
from app.visits.service import create_visit


def run_tests():
    connection = engine.connect()
    transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    previous_override = app.dependency_overrides.get(get_db)

    def override_get_db():
        yield db

    try:
        business = db.query(Business).first()

        assert business is not None, (
            "A business is required to run this test."
        )

        client = Client(
            business_id=business.id,
            name="KAIRO Public HTTP Test Customer",
            status="new",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )

        service = Service(
            business_id=business.id,
            name="KAIRO Public HTTP Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="KAIRO Public HTTP Test Staff",
            role="staff",
            status="active",
        )

        db.add_all([client, service, staff])
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

        token = survey.public_token

        assert token is not None

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as http:
            # TEST 1: Open a valid public survey
            response = http.get(
                f"/surveys/public/{token}"
            )

            assert response.status_code == 200, (
                response.text
            )

            survey_data = response.json()

            assert survey_data["status"] == "pending"

            print("PASS: Public HTTP survey lookup")

            # TEST 2: Submit a completed response
            response = http.post(
                f"/surveys/public/{token}/responses",
                json={
                    "satisfaction_score": 2,
                    "nps_score": 4,
                    "rebook_intent": "no",
                    "comment": "HTTP integration test",
                },
            )

            assert response.status_code == 200, (
                response.text
            )

            result = response.json()

            assert result["status"] == "completed"
            assert result["satisfaction_score"] == 2
            assert result["nps_score"] == 4
            assert result["rebook_intent"] == "no"

            print("PASS: Public HTTP submission")

            # TEST 3: Verify persisted response and risk
            db.expire_all()

            saved_survey = (
                db.query(Survey)
                .filter(Survey.id == survey.id)
                .one()
            )

            saved_client = (
                db.query(Client)
                .filter(Client.id == client.id)
                .one()
            )

            assert saved_survey.status == "completed"
            assert saved_survey.completed_at is not None
            assert saved_client.status == "at_risk"

            print("PASS: HTTP response and risk persisted")

            # TEST 4: Reject a duplicate submission
            response = http.post(
                f"/surveys/public/{token}/responses",
                json={
                    "satisfaction_score": 5,
                    "nps_score": 10,
                    "rebook_intent": "yes",
                },
            )

            assert response.status_code == 409, (
                response.text
            )

            print("PASS: Duplicate HTTP submission blocked")

            # TEST 5: Do not expose internal identifiers
            forbidden_fields = {
                "id",
                "business_id",
                "client_id",
                "visit_id",
                "public_token",
            }

            assert forbidden_fields.isdisjoint(
                survey_data.keys()
            )

            assert forbidden_fields.isdisjoint(
                result.keys()
            )

            print("PASS: Internal identifiers not exposed")

        print()
        print("ALL PUBLIC SURVEY HTTP TESTS PASSED")

    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override

        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()


from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.business import Business
from app.models.client import Client
from app.models.service import Service
from app.models.staff import Staff
from app.schemas.visit import VisitCreate, VisitUpdate
from app.visits.service import (
    create_visit,
    update_visit,
    delete_visit,
)


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

        client = Client(
            business_id=business.id,
            name="KAIRO Sprint 2 Test Customer",
            status="new",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )

        service = Service(
            business_id=business.id,
            name="KAIRO Sprint 2 Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="KAIRO Sprint 2 Test Staff",
            role="staff",
            status="active",
        )

        db.add_all([client, service, staff])
        db.flush()

        visit_date = (
            datetime.now(timezone.utc)
            - timedelta(days=2)
        )

        # TEST 1: Create visit
        visit = create_visit(
            VisitCreate(
                client_id=client.id,
                service_id=service.id,
                staff_id=staff.id,
                visit_date=visit_date,
                amount=Decimal("100"),
            ),
            business.id,
            db,
        )

        db.refresh(client)

        assert client.total_visits == 1
        assert client.lifetime_value == Decimal("100")
        assert client.last_visit == visit_date
        assert client.status == "active"

        print("PASS: Visit creation and customer metrics")

        # TEST 2: Update visit
        visit = update_visit(
            visit,
            VisitUpdate(amount=Decimal("150")),
            db,
        )

        db.refresh(client)

        assert client.total_visits == 1
        assert client.lifetime_value == Decimal("150")

        print("PASS: Visit update and customer metrics")

        # TEST 3: Reject inactive staff
        staff.status = "inactive"
        db.commit()

        try:
            create_visit(
                VisitCreate(
                    client_id=client.id,
                    service_id=service.id,
                    staff_id=staff.id,
                    visit_date=visit_date,
                    amount=Decimal("50"),
                ),
                business.id,
                db,
            )
        except HTTPException as error:
            assert error.status_code == 422
            print("PASS: Inactive staff rejected")
        else:
            raise AssertionError(
                "Inactive staff was incorrectly accepted."
            )

        # TEST 4: Reject archived customer
        staff.status = "active"
        client.status = "archived"
        db.commit()

        try:
            create_visit(
                VisitCreate(
                    client_id=client.id,
                    service_id=service.id,
                    staff_id=staff.id,
                    visit_date=visit_date,
                    amount=Decimal("50"),
                ),
                business.id,
                db,
            )
        except HTTPException as error:
            assert error.status_code == 422
            print("PASS: Archived customer rejected")
        else:
            raise AssertionError(
                "Archived customer was incorrectly accepted."
            )

        # TEST 5: Delete visit and recalculate metrics
        delete_visit(visit, db)
        db.refresh(client)

        assert client.total_visits == 0
        assert client.lifetime_value == Decimal("0")
        assert client.last_visit is None
        assert client.status == "archived"

        print("PASS: Visit deletion and customer metrics")

        print()
        print("ALL VISIT TESTS PASSED")

    finally:
        db.close()

        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()


def check_visits_sprint2():
    run_tests()
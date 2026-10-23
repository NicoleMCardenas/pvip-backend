from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.analytics.segmentation import get_customer_segments
from app.db.session import engine
from app.models.business import Business
from app.models.client import Client
from app.models.service import Service
from app.models.staff import Staff
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
            name=f"KAIRO Segments Test {uuid4().hex[:8]}",
            industry="Software Testing",
            email=f"segments-{uuid4().hex}@example.com",
        )

        other_business = Business(
            name=f"KAIRO Isolation Test {uuid4().hex[:8]}",
            industry="Software Testing",
            email=f"isolation-{uuid4().hex}@example.com",
        )

        db.add_all([business, other_business])
        db.flush()

        service = Service(
            business_id=business.id,
            name="Segmentation Test Service",
            duration_minutes=30,
            price=100,
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="Segmentation Test Staff",
            role="staff",
            status="active",
        )

        db.add_all([service, staff])
        db.flush()

        def create_client(name, status="active", business_id=None):
            client = Client(
                business_id=business_id or business.id,
                name=name,
                status=status,
                total_visits=0,
                lifetime_value=0,
            )
            db.add(client)
            db.flush()
            return client

        def create_visit(client, days_ago):
            visit = Visit(
                business_id=business.id,
                client_id=client.id,
                service_id=service.id,
                staff_id=staff.id,
                visit_date=AS_OF - timedelta(days=days_ago),
                amount=100,
            )
            db.add(visit)
            db.flush()

        # No visits
        create_client("New Customer")

        # One recent visit
        one_time = create_client("One-time Customer")
        create_visit(one_time, 10)

        # Multiple recent visits
        returning = create_client("Returning Customer")
        create_visit(returning, 40)
        create_visit(returning, 5)

        # Last visit more than 90 days ago
        inactive = create_client("Inactive Customer")
        create_visit(inactive, 120)

        # Exactly 90 days since last visit
        boundary = create_client("Boundary Customer")
        create_visit(boundary, 90)

        # Future visit must not count
        future = create_client("Future Visit Customer")
        create_visit(future, -5)

        # Archived customer must be excluded
        archived = create_client(
            "Archived Customer",
            status="archived",
        )
        create_visit(archived, 2)

        # Different business must be excluded
        create_client(
            "Other Business Customer",
            business_id=other_business.id,
        )

        result = get_customer_segments(
            business.id,
            db,
            as_of=AS_OF,
        )

        assert result["total_clients"] == 6
        assert result["inactivity_threshold_days"] == 90

        assert result["segments"] == {
            "new": 2,
            "one_time": 1,
            "returning": 1,
            "inactive": 2,
        }, result["segments"]

        print("PASS: Customer segments classification")
        print("PASS: 90-day inactivity boundary")
        print("PASS: Future visits excluded")
        print("PASS: Archived customers excluded")
        print("PASS: Business isolation")

        other_result = get_customer_segments(
            other_business.id,
            db,
            as_of=AS_OF,
        )

        assert other_result["total_clients"] == 1
        assert other_result["segments"]["new"] == 1

        print("PASS: Independent business segmentation")

        print()
        print("ALL CUSTOMER SEGMENTATION TESTS PASSED")

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()
        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()
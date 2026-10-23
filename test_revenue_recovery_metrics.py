from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.business import Business
from app.models.client import Client
from app.models.retention_case import RetentionCase
from app.models.revenue_recovery import RevenueRecovery
from app.models.service import Service
from app.models.staff import Staff
from app.models.visit import Visit
from app.revenue_recovery.metrics import (
    get_revenue_recovery_metrics,
)


def run_tests():
    connection = engine.connect()
    transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="rollback_only",
    )

    try:
        now = datetime.now(timezone.utc)
        case_date = now - timedelta(days=20)

        business = Business(
            name=f"KAIRO Metrics Test {uuid4().hex[:8]}",
            industry="Software Testing",
            email=f"metrics-{uuid4().hex}@example.com",
        )

        other_business = Business(
            name=f"KAIRO Metrics Isolation {uuid4().hex[:8]}",
            industry="Software Testing",
            email=f"metrics-other-{uuid4().hex}@example.com",
        )

        db.add_all([business, other_business])
        db.flush()

        def make_client(name, business_id=None):
            client = Client(
                business_id=business_id or business.id,
                name=name,
                status="active",
                lifetime_value=Decimal("0"),
                total_visits=0,
            )
            db.add(client)
            db.flush()
            return client

        client_a = make_client("Customer A")
        client_b = make_client("Customer B")
        client_c = make_client("Customer Without History")

        foreign_client = make_client(
            "Other Business Customer",
            other_business.id,
        )

        service = Service(
            business_id=business.id,
            name="Metrics Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="Metrics Test Staff",
            role="staff",
            status="active",
        )

        db.add_all([service, staff])
        db.flush()

        def make_case(
            client,
            status="pending",
            business_id=None,
        ):
            retention_case = RetentionCase(
                business_id=business_id or business.id,
                client_id=client.id,
                reason="Customer retention follow-up",
                priority="high",
                status=status,
                created_at=case_date,
                resolved_at=(
                    now - timedelta(days=1)
                    if status == "resolved"
                    else None
                ),
            )

            db.add(retention_case)
            db.flush()

            return retention_case

        case_a = make_case(client_a)

        make_case(
            client_b,
            status="in_progress",
        )

        make_case(client_c)

        make_case(
            foreign_client,
            business_id=other_business.id,
        )

        resolved_client = make_client(
            "Resolved Customer"
        )

        make_case(
            resolved_client,
            status="resolved",
        )

        def make_visit(
            client,
            amount,
            days_ago,
            business_id=None,
        ):
            visit = Visit(
                business_id=business_id or business.id,
                client_id=client.id,
                service_id=service.id,
                staff_id=staff.id,
                visit_date=now - timedelta(days=days_ago),
                amount=Decimal(amount),
            )

            db.add(visit)
            db.flush()

            return visit

        # Customer A: average historical spend = 150
        make_visit(client_a, "100", 15)

        recovered_visit = make_visit(
            client_a,
            "200",
            5,
        )

        # Customer B: average historical spend = 300
        make_visit(client_b, "300", 10)

        # Different business must not affect totals
        make_visit(
            foreign_client,
            "9000",
            10,
            business_id=other_business.id,
        )

        recovery = RevenueRecovery(
            case_id=case_a.id,
            visit_id=recovered_visit.id,
        )

        db.add(recovery)
        db.flush()

        # Evaluate after the recovery attribution exists.
        # Use one consistent cutoff for both businesses.
        as_of = (
            datetime.now(timezone.utc)
            + timedelta(seconds=1)
        )

        result = get_revenue_recovery_metrics(
            business.id,
            db,
            as_of=as_of,
        )

        # TEST 1: Open opportunities
        assert result["open_opportunities"] == 3

        print("PASS: Open recovery opportunities")

        # TEST 2: Resolved cases
        assert result["resolved_cases"] == 1

        print("PASS: Resolved retention cases")

        # TEST 3: Estimated revenue at risk
        assert (
            result["estimated_revenue_at_risk"]
            == Decimal("450.00")
        ), result

        print("PASS: Estimated revenue at risk")

        # TEST 4: Customers without history
        assert result["estimated_cases"] == 2
        assert result["insufficient_data_cases"] == 1

        opportunity_without_history = next(
            opportunity
            for opportunity in result["opportunities"]
            if opportunity["client_id"] == client_c.id
        )

        assert (
            opportunity_without_history[
                "estimated_revenue_at_risk"
            ]
            is None
        )

        print("PASS: Insufficient historical data")

        # TEST 5: Recovered revenue
        assert (
            result["recovered_revenue"]
            == Decimal("200.00")
        ), (
            "Expected recovered revenue 200.00, "
            f"got {result['recovered_revenue']}"
        )

        assert result["attributed_visits"] == 1

        print("PASS: Recovered revenue attribution")

        # TEST 6: Business isolation
        other_result = get_revenue_recovery_metrics(
            other_business.id,
            db,
            as_of=as_of,
        )

        assert other_result["open_opportunities"] == 1

        assert (
            other_result["estimated_revenue_at_risk"]
            == Decimal("9000.00")
        )

        assert (
            other_result["recovered_revenue"]
            == Decimal("0.00")
        )

        print("PASS: Business isolation")

        # TEST 7: No double counting
        assert len(result["opportunities"]) == 3
        assert result["attributed_visits"] == 1

        print("PASS: No duplicate revenue attribution")

        print()
        print(
            "ALL REVENUE RECOVERY METRICS TESTS PASSED"
        )

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()


def check_revenue_recovery_metrics():
    run_tests()

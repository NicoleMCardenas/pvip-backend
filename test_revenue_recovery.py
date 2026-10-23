from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.business import Business
from app.models.client import Client
from app.models.retention_case import RetentionCase
from app.models.revenue_recovery import RevenueRecovery
from app.models.service import Service
from app.models.staff import Staff
from app.models.visit import Visit
from app.revenue_recovery.service import (
    attribute_recovered_revenue,
    get_revenue_recoveries,
    remove_revenue_attribution,
)
from app.schemas.visit import VisitUpdate
from app.visits.service import delete_visit, update_visit


def expect_http_error(expected_status, callback):
    try:
        callback()
    except HTTPException as error:
        assert error.status_code == expected_status, (
            f"Expected {expected_status}, got "
            f"{error.status_code}: {error.detail}"
        )
    else:
        raise AssertionError(
            f"Expected HTTP {expected_status}, "
            "but operation succeeded."
        )


def run_scenario(name, test_function):
    """
    Run each scenario in an independent transaction.

    Service commits remain inside the external transaction.
    Everything is rolled back when the scenario finishes.
    """
    connection = engine.connect()
    transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="rollback_only",
    )

    try:
        now = datetime.now(timezone.utc)

        business = Business(
            name=f"KAIRO Recovery Test {uuid4().hex[:8]}",
            industry="Software Testing",
            email=f"recovery-{uuid4().hex}@example.com",
        )

        other_business = Business(
            name=f"KAIRO Isolation Test {uuid4().hex[:8]}",
            industry="Software Testing",
            email=f"isolation-{uuid4().hex}@example.com",
        )

        db.add_all([business, other_business])
        db.flush()

        client = Client(
            business_id=business.id,
            name="Recovery Test Customer",
            status="active",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )

        other_client = Client(
            business_id=business.id,
            name="Different Customer",
            status="active",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )

        foreign_client = Client(
            business_id=other_business.id,
            name="Other Business Customer",
            status="active",
            lifetime_value=Decimal("0"),
            total_visits=0,
        )

        db.add_all([client, other_client, foreign_client])
        db.flush()

        service = Service(
            business_id=business.id,
            name="Recovery Test Service",
            duration_minutes=30,
            price=Decimal("100"),
            status="active",
        )

        staff = Staff(
            business_id=business.id,
            name="Recovery Test Staff",
            role="staff",
            status="active",
        )

        db.add_all([service, staff])
        db.flush()

        retention_case = RetentionCase(
            business_id=business.id,
            client_id=client.id,
            reason="Customer at risk",
            priority="high",
            status="in_progress",
            created_at=now - timedelta(days=20),
        )

        db.add(retention_case)
        db.flush()

        def make_visit(
            customer=None,
            days_ago=5,
            amount="250",
            business_id=None,
        ):
            visit = Visit(
                business_id=business_id or business.id,
                client_id=(customer or client).id,
                service_id=service.id,
                staff_id=staff.id,
                visit_date=now - timedelta(days=days_ago),
                amount=Decimal(amount),
            )

            db.add(visit)
            db.flush()
            return visit

        context = {
            "db": db,
            "business": business,
            "other_business": other_business,
            "client": client,
            "other_client": other_client,
            "foreign_client": foreign_client,
            "retention_case": retention_case,
            "make_visit": make_visit,
            "now": now,
        }

        test_function(context)
        print(f"PASS: {name}")

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()


def test_valid_attribution(ctx):
    visit = ctx["make_visit"]()

    recovery = attribute_recovered_revenue(
        ctx["retention_case"].id,
        visit.id,
        ctx["business"].id,
        ctx["db"],
    )

    assert recovery.visit_id == visit.id
    assert recovery.case_id == ctx["retention_case"].id


def test_duplicate_attribution(ctx):
    visit = ctx["make_visit"]()

    attribute_recovered_revenue(
        ctx["retention_case"].id,
        visit.id,
        ctx["business"].id,
        ctx["db"],
    )

    expect_http_error(
        409,
        lambda: attribute_recovered_revenue(
            ctx["retention_case"].id,
            visit.id,
            ctx["business"].id,
            ctx["db"],
        ),
    )


def test_different_customer(ctx):
    visit = ctx["make_visit"](
        customer=ctx["other_client"],
    )

    expect_http_error(
        422,
        lambda: attribute_recovered_revenue(
            ctx["retention_case"].id,
            visit.id,
            ctx["business"].id,
            ctx["db"],
        ),
    )


def test_business_isolation(ctx):
    visit = ctx["make_visit"](
        customer=ctx["foreign_client"],
        business_id=ctx["other_business"].id,
    )

    expect_http_error(
        404,
        lambda: attribute_recovered_revenue(
            ctx["retention_case"].id,
            visit.id,
            ctx["business"].id,
            ctx["db"],
        ),
    )

    assert get_revenue_recoveries(
        ctx["other_business"].id,
        ctx["db"],
    ) == []


def test_historical_date(ctx):
    visit = ctx["make_visit"](days_ago=30)

    expect_http_error(
        422,
        lambda: attribute_recovered_revenue(
            ctx["retention_case"].id,
            visit.id,
            ctx["business"].id,
            ctx["db"],
        ),
    )


def test_zero_revenue(ctx):
    visit = ctx["make_visit"](amount="0")

    expect_http_error(
        422,
        lambda: attribute_recovered_revenue(
            ctx["retention_case"].id,
            visit.id,
            ctx["business"].id,
            ctx["db"],
        ),
    )


def test_amount_update(ctx):
    visit = ctx["make_visit"]()

    attribute_recovered_revenue(
        ctx["retention_case"].id,
        visit.id,
        ctx["business"].id,
        ctx["db"],
    )

    updated = update_visit(
        visit,
        VisitUpdate(amount=Decimal("350")),
        ctx["db"],
    )

    assert updated.amount == Decimal("350")

    recovered_amount = (
        ctx["db"]
        .query(func.sum(Visit.amount))
        .join(
            RevenueRecovery,
            RevenueRecovery.visit_id == Visit.id,
        )
        .filter(
            RevenueRecovery.case_id
            == ctx["retention_case"].id,
        )
        .scalar()
    )

    assert recovered_amount == Decimal("350")


def test_invalid_date_update(ctx):
    visit = ctx["make_visit"]()

    attribute_recovered_revenue(
        ctx["retention_case"].id,
        visit.id,
        ctx["business"].id,
        ctx["db"],
    )

    expect_http_error(
        422,
        lambda: update_visit(
            visit,
            VisitUpdate(
                visit_date=ctx["now"] - timedelta(days=40),
            ),
            ctx["db"],
        ),
    )


def test_zero_amount_update(ctx):
    visit = ctx["make_visit"]()

    attribute_recovered_revenue(
        ctx["retention_case"].id,
        visit.id,
        ctx["business"].id,
        ctx["db"],
    )

    expect_http_error(
        422,
        lambda: update_visit(
            visit,
            VisitUpdate(amount=Decimal("0")),
            ctx["db"],
        ),
    )


def test_remove_attribution(ctx):
    visit = ctx["make_visit"]()

    recovery = attribute_recovered_revenue(
        ctx["retention_case"].id,
        visit.id,
        ctx["business"].id,
        ctx["db"],
    )

    recovery_id = recovery.id

    remove_revenue_attribution(
        recovery_id,
        ctx["business"].id,
        ctx["db"],
    )

    assert ctx["db"].get(
        RevenueRecovery,
        recovery_id,
    ) is None


def test_delete_attributed_visit(ctx):
    visit = ctx["make_visit"]()

    recovery = attribute_recovered_revenue(
        ctx["retention_case"].id,
        visit.id,
        ctx["business"].id,
        ctx["db"],
    )

    recovery_id = recovery.id
    visit_id = visit.id

    delete_visit(visit, ctx["db"])

    assert ctx["db"].get(
        RevenueRecovery,
        recovery_id,
    ) is None

    assert ctx["db"].get(
        Visit,
        visit_id,
    ) is None


def run_tests():
    scenarios = [
        ("Valid revenue attribution", test_valid_attribution),
        ("Duplicate attribution rejected", test_duplicate_attribution),
        ("Different customer rejected", test_different_customer),
        ("Business isolation", test_business_isolation),
        ("Historical date validation", test_historical_date),
        ("Zero revenue rejected", test_zero_revenue),
        ("Recovered revenue reflects visit updates", test_amount_update),
        ("Invalid attributed visit date rejected", test_invalid_date_update),
        ("Attributed revenue cannot become zero", test_zero_amount_update),
        ("Revenue attribution removal", test_remove_attribution),
        ("Visit deletion removes attribution", test_delete_attributed_visit),
    ]

    try:
        for name, test_function in scenarios:
            run_scenario(name, test_function)

        print()
        print("ALL REVENUE RECOVERY TESTS PASSED")

    finally:
        print("Test transactions rolled back.")


if __name__ == "__main__":
    run_tests()


def check_revenue_recovery():
    run_tests()

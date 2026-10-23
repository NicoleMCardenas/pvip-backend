
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.business import Business
from app.models.staff import Staff
from app.schemas.staff import StaffCreate, StaffUpdate
from app.staff.service import (
    create_staff_member,
    get_staff_member_by_id,
    get_staff_members,
    update_staff_member,
    delete_staff_member,
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
        assert business is not None, "No business available."

        # TEST 1: Create staff
        staff = create_staff_member(
            StaffCreate(
                name="KAIRO Sprint 2 Test Staff",
                email="kairo.staff.test@example.com",
                role="staff",
            ),
            business.id,
            db,
        )

        assert staff.status == "active"
        assert staff.name == "KAIRO Sprint 2 Test Staff"

        print("PASS: Staff creation")

        # TEST 2: Retrieve staff
        retrieved = get_staff_member_by_id(
            staff.id,
            business.id,
            db,
        )

        assert retrieved is not None
        assert retrieved.id == staff.id

        print("PASS: Staff retrieval")

        # TEST 3: Update staff
        staff = update_staff_member(
            staff,
            StaffUpdate(name="KAIRO Updated Test Staff"),
            db,
        )

        assert staff.name == "KAIRO Updated Test Staff"

        print("PASS: Staff update")

        # TEST 4: Deactivate staff
        delete_staff_member(staff, db)

        db.refresh(staff)

        assert staff.status == "inactive"

        print("PASS: Staff deactivation")

        # TEST 5: Preserve inactive staff
        retrieved = get_staff_member_by_id(
            staff.id,
            business.id,
            db,
        )

        assert retrieved is not None
        assert retrieved.status == "inactive"
        assert retrieved.name == "KAIRO Updated Test Staff"

        print("PASS: Inactive staff preserved")

        # TEST 6: Reactivate staff
        staff = update_staff_member(
            staff,
            StaffUpdate(status="active"),
            db,
        )

        assert staff.status == "active"

        print("PASS: Staff reactivation")

        # TEST 7: Business isolation
        other_business_id = uuid4()

        inaccessible = get_staff_member_by_id(
            staff.id,
            other_business_id,
            db,
        )

        assert inaccessible is None

        print("PASS: Staff business isolation")

        # TEST 8: Staff appears in listing
        members = get_staff_members(business.id, db)

        assert any(member.id == staff.id for member in members)

        print("PASS: Staff listing")

        print()
        print("ALL STAFF TESTS PASSED")

    finally:
        db.close()

        if outer_transaction.is_active:
            outer_transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()


def check_staff_sprint2():
    run_tests()

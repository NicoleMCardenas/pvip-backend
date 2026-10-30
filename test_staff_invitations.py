
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.staff_invitations import (
    accept_staff_invitation,
    create_staff_invitation,
    hash_staff_invitation_token,
)
from app.db.session import engine
from app.models.business import Business
from app.models.staff import Staff
from app.models.staff_invitation import StaffInvitation
from app.models.user import User


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
            "A business is required to run these tests."
        )

        suffix = uuid4().hex

        staff = Staff(
            business_id=business.id,
            name="KAIRO Invitation Test Staff",
            role="staff",
            status="active",
        )

        inactive_staff = Staff(
            business_id=business.id,
            name="KAIRO Inactive Invitation Test",
            role="staff",
            status="inactive",
        )

        db.add_all([staff, inactive_staff])
        db.flush()

        email = f"invitation-{suffix}@example.com"

        # TEST 1: Create a valid invitation.
        token = create_staff_invitation(
            db,
            business.id,
            staff.id,
            email,
        )

        invitation = (
            db.query(StaffInvitation)
            .filter(
                StaffInvitation.token_hash
                == hash_staff_invitation_token(token)
            )
            .one()
        )

        assert invitation.business_id == business.id
        assert invitation.staff_id == staff.id
        assert invitation.email == email
        assert invitation.used_at is None
        assert invitation.expires_at > datetime.now(timezone.utc)

        print("PASS: Valid invitation created")

        # TEST 2: Reject an inactive professional.
        try:
            create_staff_invitation(
                db,
                business.id,
                inactive_staff.id,
                f"inactive-{suffix}@example.com",
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError(
                "Inactive professional was not rejected."
            )

        print("PASS: Inactive professional rejected")

        # TEST 3: Accept a valid invitation.
        accepted = accept_staff_invitation(
            db,
            token,
            "SecureTestPassword123!",
        )

        assert accepted is True

        user = (
            db.query(User)
            .filter(User.staff_id == staff.id)
            .one()
        )

        assert user.business_id == business.id
        assert user.email == email
        assert user.role == "staff"
        assert user.is_active is True
        assert user.password_hash != "SecureTestPassword123!"

        db.refresh(invitation)
        assert invitation.used_at is not None

        print("PASS: Invitation activates staff account")

        # TEST 4: Reject reuse of a consumed token.
        assert accept_staff_invitation(
            db,
            token,
            "AnotherSecurePassword123!",
        ) is False

        print("PASS: Used invitation rejected")

        # TEST 5: Reject duplicate account invitations.
        try:
            create_staff_invitation(
                db,
                business.id,
                staff.id,
                email,
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError(
                "Duplicate account was not rejected."
            )

        print("PASS: Duplicate account rejected")

        # TEST 6: Reject expired invitation.
        expired_staff = Staff(
            business_id=business.id,
            name="KAIRO Expired Invitation Test",
            role="staff",
            status="active",
        )

        db.add(expired_staff)
        db.flush()

        expired_token = create_staff_invitation(
            db,
            business.id,
            expired_staff.id,
            f"expired-{suffix}@example.com",
        )

        expired_invitation = (
            db.query(StaffInvitation)
            .filter(
                StaffInvitation.token_hash
                == hash_staff_invitation_token(expired_token)
            )
            .one()
        )

        expired_invitation.expires_at = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        )

        db.flush()

        assert accept_staff_invitation(
            db,
            expired_token,
            "SecureTestPassword123!",
        ) is False

        print("PASS: Expired invitation rejected")

        print()
        print("ALL STAFF INVITATION TESTS PASSED")

    finally:
        db.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    run_tests()

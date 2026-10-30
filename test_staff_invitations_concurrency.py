
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.auth.staff_invitations import (
    create_staff_invitation,
    hash_staff_invitation_token,
)
from app.core.config import settings
from app.models.business import Business
from app.models.staff import Staff
from app.models.staff_invitation import StaffInvitation


def get_test_engine():
    url = make_url(settings.database_url)

    if url.database != "kairo_test":
        raise RuntimeError(
            "Safety check failed: this test requires kairo_test."
        )

    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )


def run_tests():
    engine = get_test_engine()

    business_id = None
    staff_id = None
    suffix = uuid4().hex

    try:
        # Create isolated test records.
        with Session(engine) as db:
            business = Business(
                name="KAIRO Concurrency Test",
                industry="Testing",
                email=f"concurrency-business-{suffix}@example.com",
            )

            db.add(business)
            db.flush()

            staff = Staff(
                business_id=business.id,
                name="KAIRO Concurrency Staff",
                role="staff",
                status="active",
            )

            db.add(staff)
            db.flush()

            business_id = business.id
            staff_id = staff.id

            db.commit()

        print("PASS: Isolated test records created")

        barrier = threading.Barrier(2)

        def send_invitation(number):
            with Session(engine) as db:
                barrier.wait(timeout=10)

                return create_staff_invitation(
                    db=db,
                    business_id=business_id,
                    staff_id=staff_id,
                    email=(
                        f"concurrency-{number}-{suffix}@example.com"
                    ),
                )

        # Simulate two concurrent requests.
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(send_invitation, number)
                for number in (1, 2)
            ]

            tokens = [
                future.result(timeout=20)
                for future in futures
            ]

        assert len(tokens) == 2
        assert tokens[0] != tokens[1]

        print("PASS: Concurrent requests completed")

        # Verify that only one invitation remains available.
        with Session(engine) as db:
            invitations = (
                db.query(StaffInvitation)
                .filter(
                    StaffInvitation.staff_id == staff_id
                )
                .all()
            )

            assert len(invitations) == 2

            available = [
                invitation
                for invitation in invitations
                if invitation.used_at is None
            ]

            invalidated = [
                invitation
                for invitation in invitations
                if invitation.used_at is not None
            ]

            assert len(available) == 1
            assert len(invalidated) == 1

            token_hashes = {
                hash_staff_invitation_token(token)
                for token in tokens
            }

            assert {
                invitation.token_hash
                for invitation in invitations
            } == token_hashes

        print("PASS: Only one invitation remains available")
        print()
        print("ALL STAFF INVITATION CONCURRENCY TESTS PASSED")

    finally:
        # Remove only the records created by this test.
        if business_id is not None:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "DELETE FROM staff_invitations "
                        "WHERE business_id = :business_id"
                    ),
                    {"business_id": business_id},
                )

                connection.execute(
                    text(
                        "DELETE FROM staff "
                        "WHERE business_id = :business_id"
                    ),
                    {"business_id": business_id},
                )

                connection.execute(
                    text(
                        "DELETE FROM businesses "
                        "WHERE id = :business_id"
                    ),
                    {"business_id": business_id},
                )

            print("Test records cleaned up.")

        engine.dispose()


if __name__ == "__main__":
    run_tests()

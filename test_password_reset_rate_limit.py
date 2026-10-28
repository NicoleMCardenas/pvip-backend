import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from app.db.session import SessionLocal, engine
from app.models.password_reset_attempt import PasswordResetAttempt
from app.auth.password_reset_rate_limit import (
    MAX_REQUESTS,
    WINDOW_MINUTES,
    allow_password_reset_request,
    hash_client_ip,
)


def main():
    connection = engine.connect()
    transaction = connection.begin()

    db = SessionLocal(bind=connection, join_transaction_mode="create_savepoint")

    try:
        # Unique test IP to avoid interference with other tests.
        test_ip = f"test-{uuid.uuid4()}"

        ip_hash = hash_client_ip(test_ip)

        assert len(ip_hash) == 64
        assert test_ip != ip_hash
        print("PASS: Client IP is hashed")

        # The first five attempts must be allowed.
        for attempt_number in range(1, MAX_REQUESTS + 1):
            allowed = allow_password_reset_request(
                db=db,
                ip_address=test_ip,
            )

            assert allowed is True, (
                f"Attempt {attempt_number} was unexpectedly rejected"
            )

            db.commit()

        print("PASS: First five requests allowed")

        # The next attempt must be rejected.
        allowed = allow_password_reset_request(
            db=db,
            ip_address=test_ip,
        )

        assert allowed is False
        print("PASS: Sixth request rejected")

        # Verify that exactly five attempts were stored.
        stored_attempts = (
            db.query(PasswordResetAttempt)
            .filter(PasswordResetAttempt.ip_hash == ip_hash)
            .count()
        )

        assert stored_attempts == MAX_REQUESTS
        print("PASS: Rejected request was not stored")

        # Move existing attempts outside the active window.
        expired_time = (
            datetime.now(timezone.utc)
            - timedelta(minutes=WINDOW_MINUTES + 1)
        )

        (
            db.query(PasswordResetAttempt)
            .filter(PasswordResetAttempt.ip_hash == ip_hash)
            .update(
                {"created_at": expired_time},
                synchronize_session=False,
            )
        )

        db.commit()

        # Requests must be allowed again after the window.
        allowed = allow_password_reset_request(
            db=db,
            ip_address=test_ip,
        )

        assert allowed is True
        db.commit()

        print("PASS: Requests allowed after window expires")

        print()
        print("ALL PASSWORD RESET RATE LIMIT TESTS PASSED")

    finally:
        db.close()
        transaction.rollback()
        connection.close()
        print("Test transaction rolled back.")


if __name__ == "__main__":
    main()
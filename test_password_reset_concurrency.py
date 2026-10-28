
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.password_reset_attempt import PasswordResetAttempt
from app.auth.password_reset_rate_limit import (
    MAX_REQUESTS,
    allow_password_reset_request,
    hash_client_ip,
)


def submit_request(ip_address: str, start_event=None) -> bool:
    db = SessionLocal()

    try:
        if start_event is not None:
            if not start_event.wait(timeout=10):
                raise RuntimeError("Timed out waiting for concurrent requests.")

        allowed = allow_password_reset_request(
            db=db,
            ip_address=ip_address,
        )

        if allowed:
            db.commit()

        return allowed

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def main():
    test_ip = f"concurrency-test-{uuid.uuid4()}"
    ip_hash = hash_client_ip(test_ip)

    try:
        # Create four attempts before testing concurrency.
        for _ in range(MAX_REQUESTS - 1):
            assert submit_request(test_ip) is True

        print("PASS: Four initial requests registered")

        # Release both workers at approximately the same time.
        start_event = threading.Event()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(submit_request, test_ip, start_event)
                for _ in range(2)
            ]

            start_event.set()

            results = [future.result(timeout=20) for future in futures]

        assert sorted(results) == [False, True], (
            f"Expected one accepted and one rejected request, got {results}"
        )

        print("PASS: Only one concurrent request accepted")

        db = SessionLocal()

        try:
            window_start = datetime.now(timezone.utc) - timedelta(
                minutes=15
            )

            count = (
                db.query(PasswordResetAttempt)
                .filter(
                    PasswordResetAttempt.ip_hash == ip_hash,
                    PasswordResetAttempt.created_at >= window_start,
                )
                .count()
            )

            assert count == MAX_REQUESTS, (
                f"Expected {MAX_REQUESTS} attempts, found {count}"
            )

            print("PASS: Database contains exactly five attempts")

        finally:
            db.close()

        print()
        print("ALL PASSWORD RESET CONCURRENCY TESTS PASSED")

    finally:
        # This test uses separate committed transactions to
        # reproduce real concurrent requests. Clean up only
        # the records belonging to this unique test IP.
        cleanup_db = SessionLocal()

        try:
            cleanup_db.execute(
                delete(PasswordResetAttempt).where(
                    PasswordResetAttempt.ip_hash == ip_hash
                )
            )
            cleanup_db.commit()
            print("Test records cleaned up.")

        except Exception:
            cleanup_db.rollback()
            raise

        finally:
            cleanup_db.close()


if __name__ == "__main__":
    main()

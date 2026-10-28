
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.password_reset_attempt import PasswordResetAttempt


MAX_REQUESTS = 5
WINDOW_MINUTES = 15

# Identificador exclusivo para el bloqueo de este mecanismo.
ADVISORY_LOCK_NAMESPACE = 742091


def hash_client_ip(ip_address: str) -> str:
    """
    Generate a keyed hash of the client IP.

    The original IP address is never stored.
    """
    if not ip_address or not ip_address.strip():
        raise ValueError("Client IP address is required.")

    key = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        b"kairo:password-reset:ip:v1",
        hashlib.sha256,
    ).digest()

    return hmac.new(
        key,
        ip_address.strip().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def allow_password_reset_request(
    db: Session,
    ip_address: str,
) -> bool:
    """
    Check and register a password reset request.

    Returns True when allowed and False when the
    IP has reached the request limit.

    The caller must commit an allowed attempt.
    Rejected attempts are rolled back here.
    """

    ip_hash = hash_client_ip(ip_address)

    # Convert the first 32 bits to a signed PostgreSQL integer.
    # pg_advisory_xact_lock(namespace, key) requires
    # two signed 32-bit integers.
    lock_key = int(ip_hash[:8], 16)

    if lock_key >= 2**31:
        lock_key -= 2**32

    # Serialize checks for the same IP across backend processes.
    db.execute(
        text(
            "SELECT pg_advisory_xact_lock("
            ":namespace, :lock_key)"
        ),
        {
            "namespace": ADVISORY_LOCK_NAMESPACE,
            "lock_key": lock_key,
        },
    )

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=WINDOW_MINUTES)

    recent_attempts = (
        db.query(func.count(PasswordResetAttempt.id))
        .filter(
            PasswordResetAttempt.ip_hash == ip_hash,
            PasswordResetAttempt.created_at >= window_start,
        )
        .scalar()
    )

    if recent_attempts >= MAX_REQUESTS:
        db.rollback()
        return False

    attempt = PasswordResetAttempt(
        ip_hash=ip_hash,
        created_at=now,
    )

    db.add(attempt)

    return True

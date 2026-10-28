
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.business import Business
from app.models.user import User
from app.models.password_reset_token import PasswordResetToken
from app.auth.password_reset import (
    create_password_reset_token,
    hash_reset_token,
    reset_password,
)


def main():
    engine = create_engine(settings.database_url)
    connection = engine.connect()
    transaction = connection.begin()

    db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )

    try:
        unique_id = uuid.uuid4().hex

        email = f"password-reset-test-{unique_id}@example.com"
        business_email = f"business-test-{unique_id}@example.com"

        original_password = "OriginalPassword123!"
        new_password = "NewPassword456!"

        # Create a temporary business.
        business = Business(
            name="KAIRO Password Reset Test",
            industry="wellness",
            email=business_email,
        )

        db.add(business)
        db.flush()

        # Create a temporary user.
        user = User(
            business_id=business.id,
            name="KAIRO Test User",
            email=email,
            password_hash=hash_password(original_password),
            role="owner",
            token_version=0,
        )

        db.add(user)

        # Save test fixtures inside the outer transaction.
        # They will still be removed by the final rollback.
        db.commit()

        user_id = user.id

        print("PASS: Test business and user created")

        # Unknown email must not generate a token.
        unknown_token = create_password_reset_token(
            db=db,
            email=f"unknown-{unique_id}@example.com",
        )

        assert unknown_token is None

        print("PASS: Unknown email produces no token")

        # Generate a valid token.
        token = create_password_reset_token(
            db=db,
            email=email,
        )

        assert token is not None
        assert len(token) > 20

        token_record = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == hash_reset_token(token)
            )
            .first()
        )

        assert token_record is not None
        assert token_record.used_at is None
        assert token_record.token_hash != token

        print("PASS: Reset token generated and stored as hash")

        # Invalid token must be rejected.
        invalid_result = reset_password(
            db=db,
            token="invalid-token",
            new_password=new_password,
        )

        assert invalid_result is False

        print("PASS: Invalid token rejected")

        # Passwords shorter than eight characters are rejected.
        short_password_result = reset_password(
            db=db,
            token=token,
            new_password="short",
        )

        assert short_password_result is False

        print("PASS: Short password rejected")

        # Reload user after the rollback operations.
        user = db.get(User, user_id)

        assert user is not None

        initial_token_version = user.token_version

        # Reset password with a valid token.
        success = reset_password(
            db=db,
            token=token,
            new_password=new_password,
        )

        assert success is True

        db.refresh(user)

        assert verify_password(new_password, user.password_hash)
        assert not verify_password(
            original_password,
            user.password_hash,
        )

        print("PASS: Password updated")

        assert user.token_version == initial_token_version + 1

        print("PASS: Token version incremented")

        # A used token cannot be reused.
        reused_result = reset_password(
            db=db,
            token=token,
            new_password="AnotherPassword789!",
        )

        assert reused_result is False

        print("PASS: Used token cannot be reused")

        # Request cooldown must be enforced.
        cooldown_token = create_password_reset_token(
            db=db,
            email=email,
        )

        assert cooldown_token is None

        print("PASS: Request cooldown enforced")

        # Move the previous token outside the cooldown.
        previous_record = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == hash_reset_token(token)
            )
            .first()
        )

        assert previous_record is not None

        previous_record.created_at = (
            datetime.now(timezone.utc)
            - timedelta(minutes=2)
        )

        db.commit()

        # Generate a second token.
        expired_token = create_password_reset_token(
            db=db,
            email=email,
        )

        assert expired_token is not None

        expired_record = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash
                == hash_reset_token(expired_token)
            )
            .first()
        )

        assert expired_record is not None

        # Simulate expiration.
        expired_record.expires_at = (
            datetime.now(timezone.utc)
            - timedelta(minutes=1)
        )

        db.commit()

        expired_result = reset_password(
            db=db,
            token=expired_token,
            new_password="ExpiredPassword123!",
        )

        assert expired_result is False

        print("PASS: Expired token rejected")

        # Verify the expired token did not change the password.
        db.expire_all()

        user = db.get(User, user_id)

        assert user is not None
        assert verify_password(new_password, user.password_hash)
        assert not verify_password(
            "ExpiredPassword123!",
            user.password_hash,
        )

        print("PASS: Expired token does not change password")

        print()
        print("ALL PASSWORD RESET TESTS PASSED")

    finally:
        db.close()
        transaction.rollback()
        connection.close()
        engine.dispose()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    main()

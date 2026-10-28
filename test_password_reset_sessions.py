
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.main import app
from app.core.config import settings
from app.core.security import hash_password
from app.core.jwt import create_access_token
from app.db.session import get_db
from app.models.business import Business
from app.models.user import User
from app.auth.password_reset import (
    create_password_reset_token,
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

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        unique_id = uuid.uuid4().hex
        email = f"session-test-{unique_id}@example.com"

        business = Business(
            name="KAIRO Session Security Test",
            industry="wellness",
            email=f"business-{unique_id}@example.com",
        )

        db.add(business)
        db.flush()

        user = User(
            business_id=business.id,
            name="KAIRO Session Test",
            email=email,
            password_hash=hash_password("OriginalPassword123!"),
            role="owner",
            token_version=0,
        )

        db.add(user)
        db.commit()

        user_id = user.id

        old_jwt = create_access_token(
            data={
                "sub": str(user_id),
                "email": email,
                "role": "owner",
                "token_version": 0,
            }
        )

        with TestClient(app) as client:
            old_headers = {
                "Authorization": f"Bearer {old_jwt}"
            }

            response = client.get(
                "/auth/me",
                headers=old_headers,
            )

            assert response.status_code == 200, (
                f"Expected HTTP 200 before reset, "
                f"got {response.status_code}: {response.text}"
            )

            print("PASS: Old JWT accepted before password reset")

            reset_token = create_password_reset_token(
                db=db,
                email=email,
            )

            assert reset_token is not None

            changed = reset_password(
                db=db,
                token=reset_token,
                new_password="NewPassword456!",
            )

            assert changed is True

            db.expire_all()
            updated_user = db.get(User, user_id)

            assert updated_user is not None
            assert updated_user.token_version == 1

            response = client.get(
                "/auth/me",
                headers=old_headers,
            )

            assert response.status_code == 401, (
                f"Expected HTTP 401 after reset, "
                f"got {response.status_code}: {response.text}"
            )

            print("PASS: Old JWT rejected after password reset")

            new_jwt = create_access_token(
                data={
                    "sub": str(user_id),
                    "email": email,
                    "role": "owner",
                    "token_version": updated_user.token_version,
                }
            )

            response = client.get(
                "/auth/me",
                headers={
                    "Authorization": f"Bearer {new_jwt}"
                },
            )

            assert response.status_code == 200, (
                f"Expected HTTP 200 for new JWT, "
                f"got {response.status_code}: {response.text}"
            )

            print("PASS: New JWT accepted after password reset")

        print()
        print("ALL PASSWORD RESET SESSION TESTS PASSED")

    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        transaction.rollback()
        connection.close()
        engine.dispose()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    main()

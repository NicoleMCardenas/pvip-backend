
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

        business = Business(
            name="KAIRO Permissions Test",
            industry="wellness",
            email=f"permissions-{unique_id}@example.com",
        )

        db.add(business)
        db.flush()

        users = {}

        for role in ("owner", "manager", "staff"):
            email = f"{role}-{unique_id}@example.com"

            user = User(
                business_id=business.id,
                name=f"KAIRO {role} Test",
                email=email,
                password_hash=hash_password("TestPassword123!"),
                role=role,
                token_version=0,
            )

            db.add(user)
            db.flush()

            users[role] = {
                "id": user.id,
                "email": email,
            }

        db.commit()

        with TestClient(app) as client:
            for role in ("owner", "manager", "staff"):
                user_data = users[role]

                token = create_access_token(
                    data={
                        "sub": str(user_data["id"]),
                        "email": user_data["email"],
                        "role": role,
                        "token_version": 0,
                    }
                )

                headers = {
                    "Authorization": f"Bearer {token}"
                }

                response = client.get(
                    "/business/me",
                    headers=headers,
                )

                assert response.status_code == 200, (
                    f"{role}: GET expected 200, "
                    f"got {response.status_code}: {response.text}"
                )

                print(f"PASS: {role} can read business")

                response = client.patch(
                    "/business/me",
                    headers=headers,
                    json={
                        "name": f"KAIRO Updated by {role}"
                    },
                )

                expected_status = (
                    200 if role == "owner" else 403
                )

                assert response.status_code == expected_status, (
                    f"{role}: PATCH expected {expected_status}, "
                    f"got {response.status_code}: {response.text}"
                )

                print(
                    f"PASS: {role} PATCH returned "
                    f"{expected_status}"
                )

            db.expire_all()

            updated_business = db.get(Business, business.id)

            assert updated_business is not None

            assert updated_business.name == (
                "KAIRO Updated by owner"
            ), (
                "Business name changed unexpectedly."
            )

            print(
                "PASS: Unauthorized roles did not "
                "modify business data"
            )

        print()
        print("ALL BUSINESS PERMISSION TESTS PASSED")

    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        transaction.rollback()
        connection.close()
        engine.dispose()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    main()


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

        original_email = f"business-{unique_id}@example.com"
        occupied_email = f"occupied-{unique_id}@example.com"
        updated_email = f"updated-{unique_id}@example.com"

        business = Business(
            name="KAIRO Business Update Test",
            industry="wellness",
            email=original_email,
            phone="5551234567",
        )

        occupied_business = Business(
            name="KAIRO Other Business",
            industry="wellness",
            email=occupied_email,
        )

        db.add_all([business, occupied_business])
        db.flush()

        user_email = f"owner-{unique_id}@example.com"

        owner = User(
            business_id=business.id,
            name="KAIRO Update Test Owner",
            email=user_email,
            password_hash=hash_password("TestPassword123!"),
            role="owner",
            token_version=0,
        )

        db.add(owner)
        db.flush()

        business_id = business.id
        db.commit()

        token = create_access_token(
            data={
                "sub": str(owner.id),
                "email": user_email,
                "role": "owner",
                "token_version": 0,
            }
        )

        headers = {
            "Authorization": f"Bearer {token}"
        }

        with TestClient(app) as client:
            response = client.patch(
                "/business/me",
                headers=headers,
                json={
                    "name": "  KAIRO Updated Business  ",
                    "industry": "technology",
                },
            )

            assert response.status_code == 200, (
                f"Expected 200 updating business, "
                f"got {response.status_code}: {response.text}"
            )

            assert response.json()["name"] == (
                "KAIRO Updated Business"
            )
            assert response.json()["industry"] == "technology"

            print("PASS: Owner updates name and industry")

            response = client.patch(
                "/business/me",
                headers=headers,
                json={"email": updated_email},
            )

            assert response.status_code == 200, (
                f"Expected 200 updating email, "
                f"got {response.status_code}: {response.text}"
            )

            assert response.json()["email"] == updated_email

            print("PASS: Owner updates business email")

            response = client.patch(
                "/business/me",
                headers=headers,
                json={"phone": None},
            )

            assert response.status_code == 200, (
                f"Expected 200 clearing phone, "
                f"got {response.status_code}: {response.text}"
            )

            assert response.json()["phone"] is None

            print("PASS: Owner clears business phone")

            response = client.patch(
                "/business/me",
                headers=headers,
                json={"email": occupied_email},
            )

            assert response.status_code == 409, (
                f"Expected 409 for duplicate email, "
                f"got {response.status_code}: {response.text}"
            )

            print("PASS: Duplicate business email rejected")

            for field in ("name", "industry"):
                response = client.patch(
                    "/business/me",
                    headers=headers,
                    json={field: "   "},
                )

                assert response.status_code == 422, (
                    f"Expected 422 for empty {field}, "
                    f"got {response.status_code}: {response.text}"
                )

                print(f"PASS: Empty {field} rejected")

            response = client.get(
                "/business/me",
                headers=headers,
            )

            assert response.status_code == 200

            saved = response.json()

            assert saved["name"] == "KAIRO Updated Business"
            assert saved["industry"] == "technology"
            assert saved["email"] == updated_email
            assert saved["phone"] is None

            print("PASS: Invalid updates did not change data")

            db.expire_all()
            saved_business = db.get(Business, business_id)

            assert saved_business is not None
            assert saved_business.email == updated_email

            print("PASS: Changes persisted within test transaction")

        print()
        print("ALL BUSINESS UPDATE TESTS PASSED")

    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        transaction.rollback()
        connection.close()
        engine.dispose()

        print("Test transaction rolled back.")


if __name__ == "__main__":
    main()

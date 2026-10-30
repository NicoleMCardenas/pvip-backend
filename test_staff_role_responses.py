from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.staff.router as staff_router
from app.auth.dependencies import get_current_user
from app.db.session import get_db


staff_id = uuid4()
business_id = uuid4()

fake_staff = SimpleNamespace(
    id=staff_id,
    business_id=business_id,
    name="Empleado de prueba",
    email="empleado@example.com",
    phone="5551234567",
    role="staff",
    status="active",
    created_at=datetime.now(timezone.utc),
    updated_at=None,
)

app = FastAPI()
app.include_router(staff_router.router)

app.dependency_overrides[get_db] = lambda: None

original_get_staff_members = staff_router.get_staff_members
original_get_staff_member_by_id = staff_router.get_staff_member_by_id

operational_fields = {
    "id",
    "name",
    "role",
    "status",
}

administrative_fields = {
    "email",
    "phone",
    "business_id",
    "created_at",
    "updated_at",
}


def verify_response(data, role):
    if role == "owner":
        expected_fields = operational_fields | administrative_fields
        assert set(data.keys()) == expected_fields, data
    else:
        assert set(data.keys()) == operational_fields, data

    assert data["name"] == "Empleado de prueba"
    assert data["status"] == "active"


try:
    staff_router.get_staff_members = (
        lambda *args, **kwargs: [fake_staff]
    )

    staff_router.get_staff_member_by_id = (
        lambda *args, **kwargs: fake_staff
    )

    http = TestClient(app)

    for role in ("owner", "staff"):
        app.dependency_overrides[get_current_user] = (
            lambda role=role: SimpleNamespace(
                role=role,
                business_id=business_id,
            )
        )

        # GET /staff/
        response = http.get("/staff/")
        assert response.status_code == 200, response.text

        members = response.json()
        assert len(members) == 1
        verify_response(members[0], role)

        print(f"PASS: GET listado Personal - {role}")

        # GET /staff/{staff_id}
        response = http.get(f"/staff/{staff_id}")
        assert response.status_code == 200, response.text

        verify_response(response.json(), role)

        print(f"PASS: GET individual Personal - {role}")

    print("ALL STAFF ROLE RESPONSE TESTS PASSED")

finally:
    staff_router.get_staff_members = original_get_staff_members
    staff_router.get_staff_member_by_id = original_get_staff_member_by_id
    app.dependency_overrides.clear()
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.clients.router import router as clients_router
from app.staff.router import router as staff_router


app = FastAPI()
app.include_router(clients_router)
app.include_router(staff_router)

app.dependency_overrides[get_db] = lambda: None
app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
    role="staff",
    business_id=uuid4(),
)

http = TestClient(app)
fake_id = str(uuid4())

restricted_routes = [
    ("GET", "/clients/archived"),
    ("GET", f"/clients/{fake_id}/status"),
    ("PATCH", f"/clients/{fake_id}"),
    ("DELETE", f"/clients/{fake_id}"),
    ("PATCH", f"/clients/{fake_id}/restore"),
    ("POST", "/staff/"),
    ("PATCH", f"/staff/{fake_id}"),
    ("DELETE", f"/staff/{fake_id}"),
]

for method, path in restricted_routes:
    response = http.request(method, path)

    assert response.status_code == 403, (
        f"{method} {path}: "
        f"Se esperaba 403, se obtuvo {response.status_code}. "
        f"{response.text}"
    )

    print(f"PASS: Staff bloqueado - {method} {path}")

print("ALL ADMIN ROUTE PERMISSION TESTS PASSED")
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.clients.router as clients_router
from app.auth.dependencies import get_current_user
from app.db.session import get_db


client_id = uuid4()
business_id = uuid4()

fake_client = SimpleNamespace(
    id=client_id,
    business_id=business_id,
    name="Cliente de prueba",
    email=None,
    phone=None,
    status="active",
    previous_status="new",
    lifetime_value=Decimal("2500.00"),
    total_visits=8,
    last_visit=None,
    created_at=datetime.now(timezone.utc),
    updated_at=None,
)

app = FastAPI()
app.include_router(clients_router.router)

app.dependency_overrides[get_db] = lambda: None

original_get_client = clients_router.get_client_by_id
original_get_clients = clients_router.get_clients
original_create_client = clients_router.create_client

restricted_fields = {
    "lifetime_value",
    "total_visits",
    "previous_status",
    "business_id",
    "created_at",
    "updated_at",
}


def verify_response(data, role):
    if role == "owner":
        assert restricted_fields.issubset(data.keys()), data
    else:
        assert restricted_fields.isdisjoint(data.keys()), data

    assert data["name"] == "Cliente de prueba"


try:
    clients_router.get_client_by_id = (
        lambda *args, **kwargs: fake_client
    )

    clients_router.get_clients = (
        lambda *args, **kwargs: [fake_client]
    )

    clients_router.create_client = (
        lambda *args, **kwargs: fake_client
    )

    http = TestClient(app)

    for role in ("owner", "staff"):
        app.dependency_overrides[get_current_user] = (
            lambda role=role: SimpleNamespace(
                role=role,
                business_id=business_id,
            )
        )

        # Consulta individual
        response = http.get(f"/clients/{client_id}")
        assert response.status_code == 200, response.text
        verify_response(response.json(), role)
        print(f"PASS: GET individual - {role}")

        # Listado de clientes
        response = http.get("/clients/")
        assert response.status_code == 200, response.text

        clients = response.json()
        assert len(clients) == 1
        verify_response(clients[0], role)
        print(f"PASS: GET listado - {role}")

        # Creación simulada, sin guardar en PostgreSQL
        response = http.post(
            "/clients/",
            json={"name": "Cliente de prueba"},
        )
        assert response.status_code == 200, response.text

        verify_response(response.json(), role)
        print(f"PASS: POST creación - {role}")

    print("ALL CLIENT ROLE RESPONSE TESTS PASSED")

finally:
    clients_router.get_client_by_id = original_get_client
    clients_router.get_clients = original_get_clients
    clients_router.create_client = original_create_client
    app.dependency_overrides.clear()
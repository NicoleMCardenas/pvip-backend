from typing import Optional
from sqlalchemy.orm import Session

from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate


def create_client(data: ClientCreate, business_id: str, db: Session):
    client = Client(
        business_id=business_id,
        name=data.name,
        email=data.email,
        phone=data.phone
    )

    db.add(client)
    db.commit()
    db.refresh(client)

    return client


def get_clients(
    business_id: str,
    db: Session,
    search: str = None,
    status: str = None
):
    query = db.query(Client).filter(
        Client.business_id == business_id,
        Client.status != "archived"
    )

    if search:
        query = query.filter(
            Client.name.ilike(f"%{search}%")
        )

    if status:
        query = query.filter(
            Client.status == status
        )

    return query.order_by(Client.created_at.desc()).all()


def get_archived_clients(
    business_id: str,
    db: Session,
    search: str = None
):
    query = db.query(Client).filter(
        Client.business_id == business_id,
        Client.status == "archived"
    )

    if search:
        query = query.filter(
            Client.name.ilike(f"%{search}%")
        )

    return query.order_by(Client.created_at.desc()).all()


def get_client_status_by_id(
    client_id: str,
    business_id: str,
    db: Session
):
    return db.query(Client).filter(
        Client.id == client_id,
        Client.business_id == business_id
    ).first()


def get_client_by_id(
    client_id: str,
    business_id: str,
    db: Session
):
    return db.query(Client).filter(
        Client.id == client_id,
        Client.business_id == business_id,
        Client.status != "archived"
    ).first()


def get_archived_client_by_id(
    client_id: str,
    business_id: str,
    db: Session
):
    return db.query(Client).filter(
        Client.id == client_id,
        Client.business_id == business_id,
        Client.status == "archived"
    ).first()


def update_client(client: Client, data: ClientUpdate, db: Session):
    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(client, key, value)

    db.commit()
    db.refresh(client)

    return client



def archive_client(client: Client, db: Session):
    if client.status == "archived":
        raise ValueError("Customer is already archived.")

    client.previous_status = client.status
    client.status = "archived"

    db.commit()
    db.refresh(client)

    return client


def restore_client(
    client: Client,
    db: Session,
    fallback_status: Optional[str] = None
):
    valid_statuses = {"new", "active", "at_risk"}

    if client.status != "archived":
        raise ValueError("Customer is not archived.")

    if client.previous_status in valid_statuses:
        restored_status = client.previous_status
    elif fallback_status in valid_statuses:
        restored_status = fallback_status
    else:
        raise ValueError(
            "Previous customer status is unknown. "
            "A valid restoration status is required."
        )

    client.status = restored_status
    client.previous_status = None

    db.commit()
    db.refresh(client)

    return client

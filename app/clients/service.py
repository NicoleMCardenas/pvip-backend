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


def get_clients(business_id: str, db: Session):
    return db.query(Client).filter(
        Client.business_id == business_id
    ).all()


def get_client_by_id(client_id: str, business_id: str, db: Session):
    return db.query(Client).filter(
        Client.id == client_id,
        Client.business_id == business_id
    ).first()


def update_client(client: Client, data: ClientUpdate, db: Session):
    update_data = data.dict(exclude_unset=True)

    for key, value in update_data.items():
        setattr(client, key, value)

    db.commit()
    db.refresh(client)

    return client


def delete_client(client: Client, db: Session):
    db.delete(client)
    db.commit()
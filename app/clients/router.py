from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User

from app.schemas.client import (
    ClientCreate,
    ClientUpdate,
    ClientResponse
)

from app.clients.service import (
    create_client,
    get_clients,
    get_client_by_id,
    update_client,
    delete_client
)


router = APIRouter(
    prefix="/clients",
    tags=["Clients"]
)


@router.post("/", response_model=ClientResponse)
def create_my_client(
    data: ClientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return create_client(
        data,
        current_user.business_id,
        db
    )


@router.get("/", response_model=List[ClientResponse])
def list_my_clients(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_clients(
        current_user.business_id,
        db
    )


@router.get("/{client_id}", response_model=ClientResponse)
def get_my_client(
    client_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    client = get_client_by_id(
        client_id,
        current_user.business_id,
        db
    )

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado."
        )

    return client


@router.patch("/{client_id}", response_model=ClientResponse)
def update_my_client(
    client_id: UUID,
    data: ClientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    client = get_client_by_id(
        client_id,
        current_user.business_id,
        db
    )

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado."
        )

    return update_client(
        client,
        data,
        db
    )


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_client(
    client_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    client = get_client_by_id(
        client_id,
        current_user.business_id,
        db
    )

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado."
        )

    delete_client(client, db)

    return None
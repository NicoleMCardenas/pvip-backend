
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
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
    get_archived_clients,
    get_client_by_id,
    get_archived_client_by_id,
    get_client_status_by_id,
    update_client,
    archive_client,
    restore_client
)


router = APIRouter(
    prefix="/clients",
    tags=["Clients"]
)


class RestoreClientRequest(BaseModel):
    fallback_status: Optional[
        Literal["new", "active", "at_risk"]
    ] = None


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
    search: str = None,
    status: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_clients(
        current_user.business_id,
        db,
        search,
        status
    )


# This route must be declared before /{client_id}.
@router.get("/archived", response_model=List[ClientResponse])
def list_my_archived_clients(
    search: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_archived_clients(
        current_user.business_id,
        db,
        search
    )


@router.get(
    "/{client_id}/status",
    response_model=ClientResponse
)
def get_my_client_status(
    client_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    client = get_client_status_by_id(
        client_id,
        current_user.business_id,
        db
    )

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found."
        )

    return client


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


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def archive_my_client(
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

    archive_client(client, db)

    return None


@router.patch(
    "/{client_id}/restore",
    response_model=ClientResponse
)
def restore_my_client(
    client_id: UUID,
    data: RestoreClientRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    client = get_archived_client_by_id(
        client_id,
        current_user.business_id,
        db
    )

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente archivado no encontrado."
        )

    try:
        return restore_client(
            client,
            db,
            fallback_status=data.fallback_status
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        ) from error

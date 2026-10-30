from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User

from app.schemas.service import (
    ServiceCreate,
    ServiceUpdate,
    ServiceResponse
)

from app.services.service import (
    create_service,
    get_services,
    get_service_by_id,
    update_service,
    delete_service
)


router = APIRouter(
    prefix="/services",
    tags=["Services"]
)


@router.post("/", response_model=ServiceResponse)
def create_my_service(
    data: ServiceCreate,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db)
):
    return create_service(data, current_user.business_id, db)


@router.get("/", response_model=List[ServiceResponse])
def list_my_services(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_services(current_user.business_id, db)


@router.get("/{service_id}", response_model=ServiceResponse)
def get_my_service(
    service_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = get_service_by_id(service_id, current_user.business_id, db)

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Servicio no encontrado."
        )

    return service


@router.patch("/{service_id}", response_model=ServiceResponse)
def update_my_service(
    service_id: UUID,
    data: ServiceUpdate,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db)
):
    service = get_service_by_id(service_id, current_user.business_id, db)

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Servicio no encontrado."
        )

    return update_service(service, data, db)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_service(
    service_id: UUID,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db)
):
    service = get_service_by_id(service_id, current_user.business_id, db)

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Servicio no encontrado."
        )

    delete_service(service, db)

    return None
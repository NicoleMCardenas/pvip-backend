
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.auth.staff_invitation_email import (
    build_staff_invitation_url,
    send_staff_invitation_email,
)
from app.auth.staff_invitation_schemas import (
    AcceptStaffInvitationRequest,
    AcceptStaffInvitationResponse,
    CreateStaffInvitationRequest,
    StaffInvitationResponse,
)
from app.auth.staff_invitations import (
    accept_staff_invitation,
    create_staff_invitation,
    hash_staff_invitation_token,
)
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.surveys.email_provider import EmailDeliveryStatus


logger = logging.getLogger("kairo.staff_invitations")

router = APIRouter(
    prefix="/auth/staff-invitations",
    tags=["Staff Invitations"],
)


@router.post(
    "",
    response_model=StaffInvitationResponse,
)
def invite_staff(
    data: CreateStaffInvitationRequest,
    current_user: User = Depends(require_roles("owner")),
    db: Session = Depends(get_db),
):
    if not all((
        settings.resend_api_key,
        settings.email_from,
        settings.staff_invitation_public_base_url,
    )):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El envío de invitaciones no está configurado.",
        )

    raw_token = create_staff_invitation(
        db=db,
        business_id=current_user.business_id,
        staff_id=data.staff_id,
        email=str(data.email),
    )

    invitation_url = build_staff_invitation_url(
        settings.staff_invitation_public_base_url,
        raw_token,
        language=data.language,
    )

    delivery_result = send_staff_invitation_email(
        api_key=settings.resend_api_key,
        email_from=settings.email_from,
        recipient_email=str(data.email),
        invitation_url=invitation_url,
        idempotency_key=(
            f"staff-invitation-{hash_staff_invitation_token(raw_token)}"
        ),
        language=data.language,
    )

    if delivery_result.status == EmailDeliveryStatus.ACCEPTED:
        return {
            "message": (
                "La invitación fue aceptada por el servicio de correo."
            )
        }

    logger.warning(
        "Staff invitation email not confirmed. "
        "Delivery status: %s. Error: %s",
        delivery_result.status.value,
        delivery_result.error,
    )

    if delivery_result.status == EmailDeliveryStatus.UNCERTAIN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No fue posible confirmar el envío de la invitación. "
                "Comprueba si el profesional recibió el correo "
                "antes de intentar nuevamente."
            ),
        )

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=(
            "El servicio de correo rechazó la invitación. "
            "No se ha confirmado su envío."
        ),
    )


@router.post(
    "/accept",
    response_model=AcceptStaffInvitationResponse,
)
def accept_invitation(
    data: AcceptStaffInvitationRequest,
    db: Session = Depends(get_db),
):
    success = accept_staff_invitation(
        db=db,
        token=data.token,
        password=data.password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La invitación no es válida o ha expirado.",
        )

    return {
        "message": "Tu cuenta se activó correctamente."
    }

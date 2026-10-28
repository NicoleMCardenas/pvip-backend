
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.auth.schemas import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.auth.service import register_user, login_user
from app.auth.password_reset import (
    create_password_reset_token,
    hash_reset_token,
    reset_password,
)
from app.auth.password_reset_email import (
    build_password_reset_url,
    send_password_reset_email,
)
from app.auth.password_reset_rate_limit import (
    allow_password_reset_request,
)
from app.schemas.user import UserResponse
from app.auth.dependencies import get_current_user
from app.models.user import User


logger = logging.getLogger("kairo.password_reset")

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


FORGOT_PASSWORD_MESSAGE = (
    "Si el correo está registrado, recibirás "
    "instrucciones para recuperar tu contraseña."
)


@router.post("/register", response_model=UserResponse)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    return register_user(data, db)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    return login_user(data, db)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/forgot-password")
def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    response = {"message": FORGOT_PASSWORD_MESSAGE}

    # Do not generate tokens while email delivery is disabled.
    if not settings.password_reset_email_enabled:
        return response

    # Require complete email and frontend configuration.
    if not all((
        settings.resend_api_key,
        settings.email_from,
        settings.password_reset_public_base_url,
    )):
        return response

    # Use the direct connection address, not untrusted
    # forwarding headers supplied by the requester.
    if request.client is None or not request.client.host:
        return response

    client_ip = request.client.host

    # Register the attempt for all email addresses,
    # including addresses that do not belong to a user.
    allowed = allow_password_reset_request(
        db=db,
        ip_address=client_ip,
    )

    if not allowed:
        return response

    # Persist the attempt and release the PostgreSQL lock
    # before generating tokens or contacting Resend.
    db.commit()

    raw_token = create_password_reset_token(
        db=db,
        email=str(data.email),
    )

    if raw_token is None:
        return response

    reset_url = build_password_reset_url(
        settings.password_reset_public_base_url,
        raw_token,
        language=data.language,
    )

    delivery_result = send_password_reset_email(
        api_key=settings.resend_api_key,
        email_from=settings.email_from,
        recipient_email=str(data.email),
        reset_url=reset_url,
        idempotency_key=(
            f"password-reset-{hash_reset_token(raw_token)}"
        ),
        language=data.language,
    )

    if delivery_result.status.value != "accepted":
        logger.warning(
            "Password reset email was not accepted. "
            "Delivery status: %s. Error: %s",
            delivery_result.status.value,
            delivery_result.error,
        )

    return response


@router.post("/reset-password")
def change_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    success = reset_password(
        db=db,
        token=data.token,
        new_password=data.new_password,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de recuperación no es válido o ha expirado.",
        )

    return {
        "message": "Tu contraseña se actualizó correctamente."
    }

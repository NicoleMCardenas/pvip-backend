
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User


DEMO_BUSINESS_ID = uuid5(
    NAMESPACE_URL,
    "kairo-demo-business-v1",
)

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def enforce_demo_read_only(
    *,
    method: str,
    user: User,
) -> None:
    """
    Prevent authenticated demo users from modifying data.

    Regular business accounts are not affected.
    """
    if (
        user.business_id == DEMO_BUSINESS_ID
        and method.upper() in WRITE_METHODS
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "KAIRO Demo es de solo lectura. "
                "Los datos de demostración no pueden modificarse."
            ),
        )

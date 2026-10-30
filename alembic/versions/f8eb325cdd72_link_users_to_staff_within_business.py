
"""link users to staff within business

Revision ID: f8eb325cdd72
Revises: 73e80c9797c5
Create Date: 2026-10-29 21:35:54.320267
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8eb325cdd72"
down_revision: Union[str, Sequence[str], None] = "73e80c9797c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Link user accounts to staff within the same business."""

    op.create_unique_constraint(
        "uq_staff_id_business_id",
        "staff",
        ["id", "business_id"],
    )

    op.add_column(
        "users",
        sa.Column("staff_id", sa.UUID(), nullable=True),
    )

    op.create_unique_constraint(
        "uq_users_staff_id",
        "users",
        ["staff_id"],
    )

    op.create_foreign_key(
        "fk_users_staff_same_business",
        "users",
        "staff",
        ["staff_id", "business_id"],
        ["id", "business_id"],
    )


def downgrade() -> None:
    """Remove the optional user-to-staff relationship."""

    op.drop_constraint(
        "fk_users_staff_same_business",
        "users",
        type_="foreignkey",
    )

    op.drop_constraint(
        "uq_users_staff_id",
        "users",
        type_="unique",
    )

    op.drop_column("users", "staff_id")

    op.drop_constraint(
        "uq_staff_id_business_id",
        "staff",
        type_="unique",
    )

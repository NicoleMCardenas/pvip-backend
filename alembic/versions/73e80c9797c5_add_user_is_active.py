
"""add user is_active

Revision ID: 73e80c9797c5
Revises: 4932c5b0925d
Create Date: 2026-10-29 02:53:35.503729
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "73e80c9797c5"
down_revision: Union[str, Sequence[str], None] = "4932c5b0925d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")

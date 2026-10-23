
"""add client previous status

Revision ID: d8f21a6c904b
Revises: ab67fa773b51

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8f21a6c904b"

down_revision: Union[str, Sequence[str], None] = "ab67fa773b51"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column(
            "previous_status",
            sa.String(),
            nullable=True
        )
    )


def downgrade() -> None:
    op.drop_column(
        "clients",
        "previous_status"
    )

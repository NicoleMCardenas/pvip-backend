
"""add public survey flow fields

Revision ID: 3eb923e622a4
Revises: 5a808cbee263
Create Date: 2026-10-25 22:51:11.094158
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3eb923e622a4"
down_revision: Union[str, Sequence[str], None] = "5a808cbee263"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enlace público seguro. Las encuestas anteriores pueden
    # permanecer sin token hasta que se gestione su migración.
    op.add_column(
        "surveys",
        sa.Column("public_token", sa.String(length=128), nullable=True),
    )

    # Fecha de envío de la invitación.
    op.add_column(
        "surveys",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Cada token público debe identificar una sola encuesta.
    op.create_unique_constraint(
        "uq_surveys_public_token",
        "surveys",
        ["public_token"],
    )

    # Una visita solo puede tener una encuesta asociada.
    op.create_unique_constraint(
        "uq_surveys_visit_id",
        "surveys",
        ["visit_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_surveys_visit_id",
        "surveys",
        type_="unique",
    )

    op.drop_constraint(
        "uq_surveys_public_token",
        "surveys",
        type_="unique",
    )

    op.drop_column("surveys", "sent_at")
    op.drop_column("surveys", "public_token")

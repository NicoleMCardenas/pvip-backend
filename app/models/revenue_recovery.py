import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class RevenueRecovery(Base):
    __tablename__ = "revenue_recoveries"

    __table_args__ = (
        UniqueConstraint(
            "visit_id",
            name="uq_revenue_recoveries_visit",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("retention_cases.id"),
        nullable=False,
        index=True,
    )

    visit_id = Column(
        UUID(as_uuid=True),
        ForeignKey("visits.id"),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
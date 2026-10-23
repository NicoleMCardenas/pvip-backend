
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class RetentionCase(Base):
    __tablename__ = "retention_cases"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'resolved')",
            name="ck_retention_cases_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high')",
            name="ck_retention_cases_priority",
        ),
        Index(
            "uq_retention_cases_open_client",
            "business_id",
            "client_id",
            unique=True,
            postgresql_where=text(
                "status IN ('pending', 'in_progress')"
            ),
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id"),
        nullable=False,
        index=True,
    )

    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
        index=True,
    )

    reason = Column(
        Text,
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
        default="pending",
    )

    priority = Column(
        String,
        nullable=False,
        default="medium",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    resolved_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

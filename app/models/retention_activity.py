
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class RetentionActivity(Base):
    __tablename__ = "retention_activities"

    __table_args__ = (
        CheckConstraint(
            "activity_type IN ('call', 'email', 'message', 'other')",
            name="ck_retention_activities_type",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN "
            "('contacted', 'no_response', 'follow_up_needed', 'other')",
            name="ck_retention_activities_outcome",
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

    activity_type = Column(
        String,
        nullable=False,
    )

    outcome = Column(
        String,
        nullable=True,
    )

    notes = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class SurveyNotification(Base):
    __tablename__ = "survey_notifications"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    survey_id = Column(
        UUID(as_uuid=True),
        ForeignKey("surveys.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    recipient_email = Column(
        String(320),
        nullable=False,
    )

    status = Column(
        String(20),
        nullable=False,
        default="pending",
    )

    attempts = Column(
        Integer,
        nullable=False,
        default=0,
    )

    next_attempt_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    locked_until = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    lock_token = Column(
        UUID(as_uuid=True),
        nullable=True,
    )

    last_error = Column(
        Text,
        nullable=True,
    )

    provider_message_id = Column(
        String(255),
        nullable=True,
    )

    sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

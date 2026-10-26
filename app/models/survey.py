
import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class Survey(Base):
    __tablename__ = "surveys"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id"),
        nullable=False,
    )

    visit_id = Column(
        UUID(as_uuid=True),
        ForeignKey("visits.id"),
        nullable=False,
        unique=True,
    )

    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
        default="pending",
    )

    public_token = Column(
        String(128),
        nullable=True,
        unique=True,
    )

    sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    satisfaction_score = Column(Integer, nullable=True)
    nps_score = Column(Integer, nullable=True)
    rebook_intent = Column(String, nullable=True)
    comment = Column(String, nullable=True)

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

import uuid

from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class Visit(Base):
    __tablename__ = "visits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id"),
        nullable=False
    )

    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=False
    )

    service_id = Column(
        UUID(as_uuid=True),
        ForeignKey("services.id"),
        nullable=False
    )

    staff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("staff.id"),
        nullable=False
    )

    visit_date = Column(DateTime(timezone=True), nullable=False)

    amount = Column(Numeric, nullable=False)

    notes = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
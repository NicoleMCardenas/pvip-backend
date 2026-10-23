
import uuid

from sqlalchemy import Column, String, DateTime, Integer, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.session import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id"),
        nullable=False
    )

    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)

    status = Column(String, nullable=False, default="new")

    # Stores the customer's status before being archived.
    previous_status = Column(String, nullable=True)

    lifetime_value = Column(Numeric, nullable=False, default=0)
    total_visits = Column(Integer, nullable=False, default=0)
    last_visit = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RevenueRecoveryCreate(BaseModel):
    case_id: UUID
    visit_id: UUID


class RevenueRecoveryResponse(BaseModel):
    id: UUID
    case_id: UUID
    visit_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecoveryOpportunityResponse(BaseModel):
    case_id: UUID
    client_id: UUID
    priority: str
    status: str
    estimated_revenue_at_risk: Optional[Decimal] = None


class RevenueRecoveryMetricsResponse(BaseModel):
    as_of: datetime
    open_opportunities: int
    resolved_cases: int
    estimated_revenue_at_risk: Decimal
    estimated_cases: int
    insufficient_data_cases: int
    recovered_revenue: Decimal
    attributed_visits: int
    opportunities: List[RecoveryOpportunityResponse]
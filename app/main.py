
from fastapi import FastAPI

from app.businesses.router import router as business_router
from app.auth.router import router as auth_router
from app.auth.staff_invitation_router import router as staff_invitation_router  # NUEVO
from app.clients.router import router as clients_router
from app.services.router import router as services_router
from app.staff.router import router as staff_router
from app.visits.router import router as visits_router
from app.surveys.router import router as surveys_router
from app.analytics.router import router as analytics_router
from app.retention.router import router as retention_router
from app.revenue_recovery.router import router as revenue_recovery_router


app = FastAPI(
    title="PVIP API",
    description="Client Retention OS for Wellness Brands",
    version="1.0.0",
)

app.include_router(auth_router)
app.include_router(staff_invitation_router)  # NUEVO
app.include_router(business_router)
app.include_router(clients_router)
app.include_router(services_router)
app.include_router(staff_router)
app.include_router(visits_router)
app.include_router(surveys_router)
app.include_router(analytics_router)
app.include_router(retention_router)
app.include_router(revenue_recovery_router)


@app.get("/")
def health_check():
    return {"message": "PVIP Backend is running"}

from fastapi import FastAPI
from app.businesses.router import router as business_router
from app.auth.router import router as auth_router
from app.clients.router import router as clients_router
from app.services.router import router as services_router
from app.staff.router import router as staff_router

app = FastAPI(
    title="PVIP API",
    description="Client Retention OS for Wellness Brands",
    version="1.0.0"
)
app.include_router(auth_router)
app.include_router(business_router)
app.include_router(clients_router)
app.include_router(services_router)
app.include_router(staff_router)

@app.get("/")
def health_check():
    return {"message": "PVIP Backend is running"}
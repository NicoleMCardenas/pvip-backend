from fastapi import FastAPI

app = FastAPI(
    title="PVIP API",
    description="Client Retention OS for Wellness Brands",
    version="1.0.0"
)

@app.get("/")
def health_check():
    return {"message": "PVIP Backend is running"}
from fastapi import FastAPI

app = FastAPI(title="PVIP API")

@app.get("/")
def health_check():
    return {"message": "PVIP Backend is running"}
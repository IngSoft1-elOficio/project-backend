# app/routes/api.py
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["API"])

@router.get("/test")
async def test_endpoint():
    return {"message": "Test endpoint is working!"}

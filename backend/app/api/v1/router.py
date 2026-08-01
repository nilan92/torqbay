from fastapi import APIRouter

from app.api.v1 import admin

api_router = APIRouter()
api_router.include_router(admin.router, tags=["admin"])

from fastapi import APIRouter

from app.api.v1 import admin, assets, auth, customers, jobs, users

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(customers.router, tags=["customers"])
api_router.include_router(assets.router, tags=["assets"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(admin.router, tags=["admin"])

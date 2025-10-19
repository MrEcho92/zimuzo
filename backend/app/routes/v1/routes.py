from fastapi import APIRouter

from app.routes.v1 import users as user_router

api_router = APIRouter()
api_router.include_router(user_router.router, tags=["users"])

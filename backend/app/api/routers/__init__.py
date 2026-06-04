from fastapi import APIRouter

from app.api.routers import auth, chat, health, sql, threads, user_schemas


def create_api_router() -> APIRouter:
    api = APIRouter()
    api.include_router(health.router)
    api.include_router(auth.router)
    api.include_router(user_schemas.router)
    api.include_router(threads.router)
    api.include_router(sql.router)
    api.include_router(chat.router)
    return api

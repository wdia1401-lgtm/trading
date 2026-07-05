from fastapi import APIRouter

from . import adbooker, chat, ideas, trends, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(ideas.router, prefix="/ideas", tags=["ideas"])
api_router.include_router(trends.router, prefix="/trends", tags=["trends"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(adbooker.router, prefix="/adbooker", tags=["adbooker"])

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import create_api_router
from app.config import CORS_ORIGINS
from app.database.session import init_db
from app.services.warmup import warm_recent_schema_contexts


def create_app() -> FastAPI:
    application = FastAPI()

    application.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(create_api_router())

    @application.on_event("startup")
    async def startup_warmup() -> None:
        init_db()
        asyncio.create_task(delayed_schema_warmup())

    return application


async def delayed_schema_warmup() -> None:
    await asyncio.sleep(5)
    await warm_recent_schema_contexts()


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import router as api_router
from app.core.config import Settings
from app.db import models as _models  # noqa: F401 -- register all foreign-key targets
from app.db.session import create_database_engine


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        yield
        application.state.database_engine.dispose()

    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.state.database_engine = create_database_engine(settings.database_url)
    application.include_router(api_router, prefix=settings.api_prefix)
    return application


app = create_app(Settings())

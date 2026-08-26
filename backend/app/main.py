from fastapi import FastAPI

from app.api.router import router as api_router
from app.core.config import Settings

settings = Settings()

app = FastAPI(title=settings.app_name)
app.include_router(api_router, prefix=settings.api_prefix)

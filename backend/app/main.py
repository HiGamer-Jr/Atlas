import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.router import liveness, readiness
from app.api.router import router as api_router
from app.core.config import Settings
from app.core.errors import ApiError, error_response
from app.db import models as _models  # noqa: F401 -- register all foreign-key targets
from app.db.session import create_database_engine, validate_runtime_connection


def create_app(settings: Settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            if settings.environment == "production":
                try:
                    from app.api.router import validate_readiness

                    validate_readiness(application.state.database_engine)
                except (SQLAlchemyError, ValueError):
                    raise RuntimeError(
                        "Production database prerequisites failed"
                    ) from None
            yield
        finally:
            application.state.database_engine.dispose()

    from app.support.gate import observe_request

    def observe_application_request(request: Request):
        if request.scope.get("endpoint") not in (liveness, readiness):
            observe_request(request)

    application = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        dependencies=[Depends(observe_application_request)],
    )
    application.state.database_engine = create_database_engine(settings.database_url)
    from app.identity.email_transport import SMTPEmailTransport

    application.state.email_transport = SMTPEmailTransport(settings)
    from app.grants.registry import MaintenanceActionRegistry

    application.state.maintenance_registry = MaintenanceActionRegistry()
    from secrets import token_bytes

    application.state.maintenance_receipt_key = token_bytes(32)
    application.state.settings = settings
    application.state.datahub_connector = None
    application.state.datahub_raw_store = None
    if settings.datahub_enabled:
        from pathlib import Path

        from app.datahub.connectors.excel import ExcelConnector
        from app.datahub.raw_store import RawStore

        logo = (
            settings.datahub_logo_path
            or Path(__file__).resolve().parents[2]
            / "frontend/src/assets/hiatlas-light.png"
        )
        if not logo.is_file():
            raise ValueError("Enabled Data Hub requires its official logo asset")
        application.state.datahub_connector = ExcelConnector(
            logo, limits=settings.datahub_limits
        )
        application.state.datahub_raw_store = RawStore(settings)
    application.state.clock = lambda: datetime.now(UTC)

    @application.middleware("http")
    async def request_identity(request: Request, call_next):
        request.state.request_id = uuid4()
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 -- sanitize unexpected request failures
            logging.getLogger("app.requests").error(
                "Request failed request_id=%s", request.state.request_id
            )
            response = error_response(
                request,
                ApiError(
                    500, "INTERNAL_ERROR", "Não foi possível concluir a operação."
                ),
            )
        response.headers["X-Request-ID"] = str(request.state.request_id)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @application.exception_handler(ApiError)
    def api_error(request: Request, exc: ApiError):
        from app.identity.sessions import record_access

        # The request transaction has rolled back before this independent denial log.
        with Session(application.state.database_engine) as db, db.begin():
            validate_runtime_connection(db.connection())
            support_denial = getattr(request.state, "support_denial", None)
            grant_denial = getattr(request.state, "grant_denial", None)
            if grant_denial is not None:
                from app.grants.gate import record_denial as record_grant_denial

                record_grant_denial(db, request, grant_denial, exc.code)
            elif support_denial is not None:
                from app.support.services import record_denial

                record_denial(db, request, support_denial, exc.code)
            else:
                record_access(
                    db,
                    request,
                    "auth.request.denied",
                    "DENIED",
                    user_id=getattr(
                        getattr(request.state, "principal", None), "user_id", None
                    ),
                    role=getattr(
                        getattr(request.state, "principal", None), "platform_role", None
                    ),
                    reason=exc.code,
                )
        return error_response(request, exc)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _exc: RequestValidationError):
        # FastAPI's default detail includes raw input (including passwords).
        return error_response(
            request, ApiError(422, "VALIDATION_ERROR", "Dados inválidos.")
        )

    @application.exception_handler(Exception)
    async def internal_error(request: Request, _exc: Exception):
        return error_response(
            request,
            ApiError(500, "INTERNAL_ERROR", "Não foi possível concluir a operação."),
        )

    application.include_router(api_router, prefix=settings.api_prefix)
    return application


app = create_app(Settings())

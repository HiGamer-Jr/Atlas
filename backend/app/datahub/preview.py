"""Explicit technical upload UoW; business services never commit a caller's TX."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.datahub.connectors.base import WorkbookRejected
from app.datahub.models import DataHubImport
from app.datahub.policy import authorize_selection
from app.datahub.services import audit, create_preview, receive_preview, snapshot
from app.datahub.types import Operation
from app.db.session import validate_runtime_connection
from app.identity.tokens import lifecycle_lock
from app.tenancy.contexts import now, revalidate


class PreviewOrchestrator:
    def __init__(self, engine, request):
        self.engine, self.request = engine, request

    def initialize(self, db):
        validate_runtime_connection(db.connection())
        db.info.update(
            settings=self.request.app.state.settings,
            request=self.request,
            clock=getattr(self.request.app.state, "clock", lambda: datetime.now(UTC)),
        )
        lifecycle_lock(db)

    def run(self, principal, scope, filename, content):
        settings = self.request.app.state.settings
        if not settings.datahub_enabled:
            raise ApiError(503, "DATAHUB_UNAVAILABLE", "Data Hub indisponível.")
        # Authenticate/CSRF is supplied by the HTTP dependency; this phase rechecks
        # exact session/context/membership and rights before any expensive parsing.
        with Session(self.engine) as db, db.begin():
            self.initialize(db)
            authorize_selection(
                db, principal, scope, Operation.IMPORT, "COORDENACAO", 1, ()
            )
        try:
            parsed = self.request.app.state.datahub_connector.parse(
                content, settings.datahub_limits
            )
        except WorkbookRejected as exc:
            raise ApiError(
                422, exc.code, "Planilha incompatível ou inválida."
            ) from None
        with Session(self.engine) as db, db.begin():
            self.initialize(db)
            row = receive_preview(
                db, self.request, principal, scope, filename, content, parsed
            )
            receipt_id = row.id
        try:
            with Session(self.engine) as db, db.begin():
                self.initialize(db)
                db.info.update(datahub_parsed=parsed, datahub_import_id=receipt_id)
                result = create_preview(
                    db, self.request, principal, scope, filename, content
                )
            return result  # after actual commit
        except ApiError:
            raise
        except (ValueError, RuntimeError, OSError, SQLAlchemyError):
            # A failed analysis never leaves partially validated rows. Only a
            # separate auditable TX may move the last stable receipt to FAILED.
            try:
                with Session(self.engine) as db, db.begin():
                    self.initialize(db)
                    row = db.scalar(
                        select(DataHubImport)
                        .where(
                            DataHubImport.id == receipt_id,
                            DataHubImport.tenant_id == scope.tenant_id,
                            DataHubImport.contract_id == scope.contract_id,
                            DataHubImport.auth_session_id == principal.session_id,
                            DataHubImport.actor_user_id == principal.user_id,
                        )
                        .with_for_update()
                    )
                    if row is not None and row.status == "VALIDATING":
                        fresh, *_ = revalidate(db, principal, scope)
                        before = snapshot(row)
                        row.status, row.result_code, row.finished_at = (
                            "FAILED",
                            "ANALYSIS_FAILED",
                            now(db),
                        )
                        row.version += 1
                        audit(
                            db,
                            self.request,
                            fresh,
                            scope,
                            row,
                            "datahub.import.failed",
                            before,
                        )
            except (ApiError, ValueError, RuntimeError, OSError, SQLAlchemyError):
                pass  # Preserve last stable status if audit/DB is still unavailable.
            raise ApiError(
                503, "DATAHUB_ANALYSIS_FAILED", "Não foi possível concluir a análise."
            ) from None

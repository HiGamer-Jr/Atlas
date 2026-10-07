"""Confirmation commit and post-rollback technical observation are separate UoWs."""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.datahub.models import DataHubImport
from app.datahub.preview import PreviewOrchestrator
from app.datahub.services import audit, confirm_import, snapshot
from app.tenancy.contexts import now, revalidate


class ConfirmationOrchestrator(PreviewOrchestrator):
    def run(self, principal, scope, import_id, command):
        try:
            with Session(self.engine) as db, db.begin():
                self.initialize(db)
                result = confirm_import(
                    db, self.request, principal, scope, import_id, command
                )
            return result  # no success before actual commit
        except ApiError:
            raise  # Authorization and data conflicts are not technical failures.
        except (ValueError, RuntimeError, OSError, SQLAlchemyError):
            # All business locks/changes are rolled back before this observer.
            try:
                with Session(self.engine) as db, db.begin():
                    self.initialize(db)
                    row = db.scalar(
                        select(DataHubImport)
                        .where(
                            DataHubImport.id == import_id,
                            DataHubImport.tenant_id == scope.tenant_id,
                            DataHubImport.contract_id == scope.contract_id,
                            DataHubImport.access_context_id == scope.id,
                            DataHubImport.auth_session_id == principal.session_id,
                            DataHubImport.actor_user_id == principal.user_id,
                        )
                        .with_for_update()
                    )
                    if (
                        row is not None
                        and row.status == "READY_FOR_CONFIRMATION"
                        and row.version == command.expected_version
                    ):
                        fresh, *_ = revalidate(db, principal, scope)
                        before = snapshot(row)
                        row.status, row.result_code, row.finished_at = (
                            "FAILED",
                            "CONFIRMATION_FAILED",
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
                pass  # Audit unavailable: preserve last stable preview, never fake success.
            raise ApiError(
                503,
                "DATAHUB_CONFIRMATION_FAILED",
                "Não foi possível concluir a importação.",
            ) from None

"""Short authentication transaction before independent import orchestration."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.session import validate_runtime_connection
from app.support.gate import check_request
from app.tenancy.contexts import authenticated, resolve_context


def import_identity(request: Request):
    with Session(request.app.state.database_engine) as db, db.begin():
        validate_runtime_connection(db.connection())
        db.info.update(
            clock=request.app.state.clock,
            settings=request.app.state.settings,
            request=request,
        )
        error = check_request(db, request)
        if error:
            raise error
        principal = authenticated(db, request)
        scope = resolve_context(db, request, principal)
    return principal, scope


ImportIdentity = Annotated[tuple, Depends(import_identity)]

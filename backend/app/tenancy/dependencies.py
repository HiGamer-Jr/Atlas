from typing import Annotated

from fastapi import Depends, Request

from app.identity.dependencies import Database
from app.tenancy.contexts import authenticated, resolve_context
from app.tenancy.schemas import AccessScope


def require_context(request: Request, db: Database) -> AccessScope:
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        from app.identity.tokens import lifecycle_lock

        lifecycle_lock(db)
    principal = authenticated(db, request)
    return resolve_context(db, request, principal)


Context = Annotated[AccessScope, Depends(require_context)]

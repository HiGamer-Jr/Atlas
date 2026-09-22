from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.identity.schemas import Principal
from app.identity.sessions import authenticate

Database = Annotated[Session, Depends(get_db, scope="function")]


def require_principal(request: Request, db: Database) -> Principal:
    principal, _, _ = authenticate(db, request)
    return principal

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.orm import Session


def create_database_engine(database_url: str) -> Engine:
    return create_engine(database_url, hide_parameters=True, pool_pre_ping=True)


def validate_runtime_connection(connection: Connection) -> None:
    """Fail closed if application requests are using an administrative identity."""
    unsafe = connection.execute(
        text("""
        SELECT r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolbypassrls
            OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member = r.oid)
            OR has_database_privilege(current_user, current_database(), 'CREATE')
            OR has_schema_privilege(current_user, 'public', 'CREATE')
            OR EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relowner=r.oid
            )
        FROM pg_roles r WHERE r.rolname = current_user
    """)
    ).scalar_one()
    if unsafe:
        raise ValueError(
            "Unsafe database runtime role; owner/administrative access is forbidden"
        )


def get_db(request: Request) -> Iterator[Session]:
    from app.core.errors import ApiError
    from app.support.gate import check_request, observe_request

    try:
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
            yield db
    except ApiError:
        # The endpoint transaction and ALL its locks have closed. Observe again
        # to persist any expiry/revoke crossed while waiting in the service.
        observe_request(request)
        raise

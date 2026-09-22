"""Safety boundaries for disposable PostgreSQL integration tests only."""

import os
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

MARKER = "hiatlas-disposable-test-db"


def validate_test_urls(owner_url: str, runtime_url: str):
    try:
        owner, runtime = make_url(owner_url), make_url(runtime_url)
    except (ArgumentError, ValueError, TypeError):
        raise ValueError(
            "Invalid test database configuration (values redacted)"
        ) from None
    for url in (owner, runtime):
        if (
            url.drivername != "postgresql+psycopg"
            or url.query
            or not url.host
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*_test", url.database or "")
        ):
            raise ValueError(
                "Only an explicit PostgreSQL database ending in _test is allowed"
            )
    if (owner.host, owner.port, owner.database) != (
        runtime.host,
        runtime.port,
        runtime.database,
    ):
        raise ValueError(
            "Owner and runtime must target the same disposable test database"
        )
    if not owner.username or not runtime.username or owner.username == runtime.username:
        raise ValueError("Owner and runtime must use distinct roles")
    return owner, runtime


def open_test_engines():
    owner_url = os.environ.get("TEST_DATABASE_OWNER_URL", "")
    runtime_url = os.environ.get("TEST_DATABASE_RUNTIME_URL", "")
    owner, runtime = validate_test_urls(owner_url, runtime_url)
    if os.environ.get("HIATLAS_TEST_DATABASE_RESET") != "1":
        raise ValueError("Explicit HIATLAS_TEST_DATABASE_RESET=1 is required")
    engines = [create_engine(url, hide_parameters=True) for url in (owner, runtime)]
    try:
        with engines[0].connect() as conn:
            owner_endpoint = attest_test_connection(conn, owner)
            if conn.execute(
                text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")
            ).scalar_one():
                raise ValueError("Test migration owner must not be a superuser")
        with engines[1].connect() as conn:
            if attest_test_connection(conn, runtime) != owner_endpoint:
                raise ValueError("Owner and runtime reached different servers")
            unsafe = conn.execute(
                text(
                    "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls "
                    "FROM pg_roles WHERE rolname=current_user"
                )
            ).scalar_one()
            if (
                unsafe
                or conn.execute(
                    text("SELECT pg_has_role(current_user, :owner, 'MEMBER')"),
                    {"owner": owner.username},
                ).scalar_one()
            ):
                raise ValueError(
                    "Runtime must be unprivileged and cannot inherit owner privileges"
                )
    except Exception:
        for engine in engines:
            engine.dispose()
        raise
    return engines


def attest_test_connection(conn, expected):
    actual = conn.execute(
        text(
            "SELECT current_database(), current_user, inet_server_addr()::text, "
            "inet_server_port(), shobj_description(oid, 'pg_database') "
            "FROM pg_database WHERE datname=current_database()"
        )
    ).one()
    if actual[0] != expected.database or actual[1] != expected.username:
        raise ValueError("Actual test database identity differs from explicit target")
    if actual[4] != MARKER:
        raise ValueError("Database lacks disposable-test marker; refusing mutations")
    return actual[2], actual[3]

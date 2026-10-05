"""Attested phase11 browser infrastructure; never imported by production code."""

import json
import os
import sys
from pathlib import Path

from sqlalchemy import text


def validate_e2e_environment():
    from tests.database_harness import validate_test_urls

    owner, runtime = validate_test_urls(
        os.environ.get("TEST_DATABASE_OWNER_URL", ""),
        os.environ.get("TEST_DATABASE_RUNTIME_URL", ""),
    )
    if (owner.database, owner.username, runtime.username, owner.host, owner.port) != (
        "hiatlas_phase11_e2e_test",
        "phase11_e2e_owner",
        "phase11_e2e_runtime",
        "127.0.0.1",
        55491,
    ):
        raise ValueError("Dedicated disposable E2E database configuration required")
    if (
        os.environ.get("HIATLAS_E2E_ORIGIN") != "https://localhost:5181"
        or os.environ.get("PUBLIC_ORIGIN") != "https://localhost:5181"
        or os.environ.get("HIATLAS_API_TARGET") != "http://127.0.0.1:8011"
        or os.environ.get("HIATLAS_TEST_DATABASE_RESET") != "1"
    ):
        raise ValueError("Dedicated loopback HTTPS E2E configuration required")
    return {
        "database": owner.database,
        "owner": owner.username,
        "runtime": runtime.username,
        "host": owner.host,
        "port": owner.port,
        "origin": os.environ["HIATLAS_E2E_ORIGIN"],
    }


def set_fixture_password(engine):
    if os.environ.get("HIATLAS_PHASE11_E2E") != "1":
        return
    from sqlalchemy.engine import make_url

    validate_e2e_environment()
    from app.identity.passwords import hash_password
    from tests.database_harness import attest_test_connection, open_test_engines

    owner, runtime = open_test_engines()
    try:
        expected = make_url(os.environ["TEST_DATABASE_RUNTIME_URL"])
        with engine.connect() as connection:
            attest_test_connection(connection, expected)
        password = os.environ["HIATLAS_E2E_PASSWORD"]
        if len(password) < 12:
            raise ValueError("Protected synthetic password missing or unsafe")
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE users SET password_hash=:hash"),
                {"hash": hash_password(password)},
            )
    finally:
        owner.dispose()
        runtime.dispose()


def create_browser_app():
    validate_e2e_environment()
    from phase10_browser_fixture import create_browser_app as factory

    application = factory()
    if os.environ.get("HIATLAS_PHASE11_BUILD") != "1":
        return application
    if os.environ.get("HIATLAS_PHASE10_CONTROLLED") == "1":
        raise ValueError("Build proof requires normal registry")
    from fastapi import Request
    from fastapi.responses import FileResponse, JSONResponse

    dist = (Path(__file__).resolve().parents[1] / "frontend" / "dist").resolve()
    if not (dist / "index.html").is_file():
        raise ValueError("Build output absent")

    @application.middleware("http")
    async def frontend_headers(request: Request, call_next):
        response = await call_next(request)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @application.get("/{asset_path:path}", include_in_schema=False)
    async def built_frontend(asset_path: str):
        if asset_path == "api" or asset_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"code": "NOT_FOUND"})
        target = (dist / asset_path).resolve()
        if not target.is_relative_to(dist):
            return JSONResponse(status_code=404, content={"code": "NOT_FOUND"})
        if target.is_file():
            return FileResponse(target)
        if Path(asset_path).suffix:
            return JSONResponse(status_code=404, content={"code": "NOT_FOUND"})
        return FileResponse(dist / "index.html")

    return application


if __name__ == "__main__":
    try:
        if sys.argv[1:] != ["--validate-env"]:
            raise ValueError("Explicit validation mode required")
        print(json.dumps(validate_e2e_environment()))
    except Exception:  # noqa: BLE001 -- suppress potentially credential-bearing parse diagnostics
        print(
            "Dedicated E2E configuration rejected; no mutation performed",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

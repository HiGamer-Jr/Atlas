from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, message: str, retry_after: int | None = None
    ):
        super().__init__(code)
        self.status, self.code, self.message = status, code, message
        self.retry_after = retry_after


def error_response(request: Request, error: ApiError) -> JSONResponse:
    response = JSONResponse(
        status_code=error.status,
        content={
            "code": error.code,
            "message": error.message,
            "request_id": str(getattr(request.state, "request_id", uuid4())),
        },
        headers={"Cache-Control": "no-store"},
    )
    if error.retry_after is not None:
        response.headers["Retry-After"] = str(error.retry_after)
    if error.code == "SESSION_INVALID":
        for name in ("__Host-hiatlas-session", "__Host-hiatlas-csrf"):
            response.delete_cookie(
                name, path="/", secure=True, httponly=True, samesite="strict"
            )
    return response

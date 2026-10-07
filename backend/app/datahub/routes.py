"""Thin contextual endpoints; mutation UoWs commit before response."""

from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from app.core.errors import ApiError
from app.datahub import queries
from app.datahub.confirmation import ConfirmationOrchestrator
from app.datahub.dependencies import ImportIdentity
from app.datahub.preview import PreviewOrchestrator
from app.datahub.schemas import (
    ConfirmationInput,
    ConfirmationResult,
    ExportInput,
    ImportDetail,
    ImportPage,
    ImportQuery,
    ImportSummary,
    PagedIssues,
    PagedRows,
    TemplateCatalog,
    TemplateInput,
)
from app.identity.dependencies import Database
from app.tenancy.dependencies import Context

router = APIRouter(prefix="/datahub")


def file_response(file):
    return Response(
        file.content,
        media_type=file.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file.filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/templates", response_model=TemplateCatalog)
def templates(request: Request, db: Database, scope: Context):
    return queries.template_catalog(db, request.state.principal, scope)


@router.post("/templates/{template_id}/download")
def template(
    template_id: str,
    command: TemplateInput,
    request: Request,
    db: Database,
    scope: Context,
):
    return file_response(
        queries.download_template(
            db, request.state.principal, scope, template_id, command
        )
    )


@router.post("/imports", status_code=201, response_model=ImportSummary)
async def upload(request: Request, identity: ImportIdentity):
    settings = request.app.state.settings
    if not settings.datahub_enabled:
        raise ApiError(503, "DATAHUB_UNAVAILABLE", "Data Hub indisponível.")
    budget = settings.datahub_limits.max_upload_bytes
    # Cap the complete envelope before multipart parsing/spooling.
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > budget + 128 * 1024:
            raise ApiError(413, "UPLOAD_LIMIT", "A planilha excede o limite permitido.")
        content.extend(chunk)
    request._body = bytes(content)
    try:
        async with request.form(
            max_files=1, max_fields=0, max_part_size=budget
        ) as form:
            if len(form.multi_items()) != 1 or not isinstance(
                form.get("file"), UploadFile
            ):
                raise ApiError(422, "UPLOAD_INVALID", "Envie somente um arquivo XLSX.")
            file = form["file"]
            source = await file.read(budget + 1)
            if not source or len(source) > budget:
                raise ApiError(
                    413, "UPLOAD_LIMIT", "A planilha excede o limite permitido."
                )
            filename = file.filename or "planilha.xlsx"
    except ApiError:
        raise
    except (ValueError, RuntimeError):
        raise ApiError(422, "UPLOAD_INVALID", "Arquivo XLSX inválido.") from None
    return await run_in_threadpool(
        PreviewOrchestrator(request.app.state.database_engine, request).run,
        *identity,
        filename,
        source,
    )


@router.get("/imports", response_model=ImportPage)
def history(
    request: Request,
    db: Database,
    scope: Context,
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=50, ge=1, le=100),
):
    return queries.list_imports(
        db, request.state.principal, scope, ImportQuery(page=page, page_size=page_size)
    )


@router.get("/imports/{import_id}", response_model=ImportDetail)
def detail(import_id: UUID, request: Request, db: Database, scope: Context):
    return queries.get_import(db, request.state.principal, scope, import_id)


@router.get("/imports/{import_id}/rows", response_model=PagedRows)
def rows(
    import_id: UUID,
    request: Request,
    db: Database,
    scope: Context,
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=50, ge=1, le=100),
):
    return queries.list_rows(
        db,
        request.state.principal,
        scope,
        import_id,
        ImportQuery(page=page, page_size=page_size),
    )


@router.get("/imports/{import_id}/issues", response_model=PagedIssues)
def issues(
    import_id: UUID,
    request: Request,
    db: Database,
    scope: Context,
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=50, ge=1, le=100),
):
    return queries.list_issues(
        db,
        request.state.principal,
        scope,
        import_id,
        ImportQuery(page=page, page_size=page_size),
    )


@router.post("/imports/{import_id}/confirm", response_model=ConfirmationResult)
def confirm(
    import_id: UUID,
    command: ConfirmationInput,
    request: Request,
    identity: ImportIdentity,
):
    return ConfirmationOrchestrator(request.app.state.database_engine, request).run(
        *identity, import_id, command
    )


@router.post("/exports")
def export(command: ExportInput, request: Request, db: Database, scope: Context):
    return file_response(
        queries.export_workbook(db, request.state.principal, scope, command)
    )

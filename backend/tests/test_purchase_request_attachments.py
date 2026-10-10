"""Private specifications are bounded, versioned, auditable and currently authorized."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.procurement.requests import command_schemas, commands
from app.procurement.requests.models import (
    PurchaseRequest,
    PurchaseRequestEvent,
    RequestAttachment,
    RequestCommandReceipt,
)
from tests.helpers import select_context
from tests.test_purchase_request_commands import act, create, fail, request
from tests.test_purchase_request_commands import (
    command_case as _command_case,  # noqa: F401
)


def api():
    from app.procurement.requests import attachments

    return attachments


def upload(
    db,
    case,
    row,
    *,
    content=b"Actual specifications",
    filename="spec.txt",
    item_id=None,
    key=None,
):
    _, actor, scope, *_ = case
    return api().add_attachment(
        db,
        request(),
        actor,
        scope,
        row.id,
        row.version,
        item_id,
        filename,
        content,
        key or uuid4(),
    )


def picture(kind):
    out = BytesIO()
    Image.new("RGB", (2, 2), "white").save(out, format=kind)
    return out.getvalue()


def test_download_fresh_private_no_cache(member, db, command_case):
    ids, *_ = command_case
    row = create(db, command_case)
    db.commit()
    headers = select_context(member, ids["contract_a"]) | {
        "Idempotency-Key": str(uuid4())
    }
    path = f"/api/procurement/requests/{row.id}/attachments"
    result = member.post(
        path,
        headers=headers,
        data={"expected_version": "1"},
        files={"file": ("../spec.txt", b"Actual specifications", "text/plain")},
    )
    assert result.status_code == 200, result.text
    attachment = result.json()["attachments"][0]
    assert attachment["filename"] == "spec.txt"
    response = member.get(path + f"/{attachment['id']}/download", headers=headers)
    assert response.status_code == 200
    assert response.content == b"Actual specifications"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "content" not in attachment and "url" not in attachment
    from app.organization.models import MembershipUnitScope

    grant = db.scalar(
        select(MembershipUnitScope).where(
            MembershipUnitScope.membership_id == ids["member_a"],
            MembershipUnitScope.node_id == ids["node"],
        )
    )
    grant.active = False
    db.commit()
    assert (
        member.get(path + f"/{attachment['id']}/download", headers=headers).status_code
        == 403
    )


@pytest.mark.parametrize(
    "kind,name,mime",
    [
        ("PNG", "spec.png", "image/png"),
        ("JPEG", "spec.jpg", "image/jpeg"),
        ("PDF", "spec.pdf", "application/pdf"),
    ],
)
def test_real_image_and_pdf(kind, name, mime):
    result = api().validate_attachment(picture(kind), name)
    assert result.media_type == mime
    assert result.size > 0 and len(result.digest) == 64


def test_type_size_encryption_malformed_and_filename():
    validated = api().validate_attachment(
        b"a" * (5 * 1024 * 1024), "..\\unsafe\r\nname.txt"
    )
    assert validated.size == 5242880
    assert (
        "\r" not in validated.filename
        and "\n" not in validated.filename
        and "\\" not in validated.filename
    )
    with pytest.raises(ApiError) as error:
        api().validate_attachment(b"a" * 5242881, "large.txt")
    assert error.value.status == 413
    pdf = picture("PDF")
    rejected = [
        (b"", "empty.txt"),
        (b"<html>unsafe</html>", "spec.txt"),
        (b"<svg></svg>", "spec.txt"),
        (b"MZevil", "spec.txt"),
        (b"\xff", "spec.txt"),
        (b"text", "spec.png"),
        (picture("PNG")[:-10], "spec.png"),
        (picture("JPEG")[:-10], "spec.jpg"),
        (pdf[:-20], "spec.pdf"),
        (b"%PDF-1.7\n%%EOF", "spec.pdf"),
        (pdf.replace(b"trailer", b"/Encrypt 9 0 R\ntrailer"), "spec.pdf"),
        (pdf.replace(b"trailer", b"/JavaScript\ntrailer"), "spec.pdf"),
        (b"hello", "spec.svg"),
    ]
    for content, filename in rejected:
        with pytest.raises(ApiError):
            api().validate_attachment(content, filename)


def test_cross_item_denied(db, command_case):
    row = create(db, command_case)
    other = create(db, command_case)
    fail(lambda: upload(db, command_case, row, item_id=other.items[0].id), "NOT_FOUND")
    row = upload(db, command_case, row, item_id=row.items[0].id)
    _, actor, scope, *_ = command_case
    fail(
        lambda: api().download_attachment(
            db, actor, scope, other.id, row.attachments[0].id
        ),
        "NOT_FOUND",
    )
    fail(
        lambda: api().download_attachment(
            db, actor, scope, uuid4(), row.attachments[0].id
        ),
        "NOT_FOUND",
    )


def test_receipt_version_current_authority_and_item_preservation(db, command_case):
    ids, actor, scope, *_ = command_case
    before = create(db, command_case)
    key = uuid4()
    row = upload(db, command_case, before, key=key, item_id=before.items[0].id)
    assert upload(
        db, command_case, before, key=key, item_id=before.items[0].id
    ).model_dump(mode="json") == row.model_dump(mode="json")
    fail(
        lambda: upload(
            db,
            command_case,
            before,
            key=key,
            content=b"Changed",
            item_id=before.items[0].id,
        ),
        "IDEMPOTENCY_CONFLICT",
    )
    fail(lambda: upload(db, command_case, before), "VERSION_CONFLICT")
    updated = commands.update_draft(
        db,
        request(),
        actor,
        scope,
        row.id,
        command_schemas.DraftPatch(
            expected_version=row.version,
            items=[
                command_schemas.RequestItemInput(
                    id=row.items[0].id,
                    description="Updated",
                    requested_quantity="2",
                    uom_code="UN",
                )
            ],
        ),
    )
    assert (
        updated.items[0].id == row.items[0].id
        and updated.attachments == row.attachments
    )
    fail(
        lambda: commands.update_draft(
            db,
            request(),
            actor,
            scope,
            row.id,
            command_schemas.DraftPatch(
                expected_version=updated.version,
                items=[
                    command_schemas.RequestItemInput(
                        description="Replacement", requested_quantity="2", uom_code="UN"
                    )
                ],
            ),
        ),
        "ITEM_HAS_ATTACHMENTS",
    )
    assert db.get(PurchaseRequest, row.id).version == updated.version
    from app.tenancy.models import TenantRolePermission

    permission = db.scalar(
        select(TenantRolePermission).where(
            TenantRolePermission.role_id == ids["role_basic"],
            TenantRolePermission.capability == "procurement.requests.create",
        )
    )
    permission.active = False
    db.flush()
    fail(
        lambda: upload(db, command_case, before, key=key, item_id=before.items[0].id),
        "CAPABILITY_DENIED",
    )


def test_concurrent_tenth_file_and_audit_rollback(
    db, db_runtime, command_case, monkeypatch
):
    row = create(db, command_case)
    for _ in range(9):
        row = upload(db, command_case, row)
    db.commit()
    start = Barrier(2)

    def worker():
        with Session(db_runtime) as session:
            session.execute(text("SET LOCAL lock_timeout='8s'"))
            start.wait(timeout=5)
            try:
                result = upload(session, command_case, row)
                session.commit()
                return result.version
            except ApiError as error:
                session.rollback()
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(map(str, results)) == ["11", "VERSION_CONFLICT"]
    latest = commands.queries.get_request(db, command_case[1], command_case[2], row.id)
    assert len(latest.attachments) == 10
    fail(lambda: upload(db, command_case, latest), "ATTACHMENT_LIMIT")
    new = create(db, command_case)
    counts = [
        db.scalar(select(func.count()).select_from(model))
        for model in (RequestAttachment, PurchaseRequestEvent, RequestCommandReceipt)
    ]

    def unavailable(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(commands.events, "append_event", unavailable)
    with pytest.raises(RuntimeError), db.begin_nested():
        upload(db, command_case, new)
    assert [
        db.scalar(select(func.count()).select_from(model))
        for model in (RequestAttachment, PurchaseRequestEvent, RequestCommandReceipt)
    ] == counts
    assert db.get(PurchaseRequest, new.id).version == 1


def test_draft_delete_and_terminal_rules(db, command_case):
    _, actor, scope, *_ = command_case
    row = upload(db, command_case, create(db, command_case))
    attachment = row.attachments[0]
    fail(
        lambda: api().remove_draft_attachment(
            db, request(), actor, scope, row.id, attachment.id, 1
        ),
        "VERSION_CONFLICT",
    )
    deleted = api().remove_draft_attachment(
        db, request(), actor, scope, row.id, attachment.id, row.version
    )
    assert deleted.version == 3 and deleted.attachments == []
    event = db.scalar(
        select(PurchaseRequestEvent).where(
            PurchaseRequestEvent.request_id == row.id,
            PurchaseRequestEvent.sequence == 3,
        )
    )
    assert event.action == "procurement.request.attachment_removed"
    row = upload(db, command_case, deleted)
    row = act(db, command_case, row, "submit")
    fail(
        lambda: api().remove_draft_attachment(
            db, request(), actor, scope, row.id, row.attachments[0].id, row.version
        ),
        "INVALID_TRANSITION",
    )
    for status in (
        "SUBMITTED",
        "IN_TRIAGE",
        "AWAITING_APPROVAL",
        "APPROVED",
        "IN_FULFILLMENT",
        "FULFILLED",
    ):
        stored = db.get(PurchaseRequest, row.id)
        stored.status = status
        db.flush()
        row = commands.queries.get_request(db, actor, scope, row.id)
        row = upload(db, command_case, row)
    for status in ("CLOSED", "CANCELLED", "REJECTED"):
        stored.status = status
        db.flush()
        row = commands.queries.get_request(db, actor, scope, row.id)
        fail(lambda row=row: upload(db, command_case, row), "INVALID_TRANSITION")
        assert (
            api()
            .download_attachment(db, actor, scope, row.id, row.attachments[0].id)
            .content
            == b"Actual specifications"
        )


def test_http_multipart_limits_allowlist_false_mime(member, db, command_case):
    ids, *_ = command_case
    row = create(db, command_case)
    db.commit()
    headers = select_context(member, ids["contract_a"]) | {
        "Idempotency-Key": str(uuid4())
    }
    path = f"/api/procurement/requests/{row.id}/attachments"

    def post(data, files):
        return member.post(path, headers=headers, data=data, files=files)

    assert (
        post(
            {"expected_version": "1"},
            {"file": ("spec.txt", b"a" * 5242881, "text/plain")},
        ).status_code
        == 413
    )
    for data, files in [
        (
            {"expected_version": "1", "unknown": "x"},
            {"file": ("spec.txt", b"spec", "text/plain")},
        ),
        (
            {"expected_version": "1"},
            [
                ("file", ("spec.txt", b"spec", "text/plain")),
                ("file", ("another.txt", b"spec", "text/plain")),
            ],
        ),
        ({"expected_version": "1"}, {"file": ("spec.txt", b"spec", "image/png")}),
    ]:
        assert post(data, files).status_code == 422
    response = post(
        {"expected_version": "1"}, {"file": ("spec.txt", b"a" * 5242880, "text/plain")}
    )
    assert response.status_code == 200, response.text


def test_stream_bound_without_trusted_length_and_auth_before_body(db, command_case):
    import asyncio

    from starlette.requests import Request

    from app.procurement.requests.routes import add_attachment
    from app.tenancy.models import TenantRolePermission

    ids, actor, scope, *_ = command_case
    row = create(db, command_case)
    chunks = 0

    async def receive():
        nonlocal chunks
        chunks += 1
        assert chunks <= 82, "Body limiter kept consuming unbounded stream"
        return {"type": "http.request", "body": b"a" * 65536, "more_body": True}

    for headers in ([], [(b"content-length", b"1")]):
        chunks = 0
        incoming = Request(
            {"type": "http", "method": "POST", "headers": headers}, receive
        )
        incoming.state.principal = actor
        incoming.state.request_id = uuid4()
        with pytest.raises(ApiError) as error:
            asyncio.run(
                add_attachment(
                    row.id,
                    incoming,
                    __import__("fastapi").Response(),
                    db,
                    scope,
                    uuid4(),
                )
            )
        assert error.value.status == 413
    permission = db.scalar(
        select(TenantRolePermission).where(
            TenantRolePermission.role_id == ids["role_basic"],
            TenantRolePermission.capability == "procurement.requests.create",
        )
    )
    permission.active = False
    db.flush()

    async def must_not_read():
        raise AssertionError("Denied upload consumed bytes")

    incoming = Request({"type": "http", "method": "POST", "headers": []}, must_not_read)
    incoming.state.principal = actor
    incoming.state.request_id = uuid4()
    with pytest.raises(ApiError) as error:
        asyncio.run(
            add_attachment(
                row.id, incoming, __import__("fastapi").Response(), db, scope, uuid4()
            )
        )
    assert error.value.status == 403


def test_png_trailing_content_and_pixel_bound():
    import struct
    import zlib

    png = picture("PNG")
    with pytest.raises(ApiError):
        api().validate_attachment(png + b"<html>unsafe</html>", "spec.png")
    # Replace IHDR dimensions and recalculate CRC without allocating a huge image.
    huge = bytearray(png)
    huge[16:24] = struct.pack(">II", 5001, 5000)
    huge[29:33] = struct.pack(">I", zlib.crc32(huge[12:29]))
    with pytest.raises(ApiError):
        api().validate_attachment(bytes(huge), "spec.png")


def test_foreign_scope_nonowner_delete_comment_revocation_and_exact_receipt(
    db, command_case
):
    from dataclasses import replace

    from app.tenancy.models import TenantRolePermission

    ids, actor, scope, buyer, buyer_scope = command_case
    before = create(db, command_case)
    key = uuid4()
    row = upload(db, command_case, before, key=key)
    receipt = db.scalar(
        select(RequestCommandReceipt).where(
            RequestCommandReceipt.request_id == row.id,
            RequestCommandReceipt.route == "attachments",
        )
    )
    assert receipt.result == row.model_dump(mode="json")
    assert (
        receipt.result["attachments"][0]["digest"]
        == "a0beae65a3e431390633cf5d8947652296af453c437add458285f793e715ac91"
    )
    foreign = replace(scope, tenant_id=ids["tenant_b"], contract_id=ids["contract_b"])
    # Scope credential claims alone never grant access to another contract.
    with pytest.raises(ApiError):
        api().download_attachment(db, actor, foreign, row.id, row.attachments[0].id)
    with pytest.raises(ApiError):
        api().remove_draft_attachment(
            db,
            request(),
            buyer,
            buyer_scope,
            row.id,
            row.attachments[0].id,
            row.version,
        )
    row = act(db, command_case, row, "submit")
    assert (
        upload(db, command_case, before, key=key).model_dump(mode="json")
        == receipt.result
    )
    buyer_case = (ids, buyer, buyer_scope, actor, scope)
    submitted = row
    buyer_key = uuid4()
    row = upload(db, buyer_case, submitted, key=buyer_key)
    permission = db.scalar(
        select(TenantRolePermission).where(
            TenantRolePermission.role_id == ids["buyer_role"],
            TenantRolePermission.capability == "procurement.requests.comment",
        )
    )
    permission.active = False
    db.flush()
    fail(lambda: upload(db, buyer_case, submitted, key=buyer_key), "CAPABILITY_DENIED")
    assert (
        api()
        .download_attachment(db, buyer, buyer_scope, row.id, row.attachments[0].id)
        .content
        == b"Actual specifications"
    )
    event = db.scalar(
        select(PurchaseRequestEvent).where(
            PurchaseRequestEvent.request_id == row.id,
            PurchaseRequestEvent.aggregate_version == row.version,
        )
    )
    assert "Actual specifications" not in str(event.payload)


def test_upload_database_lock_wait_keeps_event_loop_responsive(
    db, db_runtime, command_case
):
    import asyncio
    from threading import Event

    from fastapi import Response
    from sqlalchemy import event
    from starlette.requests import Request

    from app.identity.models import User
    from app.procurement.requests.routes import add_attachment

    _, actor, scope, *_ = command_case
    row = create(db, command_case)
    db.commit()
    attempted, heartbeat = Event(), Event()
    body = b'--test-boundary\r\nContent-Disposition: form-data; name="expected_version"\r\n\r\n1\r\n--test-boundary\r\nContent-Disposition: form-data; name="file"; filename="spec.txt"\r\nContent-Type: text/plain\r\n\r\nActual specifications\r\n--test-boundary--\r\n'

    def observe(connection, cursor, statement, params, context, executemany):
        running = connection.info.get("attachment_loop")
        if (
            running
            and "users" in statement
            and "FOR UPDATE" in statement
            and not attempted.is_set()
        ):
            running.call_soon_threadsafe(heartbeat.set)
            attempted.set()

    def upload_waiter():
        with Session(db_runtime) as session:
            session.execute(text("SET LOCAL lock_timeout='8s'"))
            connection = session.connection()
            connection_info = connection.info

            async def invoke():
                connection_info["attachment_loop"] = asyncio.get_running_loop()

                async def receive():
                    return {"type": "http.request", "body": body, "more_body": False}

                incoming = Request(
                    {
                        "type": "http",
                        "method": "POST",
                        "headers": [
                            (
                                b"content-type",
                                b"multipart/form-data; boundary=test-boundary",
                            )
                        ],
                    },
                    receive,
                )
                incoming.state.principal = actor
                incoming.state.request_id = uuid4()
                return await add_attachment(
                    row.id, incoming, Response(), session, scope, uuid4()
                )

            try:
                result = asyncio.run(invoke())
                session.commit()
                return result
            finally:
                connection_info.pop("attachment_loop", None)

    event.listen(db_runtime, "before_cursor_execute", observe)
    try:
        with Session(db_runtime) as blocker, ThreadPoolExecutor(max_workers=1) as pool:
            blocker.scalar(
                select(User).where(User.id == actor.user_id).with_for_update()
            )
            future = pool.submit(upload_waiter)
            try:
                assert attempted.wait(5), (
                    "Upload never attempted the real identity lock"
                )
                responsive = heartbeat.wait(1)
            finally:
                blocker.commit()
            result = future.result(timeout=15)
        assert result.version == 2 and len(result.attachments) == 1
        assert responsive, (
            "Async upload blocked the event loop during a real database lock wait"
        )
    finally:
        event.remove(db_runtime, "before_cursor_execute", observe)


def test_pdf_cross_reference_work_is_bounded():
    import re

    pdf = picture("PDF")
    entry = re.search(rb"(?m)^\d{10} \d{5} n ?$", pdf)
    assert entry is not None
    # An attacker cannot multiply validation work with thousands of repeated offsets.
    oversized_table = (
        pdf[: entry.start()] + (entry[0] + b"\n") * 4097 + pdf[entry.end() :]
    )
    with pytest.raises(ApiError):
        api().validate_attachment(oversized_table, "spec.pdf")

"""Private bytea specifications with conservative validation, never a malware scanner."""

import re
import warnings
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import func, select

from app.core.errors import ApiError
from app.procurement.requests import assignment, commands, events, policy, queries
from app.procurement.requests.command_schemas import VersionCommand
from app.procurement.requests.idempotency import canonical_digest, run_idempotent
from app.procurement.requests.models import PurchaseRequestItem, RequestAttachment
from app.procurement.requests.schemas import AttachmentEventPayload, RequestView
from app.tenancy.contexts import now

MAX_BYTES = 5 * 1024 * 1024
MAX_BODY_BYTES = MAX_BYTES + 65536
ACTIVE = frozenset(
    {
        "SUBMITTED",
        "IN_TRIAGE",
        "AWAITING_APPROVAL",
        "APPROVED",
        "IN_FULFILLMENT",
        "FULFILLED",
    }
)


@dataclass(frozen=True)
class AttachmentDownload:
    content: bytes
    filename: str
    media_type: str


@dataclass(frozen=True)
class ValidatedAttachment:
    filename: str
    media_type: str
    digest: str
    size: int


def invalid_file():
    return ApiError(422, "ATTACHMENT_INVALID", "Arquivo inválido ou tipo indisponível.")


def too_large():
    return ApiError(413, "ATTACHMENT_TOO_LARGE", "Arquivo excede o limite de 5 MiB.")


def sanitize_filename(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1]
    name = re.sub(r'[\x00-\x1f\x7f";]', "_", name).strip(" .")
    if not name or len(name) > 200:
        raise invalid_file()
    return name


def validate_pdf(content):
    # Accept classic cross-reference PDFs only. Unsupported structures fail closed.
    # Decode escaped names before checking active/encrypted/embedded content markers.
    decoded = re.sub(rb"#([0-9a-fA-F]{2})", lambda m: bytes([int(m[1], 16)]), content)
    if re.search(
        rb"/(Encrypt|JavaScript|JS|Launch|OpenAction|AA|EmbeddedFile|Filespec|RichMedia|XFA)\b",
        decoded,
    ):
        raise invalid_file()
    if not re.match(rb"%PDF-1\.[0-7](?:\r?\n|\r)", content):
        raise invalid_file()
    end = re.search(rb"startxref\s+(\d{1,10})\s+%%EOF\s*\Z", content)
    if not end:
        raise invalid_file()
    offset = int(end[1])
    if offset >= len(content) or not content[offset:].startswith(b"xref"):
        raise invalid_file()
    xref = content[offset : end.start()]
    if not re.search(rb"trailer\s*<<.*?/Root\s+\d+\s+\d+\s+R.*?>>", xref, re.DOTALL):
        raise invalid_file()
    if not re.search(rb"/Type\s*/Catalog\b", content) or not re.search(
        rb"/Type\s*/Pages\b", content
    ):
        raise invalid_file()
    # Bound object work, reject repeated offsets, and inspect each object only
    # within its occupied byte range. Never copy a large tail for every entry.
    entries = []
    for match in re.finditer(rb"(?m)^(\d{10}) (\d{5}) n\s*$", xref):
        if len(entries) >= 4096:
            raise invalid_file()
        entries.append((int(match[1]), int(match[2])))
    if not entries or len({start for start, _ in entries}) != len(entries):
        raise invalid_file()
    entries.sort()
    for index, (start, generation) in enumerate(entries):
        boundary = entries[index + 1][0] if index + 1 < len(entries) else offset
        if start >= boundary or boundary > offset:
            raise invalid_file()
        header = re.compile(rb"\d+\s+" + str(generation).encode() + rb"\s+obj\b")
        if not header.match(content, start, boundary):
            raise invalid_file()
        if content.find(b"endobj", start, boundary) < 0:
            raise invalid_file()


def validate_attachment(content: bytes, filename: str) -> ValidatedAttachment:
    if len(content) > MAX_BYTES:
        raise too_large()
    if not content:
        raise invalid_file()
    name = sanitize_filename(filename)
    extension = name.rsplit(".", 1)[-1].lower()
    mime = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "txt": "text/plain",
    }.get(extension)
    if mime is None:
        raise invalid_file()
    if extension == "pdf":
        validate_pdf(content)
    elif extension in {"png", "jpg", "jpeg"}:
        expected = "PNG" if extension == "png" else "JPEG"
        if (expected == "PNG" and not content.startswith(b"\x89PNG\r\n\x1a\n")) or (
            expected == "JPEG" and not content.startswith(b"\xff\xd8\xff")
        ):
            raise invalid_file()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    if (
                        image.format != expected
                        or image.width * image.height > 25_000_000
                        or getattr(image, "n_frames", 1) != 1
                    ):
                        raise invalid_file()
                    image.verify()
                # JPEG verify alone does not decode a truncated pixel stream.
                with Image.open(BytesIO(content)) as image:
                    image.load()
            if expected == "PNG" and not content.endswith(
                b"\x00\x00\x00\x00IEND\xaeB\x60\x82"
            ):
                raise invalid_file()
            if expected == "JPEG" and not content.endswith(b"\xff\xd9"):
                raise invalid_file()
        except (
            OSError,
            ValueError,
            SyntaxError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as error:
            raise invalid_file() from error
    else:
        try:
            value = content.decode("utf-8", errors="strict")
        except UnicodeError as error:
            raise invalid_file() from error
        if (
            not value.strip()
            or any(ord(c) < 32 and c not in "\r\n\t" for c in value)
            or re.search(r"<\s*[!?/a-zA-Z]", value)
            or content.startswith((b"MZ", b"\x7fELF", b"#!", b"%PDF", b"PK\x03\x04"))
        ):
            raise invalid_file()
    return ValidatedAttachment(name, mime, sha256(content).hexdigest(), len(content))


def authorize_add(db, principal, scope, row, origin=None):
    status = origin or row.status
    action = "create" if status == "DRAFT" else "comment"
    member = policy.require_request_actor(db, principal, scope, action)
    policy.require_request_unit(db, principal, scope, row.requesting_node_id, action)
    policy.authorize_request_read(db, principal, scope, row)
    if status == "DRAFT" and not commands.owner(principal, member, row):
        raise policy.denied()
    if status != "DRAFT" and status not in ACTIVE:
        raise commands.invalid()
    return member


def prepare_upload(db, principal, scope, request_id, key):
    assignment.prelock_identities(db, principal.user_id)
    row = commands.load_command_row(db, principal, scope, request_id)
    origin = commands.replay_origin(db, principal, scope, row, "attachments", key)
    authorize_add(db, principal, scope, row, origin)
    return row


def add_attachment(
    db,
    request,
    principal,
    scope,
    request_id: UUID,
    expected_version: int,
    item_id: UUID | None,
    filename: str,
    content: bytes,
    key: UUID,
) -> RequestView:
    assignment.prelock_identities(db, principal.user_id)
    row = commands.load_command_row(db, principal, scope, request_id)
    origin = commands.replay_origin(db, principal, scope, row, "attachments", key)
    authorize_add(db, principal, scope, row, origin)
    validated = validate_attachment(content, filename)
    digest = canonical_digest(
        {
            "expected_version": expected_version,
            "item_id": str(item_id) if item_id else None,
            "filename": validated.filename,
            "media_type": validated.media_type,
            "content_digest": validated.digest,
        }
    )

    def operation():
        member = authorize_add(db, principal, scope, row)
        commands.require_version(row, VersionCommand(expected_version=expected_version))
        if (
            item_id is not None
            and db.scalar(
                queries.scoped(PurchaseRequestItem, scope).where(
                    PurchaseRequestItem.request_id == row.id,
                    PurchaseRequestItem.id == item_id,
                )
            )
            is None
        ):
            raise ApiError(404, "NOT_FOUND", "Item não encontrado.")
        count = db.scalar(
            select(func.count())
            .select_from(RequestAttachment)
            .where(
                RequestAttachment.tenant_id == scope.tenant_id,
                RequestAttachment.contract_id == scope.contract_id,
                RequestAttachment.request_id == row.id,
            )
        )
        if count >= 10:
            raise ApiError(
                422, "ATTACHMENT_LIMIT", "Limite de dez anexos por solicitação."
            )
        before = events.snapshot(db, principal, scope, row)
        entry = RequestAttachment(
            id=uuid4(),
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            request_id=row.id,
            item_id=item_id,
            uploader_user_id=principal.user_id,
            uploader_membership_id=member.id,
            filename=validated.filename,
            media_type=validated.media_type,
            digest=validated.digest,
            size=validated.size,
            content=content,
        )
        db.add(entry)
        row.version += 1
        row.updated_at = now(db)
        return commands.finish(
            db,
            request,
            principal,
            scope,
            row,
            before,
            "attachment_added",
            AttachmentEventPayload(
                attachment_id=entry.id,
                content_digest=validated.digest,
                from_status=before.status,
            ),
            attachment_id=entry.id,
            content_digest=validated.digest,
        )

    return run_idempotent(
        db, principal, scope, "attachments", request_id, key, digest, operation
    )


def download_attachment(
    db, principal, scope, request_id: UUID, attachment_id: UUID
) -> AttachmentDownload:
    row = queries.read_row(db, principal, scope, request_id)
    entry = db.scalar(
        queries.scoped(RequestAttachment, scope).where(
            RequestAttachment.request_id == row.id,
            RequestAttachment.id == attachment_id,
        )
    )
    if entry is None:
        raise ApiError(404, "NOT_FOUND", "Anexo não encontrado.")
    policy.authorize_request_read(db, principal, scope, row)
    return AttachmentDownload(entry.content, entry.filename, entry.media_type)


def remove_draft_attachment(
    db,
    request,
    principal,
    scope,
    request_id: UUID,
    attachment_id: UUID,
    expected_version: int,
) -> RequestView:
    assignment.prelock_identities(db, principal.user_id)
    row = commands.load_command_row(db, principal, scope, request_id)
    member = policy.require_request_actor(db, principal, scope, "create")
    policy.require_request_unit(db, principal, scope, row.requesting_node_id, "create")
    if not commands.owner(principal, member, row):
        raise policy.denied()
    if row.status != "DRAFT":
        raise commands.invalid()
    commands.require_version(row, VersionCommand(expected_version=expected_version))
    entry = db.scalar(
        queries.scoped(RequestAttachment, scope).where(
            RequestAttachment.request_id == row.id,
            RequestAttachment.id == attachment_id,
        )
    )
    if entry is None:
        raise ApiError(404, "NOT_FOUND", "Anexo não encontrado.")
    before = events.snapshot(db, principal, scope, row)
    digest = entry.digest
    db.delete(entry)
    row.version += 1
    row.updated_at = now(db)
    return commands.finish(
        db,
        request,
        principal,
        scope,
        row,
        before,
        "attachment_removed",
        AttachmentEventPayload(
            attachment_id=attachment_id,
            content_digest=digest,
            from_status=before.status,
        ),
        attachment_id=attachment_id,
        content_digest=digest,
    )

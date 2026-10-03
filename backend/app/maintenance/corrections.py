"""Closed correction previews and atomic audited mutations."""

import hmac
import json
from hashlib import sha256
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select

from app.audit.schemas import AuditInput
from app.audit.service import append_event
from app.core.errors import ApiError
from app.grants.models import TemporaryPrivilegedGrant
from app.grants.services import require_maintenance, require_module, validate_bound
from app.maintenance.registry import MaintenanceHandler
from app.maintenance.schemas import command_schema
from app.platform.capabilities import INTERNAL_GRANTS
from app.tenancy.contexts import now, revalidate


def conflict():
    return ApiError(
        409, "VERSION_CONFLICT", "O estado foi alterado. Revise uma nova prévia."
    )


def typed_action(request, code):
    action = request.app.state.maintenance_registry.get(code)
    if not isinstance(action.handler, MaintenanceHandler):
        raise ApiError(
            403,
            "MAINTENANCE_HANDLER_UNAVAILABLE",
            "Operação de manutenção indisponível.",
        )
    return action


def command(request, payload, *, apply=False):
    if not isinstance(payload, dict) or not isinstance(payload.get("action_code"), str):
        raise ApiError(422, "VALIDATION_ERROR", "Dados inválidos.")
    action = typed_action(request, payload["action_code"])
    try:
        return action, command_schema(action, apply=apply).model_validate(payload)
    except ValidationError:
        raise ApiError(422, "VALIDATION_ERROR", "Dados inválidos.") from None


def snapshot(handler, entity):
    # Explicit names from the registered output contract; no ORM/dict serialization.
    return handler.snapshot_type.model_validate(
        {key: getattr(entity, key) for key in handler.snapshot_type.model_fields}
    )


def grant(db, scope):
    return db.scalar(
        select(TemporaryPrivilegedGrant).where(
            TemporaryPrivilegedGrant.context_id == scope.id
        )
    )


def authorize(db, request, principal, scope, action, entity_id):
    require_maintenance(
        db, request, principal, scope, action.action_code, action.entity_type, entity_id
    )
    return grant(db, scope)


def signed_receipt(
    request, principal, scope, row, cmd, before, after, effects, deadline
):
    value = {
        "context": str(scope.id),
        "grant": str(row.id),
        "operator": str(principal.user_id),
        "session": str(principal.session_id),
        "tenant": str(scope.tenant_id),
        "contract": str(scope.contract_id),
        "command": cmd.model_dump(mode="json", exclude={"preview_receipt"}),
        "before": before.model_dump(mode="json"),
        "after": after.model_dump(mode="json"),
        "effects": effects,
        "deadline": deadline,
    }
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    signature = hmac.new(
        request.app.state.maintenance_receipt_key, encoded, sha256
    ).hexdigest()
    return str(deadline) + "." + signature


def isolated_preview(db, handler, entity, typed):
    before = snapshot(handler, entity)
    savepoint = db.begin_nested()
    try:
        result = handler.snapshot_type.model_validate(handler.preview(entity, typed))
        db.flush()
        changed = snapshot(handler, entity) != before
    finally:
        # Unconditionally rollback even an explicit handler flush or raw SQL write.
        savepoint.rollback()
    if changed:
        raise RuntimeError("Preview cannot mutate domain state")
    return result


def preview_correction(db, request, principal, scope, action, cmd):
    row = authorize(db, request, principal, scope, action, cmd.entity_id)
    entity = action.handler.load_scoped(db, scope, cmd.entity_id, lock=False)
    if entity is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    if entity.version != cmd.expected_version:
        raise conflict()
    before = snapshot(action.handler, entity)
    after = isolated_preview(db, action.handler, entity, cmd.proposed_input)
    # A preview callback must produce a value without touching persistent state.
    if db.is_modified(entity) or db.new or db.deleted:
        raise RuntimeError("Preview cannot mutate domain state")
    authorize(db, request, principal, scope, action, cmd.entity_id)
    deadline = min(int(now(db).timestamp()) + 300, int(row.expires_at.timestamp()))
    return {
        "action_code": action.action_code,
        "entity_id": cmd.entity_id,
        "expected_version": entity.version,
        "before": before.model_dump(mode="json"),
        "after": after.model_dump(mode="json"),
        "effects": list(action.handler.effects),
        "preview_receipt": signed_receipt(
            request,
            principal,
            scope,
            row,
            cmd,
            before,
            after,
            list(action.handler.effects),
            deadline,
        ),
    }


def apply_correction(db, request, principal, scope, action, cmd):
    authorize(db, request, principal, scope, action, cmd.entity_id)
    entity = action.handler.load_scoped(db, scope, cmd.entity_id, lock=True)
    # The wait may cross revocation, expiry, a module or domain invariant change.
    row = authorize(db, request, principal, scope, action, cmd.entity_id)
    if entity is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    before = snapshot(action.handler, entity)
    if entity.version != cmd.expected_version:
        raise conflict()
    try:
        deadline = int(cmd.preview_receipt.split(".", 1)[0])
    except (ValueError, AttributeError):
        raise conflict() from None
    expected = isolated_preview(db, action.handler, entity, cmd.proposed_input)
    if (
        deadline <= int(now(db).timestamp())
        or deadline > int(row.expires_at.timestamp())
        or not hmac.compare_digest(
            cmd.preview_receipt,
            signed_receipt(
                request,
                principal,
                scope,
                row,
                cmd,
                before,
                expected,
                list(action.handler.effects),
                deadline,
            ),
        )
    ):
        raise conflict()
    action.handler.apply(entity, cmd.proposed_input)
    db.flush()
    authorize(db, request, principal, scope, action, cmd.entity_id)
    after = snapshot(action.handler, entity)
    if after.version != before.version + 1 or after != expected:
        raise RuntimeError("Handler violated its typed preview contract")
    audit_id = append_event(
        db,
        AuditInput(
            actor_id=principal.user_id,
            actor_role=principal.platform_role,
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            entity_type=action.entity_type,
            entity_id=entity.id,
            action="maintenance.correction.applied",
            before=before,
            after=after,
            reason=cmd.reason,
            reference=cmd.reference,
            request_id=getattr(request.state, "request_id", uuid4()),
        ),
    )
    return {
        "audit_event_id": audit_id,
        "action_code": action.action_code,
        "entity_id": entity.id,
        "version": entity.version,
    }


def require_registered_module(db, principal, scope, code):
    if grant(db, scope):
        return require_module(db, principal, scope, code)
    from app.organization.models import ContractModule
    from app.organization.modules import OPERATIONAL_MODULES

    module = db.scalar(
        select(ContractModule)
        .where(
            ContractModule.tenant_id == scope.tenant_id,
            ContractModule.contract_id == scope.contract_id,
            ContractModule.code == code,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    revalidate(db, principal, scope)
    if (
        not module
        or not module.contracted
        or not module.active
        or code not in OPERATIONAL_MODULES
    ):
        raise ApiError(
            403, "MODULE_UNAVAILABLE", "Módulo operacional ainda indisponível."
        )


def catalog(db, request, principal, scope):
    principal, *_ = revalidate(db, principal, scope)
    if principal.platform_role != "PLATFORM_ADMIN":
        raise ApiError(
            403, "PLATFORM_ADMIN_REQUIRED", "Operação restrita à administração HiAtlas."
        )
    row = grant(db, scope)
    if row:
        if row.grant_type != "MAINTENANCE":
            raise ApiError(
                403, "GRANT_CONTEXT_INVALID", "Acesso temporário indisponível."
            )
        validate_bound(db, principal, row)
    items = []
    for action in request.app.state.maintenance_registry.list():
        if not isinstance(
            action.handler, MaintenanceHandler
        ) or action.capability not in INTERNAL_GRANTS.get(principal.platform_role, ()):
            continue
        if action.module_code is not None:
            try:
                require_registered_module(db, principal, scope, action.module_code)
            except ApiError:
                continue
        items.append(
            {
                "action_code": action.action_code,
                "label": action.label,
                "entity_type": action.entity_type,
                "can_correct": True,
                "can_reprocess": action.handler.reprocess is not None,
            }
        )
    return {"items": items, "mode": "MAINTENANCE" if row else "NORMAL"}


def entity_view(db, request, principal, scope, action_code, entity_id):
    principal, *_ = revalidate(db, principal, scope)
    if principal.platform_role != "PLATFORM_ADMIN":
        raise ApiError(
            403, "PLATFORM_ADMIN_REQUIRED", "Operação restrita à administração HiAtlas."
        )
    action = typed_action(request, action_code)
    if grant(db, scope):
        authorize(db, request, principal, scope, action, entity_id)
    elif action.capability not in INTERNAL_GRANTS.get(
        principal.platform_role, ()
    ) or not action.authorize_domain(db, principal, scope, entity_id):
        raise ApiError(403, "CAPABILITY_DENIED", "Ação não permitida.")
    elif action.module_code is not None:
        require_registered_module(db, principal, scope, action.module_code)
    entity = action.handler.load_scoped(db, scope, entity_id, lock=False)
    if entity is None or not action.resolve_entity(db, scope, entity_id):
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    revalidate(db, principal, scope)
    if grant(db, scope):
        authorize(db, request, principal, scope, action, entity_id)
    return snapshot(action.handler, entity).model_dump(mode="json")

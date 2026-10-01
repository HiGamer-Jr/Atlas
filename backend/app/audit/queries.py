"""Scope before filters/pagination; cursors are navigation, never authorization."""

import base64
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select, tuple_

from app.audit.models import AuditEvent
from app.audit.projections import ACCESS_ACTIONS, ROLE_ACTIONS, project
from app.core.errors import ApiError
from app.identity.models import PlatformRoleAssignment
from app.platform.policy import require_capability, safe_role_predicate
from app.tenancy.contexts import revalidate
from app.tenancy.member_queries import last_context_access, read_member
from app.tenancy.models import Membership, TenantRole


def base_query(scope, support=False):
    query = select(AuditEvent).where(
        AuditEvent.tenant_id == scope.tenant_id,
        AuditEvent.contract_id == scope.contract_id,
    )
    if support:
        safe_roles = select(TenantRole.id).where(
            TenantRole.tenant_id == scope.tenant_id,
            TenantRole.contract_id == scope.contract_id,
            safe_role_predicate(),
        )
        members = select(Membership.id).where(
            Membership.tenant_id == scope.tenant_id,
            Membership.contract_id == scope.contract_id,
            Membership.role_id.in_(safe_roles),
            Membership.user_id.not_in(select(PlatformRoleAssignment.user_id)),
        )
        safe_actors = select(Membership.user_id).where(
            Membership.tenant_id == scope.tenant_id,
            Membership.contract_id == scope.contract_id,
            Membership.role_id.in_(safe_roles),
            Membership.user_id.not_in(select(PlatformRoleAssignment.user_id)),
        )
        query = query.where(
            or_(
                and_(
                    AuditEvent.action.in_(ACCESS_ACTIONS),
                    AuditEvent.entity_type == "membership",
                    AuditEvent.entity_id.in_(members),
                ),
                and_(
                    AuditEvent.action.in_(ROLE_ACTIONS),
                    AuditEvent.entity_type == "tenant_role",
                    AuditEvent.entity_id.in_(safe_roles),
                ),
                and_(
                    AuditEvent.action == "context.selected",
                    AuditEvent.entity_type == "access_context",
                    AuditEvent.actor_id.in_(safe_actors),
                ),
            )
        )
    return query


def cursor_encode(scope, row):
    raw = json.dumps(
        [
            str(scope.tenant_id),
            str(scope.contract_id),
            row.occurred_at.isoformat(),
            str(row.id),
        ],
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def cursor_decode(scope, cursor):
    try:
        raw = json.loads(
            base64.b64decode(
                cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True
            )
        )
        if (
            not isinstance(raw, list)
            or len(raw) != 4
            or raw[:2] != [str(scope.tenant_id), str(scope.contract_id)]
        ):
            raise ValueError
        stamp = datetime.fromisoformat(raw[2])
        if stamp.tzinfo is None:
            raise ValueError
        return stamp, UUID(raw[3])
    except (ValueError, TypeError, json.JSONDecodeError):
        raise ApiError(
            422, "INVALID_CURSOR", "Pagina indisponivel neste contexto."
        ) from None


def list_events(
    db, principal, scope, limit, cursor, action, outcome, from_at, to_at, member_id=None
):
    require_capability(
        db, principal, scope, "logs.access.read" if member_id else "audit.read"
    )
    fresh, *_ = revalidate(db, principal, scope)
    if fresh.platform_role not in {"PLATFORM_ADMIN", "PLATFORM_SUPPORT"}:
        raise ApiError(403, "CAPABILITY_DENIED", "Acao nao permitida.")
    for stamp in (from_at, to_at):
        if stamp is not None and stamp.tzinfo is None:
            raise ApiError(422, "INVALID_FILTER", "Informe data com fuso horario.")
    if from_at and to_at and from_at > to_at:
        raise ApiError(422, "INVALID_FILTER", "Periodo invalido.")
    query = base_query(scope, fresh.platform_role == "PLATFORM_SUPPORT")
    member = None
    if member_id:
        member = read_member(db, fresh, scope, member_id)
        query = query.where(
            or_(
                and_(
                    AuditEvent.entity_type == "membership",
                    AuditEvent.entity_id == member_id,
                    AuditEvent.action.in_(ACCESS_ACTIONS),
                ),
                and_(
                    AuditEvent.entity_type == "access_context",
                    AuditEvent.actor_id == member.user_id,
                    AuditEvent.action == "context.selected",
                ),
            )
        )
    if action:
        query = query.where(AuditEvent.action == action)
    if outcome:
        query = query.where(AuditEvent.outcome == outcome)
    if from_at:
        query = query.where(AuditEvent.occurred_at >= from_at)
    if to_at:
        query = query.where(AuditEvent.occurred_at <= to_at)
    if cursor:
        stamp, row_id = cursor_decode(scope, cursor)
        query = query.where(
            tuple_(AuditEvent.occurred_at, AuditEvent.id) < tuple_(stamp, row_id)
        )
    rows = list(
        db.scalars(
            query.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(
                limit + 1
            )
        )
    )
    require_capability(
        db, principal, scope, "logs.access.read" if member_id else "audit.read"
    )
    result = {
        "items": [
            project(db, row, support=fresh.platform_role == "PLATFORM_SUPPORT")
            for row in rows[:limit]
        ],
        "next_cursor": cursor_encode(scope, rows[limit - 1])
        if len(rows) > limit
        else None,
    }
    if member_id:
        # Existing login events are global; their timestamps cannot prove a contract login.
        result["last_access_at"] = last_context_access(db, scope, member.user_id)
    return result


def event_detail(db, principal, scope, event_id):
    require_capability(db, principal, scope, "audit.read")
    fresh, *_ = revalidate(db, principal, scope)
    if fresh.platform_role != "PLATFORM_ADMIN":
        raise ApiError(403, "CAPABILITY_DENIED", "Detalhe indisponivel ao suporte.")
    row = db.scalar(base_query(scope).where(AuditEvent.id == event_id))
    if row is None:
        raise ApiError(404, "NOT_FOUND", "Registro nao encontrado.")
    return project(db, row, detail=True)

"""Fresh contract-scoped unit policy; client identifiers are only candidates."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.organization.catalogue import CHILDREN, LABELS
from app.organization.models import MembershipUnitScope, OrganizationNode
from app.tenancy.models import Membership
from app.tenancy.schemas import AccessScope

MAX_OPERATIONAL_SCOPE_NODES = 1000


@dataclass(frozen=True)
class ResolvedUnitScope:
    mode: Literal["ALL", "RESTRICTED"]
    nodes: tuple[OrganizationNode, ...]


def invalid():
    return ApiError(
        409, "OPERATIONAL_SCOPE_INVALID", "Escopo operacional indisponível."
    )


def fresh_member(db, scope, membership):
    member = db.scalar(
        select(Membership)
        .where(
            Membership.id == membership.id,
            Membership.tenant_id == scope.tenant_id,
            Membership.contract_id == scope.contract_id,
            Membership.user_id == scope.actor_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not member or not member.active or member.blocked or member.invitation_pending:
        raise ApiError(403, "UNIT_SCOPE_DENIED", "Unidade indisponível neste contexto.")
    if member.unit_scope_mode not in {"ALL", "RESTRICTED"}:
        raise invalid()
    return member


def node_query(scope):
    return (
        select(OrganizationNode)
        .where(
            OrganizationNode.tenant_id == scope.tenant_id,
            OrganizationNode.contract_id == scope.contract_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def viable(node, graph):
    visited = set()
    active = True
    while node is not None:
        if node.id in visited or node.kind not in LABELS:
            raise invalid()
        visited.add(node.id)
        active = active and node.active
        if node.parent_id is None:
            break
        parent = graph.get(node.parent_id)
        if parent is None or node.kind not in CHILDREN.get(parent.kind, ()):
            raise invalid()
        node = parent
    return active


def grant_ids(db, scope, member):
    return set(
        db.scalars(
            select(MembershipUnitScope.node_id)
            .where(
                MembershipUnitScope.tenant_id == scope.tenant_id,
                MembershipUnitScope.contract_id == scope.contract_id,
                MembershipUnitScope.membership_id == member.id,
                MembershipUnitScope.active.is_(True),
            )
            .order_by(MembershipUnitScope.node_id)
            .with_for_update()
        )
    )


def resolve_unit_scope(
    db: Session, scope: AccessScope, membership: Membership
) -> ResolvedUnitScope:
    member = fresh_member(db, scope, membership)
    nodes = tuple(
        db.scalars(
            node_query(scope)
            .order_by(OrganizationNode.id)
            .limit(MAX_OPERATIONAL_SCOPE_NODES + 1)
        )
    )
    if len(nodes) > MAX_OPERATIONAL_SCOPE_NODES:
        raise ApiError(
            503,
            "OPERATIONAL_SCOPE_TOO_LARGE",
            "Escopo excede o limite seguro desta versão.",
        )
    graph = {node.id: node for node in nodes}
    available = tuple(node for node in nodes if viable(node, graph))
    permitted = (
        grant_ids(db, scope, member)
        if member.unit_scope_mode == "RESTRICTED"
        else set(graph)
    )
    return ResolvedUnitScope(
        member.unit_scope_mode,
        tuple(node for node in available if node.id in permitted),
    )


def require_authorized_node(
    db: Session, scope: AccessScope, membership: Membership, node_id: UUID
) -> OrganizationNode:
    member = fresh_member(db, scope, membership)
    graph = {}
    current = node_id
    while current is not None:
        if current in graph or len(graph) >= MAX_OPERATIONAL_SCOPE_NODES:
            raise invalid()
        node = db.scalar(node_query(scope).where(OrganizationNode.id == current))
        if node is None:
            if current == node_id:
                raise ApiError(
                    403, "UNIT_SCOPE_DENIED", "Unidade indisponível neste contexto."
                )
            raise invalid()
        graph[current] = node
        current = node.parent_id
    node = graph[node_id]
    if not viable(node, graph) or (
        member.unit_scope_mode == "RESTRICTED"
        and node_id not in grant_ids(db, scope, member)
    ):
        raise ApiError(403, "UNIT_SCOPE_DENIED", "Unidade indisponível neste contexto.")
    return node

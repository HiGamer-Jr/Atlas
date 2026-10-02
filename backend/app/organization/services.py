"""Contract-serialized physical forest commands; context authority stays central."""

from sqlalchemy import Text, cast, func, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.exc import IntegrityError

from app.audit.schemas import MembershipUnitScopeSnapshot, OrganizationNodeSnapshot
from app.core.errors import ApiError
from app.organization.catalogue import CHILDREN, allowed_parents
from app.organization.models import MembershipUnitScope, OrganizationNode
from app.organization.schemas import NodeView
from app.platform.policy import require_capability
from app.platform.roles import revoke_contexts
from app.tenancy.contexts import revalidate
from app.tenancy.member_commands import target_member
from app.tenancy.services import audit


def scoped(model, scope):
    return select(model).where(
        model.tenant_id == scope.tenant_id, model.contract_id == scope.contract_id
    )


def load_node(db, scope, node_id):
    node = db.scalar(
        scoped(OrganizationNode, scope)
        .where(OrganizationNode.id == node_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if node is None:
        raise ApiError(404, "NOT_FOUND", "Registro não encontrado.")
    return node


def ancestors(db, scope, parent_id, moving_id=None):
    result, visited = [], set()
    while parent_id is not None:
        if parent_id == moving_id or parent_id in visited:
            raise ApiError(409, "ORGANIZATION_CYCLE", "A alteração criaria um ciclo.")
        visited.add(parent_id)
        parent = load_node(db, scope, parent_id)
        result.append(parent)
        parent_id = parent.parent_id
    return result


def validate_parent(db, scope, kind, parent_id, active, moving_id=None):
    chain = ancestors(db, scope, parent_id, moving_id)
    if chain and kind not in CHILDREN[chain[0].kind]:
        raise ApiError(422, "INVALID_PARENT_KIND", "Tipo de pai não permitido.")
    if active and any(not parent.active for parent in chain):
        raise ApiError(409, "INACTIVE_ANCESTOR", "Pai e ancestrais devem estar ativos.")
    return chain


def snapshot(node):
    return OrganizationNodeSnapshot(
        **{key: getattr(node, key) for key in OrganizationNodeSnapshot.model_fields}
    )


def counts(db, scope, node_id):
    children = scoped(OrganizationNode, scope).where(
        OrganizationNode.parent_id == node_id
    )
    child_count = db.scalar(select(func.count()).select_from(children.subquery()))
    active_count = db.scalar(
        select(func.count()).select_from(
            children.where(OrganizationNode.active.is_(True)).subquery()
        )
    )
    scopes = scoped(MembershipUnitScope, scope).where(
        MembershipUnitScope.node_id == node_id, MembershipUnitScope.active.is_(True)
    )
    scope_count = db.scalar(select(func.count()).select_from(scopes.subquery()))
    return child_count, active_count, scope_count


def view(db, scope, node):
    chain = ancestors(db, scope, node.parent_id, node.id)
    child_count, active_count, scope_count = counts(db, scope, node.id)
    actions = ["edit"]
    if node.active:
        if active_count == scope_count == 0:
            actions.append("inactivate")
    elif all(parent.active for parent in chain):
        actions.append("activate")
    return NodeView(
        id=node.id,
        tenant_id=node.tenant_id,
        contract_id=node.contract_id,
        parent_name=chain[0].name if chain else None,
        parent_code=chain[0].code if chain else None,
        created_at=node.created_at,
        updated_at=node.updated_at,
        depth=len(chain),
        child_count=child_count,
        active_child_count=active_count,
        scope_membership_count=scope_count,
        allowed_actions=actions,
        **snapshot(node).model_dump(),
    )


def detail(db, principal, scope, node_id):
    require_capability(db, principal, scope, "organization.manage")
    node = load_node(db, scope, node_id)
    result = view(db, scope, node)
    require_capability(db, principal, scope, "organization.manage")
    return result


def list_nodes(
    db,
    principal,
    scope,
    search,
    kind,
    status,
    limit,
    offset,
    parent_for_kind,
    exclude_descendants_of,
):
    require_capability(db, principal, scope, "organization.manage")
    query = scoped(OrganizationNode, scope)
    if search:
        query = query.where(
            OrganizationNode.name.icontains(search, autoescape=True)
            | OrganizationNode.code.icontains(search, autoescape=True)
        )
    if kind:
        query = query.where(OrganizationNode.kind == kind)
    if status:
        query = query.where(OrganizationNode.active.is_(status == "ACTIVE"))
    if parent_for_kind:
        query = query.where(
            OrganizationNode.kind.in_(allowed_parents(parent_for_kind)),
            OrganizationNode.active.is_(True),
        )
    if exclude_descendants_of:
        load_node(db, scope, exclude_descendants_of)
        descendants = (
            scoped(OrganizationNode, scope)
            .with_only_columns(OrganizationNode.id)
            .where(OrganizationNode.id == exclude_descendants_of)
            .cte("descendants", recursive=True)
        )
        descendants = descendants.union(
            scoped(OrganizationNode, scope)
            .with_only_columns(OrganizationNode.id)
            .join(descendants, OrganizationNode.parent_id == descendants.c.id)
        )
        query = query.where(OrganizationNode.id.not_in(select(descendants.c.id)))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    # Contract-scoped recursive path orders the forest before bounded pagination.
    tree = (
        scoped(OrganizationNode, scope)
        .with_only_columns(
            OrganizationNode.id,
            array([cast(OrganizationNode.code, Text)]).label("path"),
        )
        .where(OrganizationNode.parent_id.is_(None))
        .cte("tree", recursive=True)
    )
    tree = tree.union_all(
        scoped(OrganizationNode, scope)
        .with_only_columns(
            OrganizationNode.id,
            tree.c.path.concat(array([cast(OrganizationNode.code, Text)])),
        )
        .join(tree, OrganizationNode.parent_id == tree.c.id)
    )
    rows = list(
        db.scalars(
            query.join(tree, OrganizationNode.id == tree.c.id)
            .order_by(tree.c.path, OrganizationNode.id)
            .limit(limit)
            .offset(offset)
        )
    )
    result = {
        "items": [view(db, scope, row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
    require_capability(db, principal, scope, "organization.manage")
    return result


def create_node(db, request, principal, scope, payload):
    require_capability(db, principal, scope, "organization.manage")
    validate_parent(db, scope, payload.kind, payload.parent_id, payload.active)
    # Revalidate time/session/context after the last parent lock, before any write.
    require_capability(db, principal, scope, "organization.manage")
    node = OrganizationNode(
        tenant_id=scope.tenant_id,
        contract_id=scope.contract_id,
        version=1,
        **payload.model_dump(),
    )
    db.add(node)
    try:
        db.flush()
    except IntegrityError:
        raise ApiError(
            409, "CODE_CONFLICT", "Código indisponível neste contrato."
        ) from None
    audit(
        db,
        request,
        principal,
        "organization.node.created",
        "organization_node",
        node.id,
        after=snapshot(node),
        scope=scope,
    )
    result = view(db, scope, node)
    require_capability(db, principal, scope, "organization.manage")
    return result


def patch_node(db, request, principal, scope, node_id, payload):
    require_capability(db, principal, scope, "organization.manage")
    node = load_node(db, scope, node_id)
    parent_id = (
        payload.parent_id if "parent_id" in payload.model_fields_set else node.parent_id
    )
    active = payload.active if "active" in payload.model_fields_set else node.active
    validate_parent(db, scope, node.kind, parent_id, active, node.id)
    _, active_count, scope_count = counts(db, scope, node.id)
    require_capability(db, principal, scope, "organization.manage")
    if node.version != payload.expected_version:
        raise ApiError(
            409, "VERSION_CONFLICT", "Registro alterado. Atualize antes de confirmar."
        )
    if "code" in payload.model_fields_set and payload.code.strip().upper() != node.code:
        raise ApiError(422, "IMMUTABLE_CODE", "Código não pode ser alterado.")
    if not active and (active_count or scope_count):
        raise ApiError(
            409, "ACTIVE_DEPENDENCIES", "Existem filhos ou escopos ativos dependentes."
        )
    before = snapshot(node)
    if "name" in payload.model_fields_set:
        node.name = payload.name
    node.parent_id, node.active = parent_id, active
    node.version += 1
    db.flush()
    audit(
        db,
        request,
        principal,
        "organization.node.updated",
        "organization_node",
        node.id,
        before=before,
        after=snapshot(node),
        scope=scope,
    )
    result = view(db, scope, node)
    require_capability(db, principal, scope, "organization.manage")
    return result


def unit_scope_view(db, scope, member):
    ids = list(
        db.scalars(
            scoped(MembershipUnitScope, scope)
            .with_only_columns(MembershipUnitScope.node_id)
            .where(
                MembershipUnitScope.membership_id == member.id,
                MembershipUnitScope.active.is_(True),
            )
            .order_by(MembershipUnitScope.node_id)
        )
    )
    return {"membership_id": member.id, "node_ids": ids, "version": member.version}


def read_unit_scope(db, principal, scope, member_id):
    require_capability(db, principal, scope, "organization.manage")
    member = target_member(db, scope, member_id)
    result = unit_scope_view(db, scope, member)
    require_capability(db, principal, scope, "organization.manage")
    return result


def set_unit_scope(db, request, principal, scope, member_id, payload):
    require_capability(db, principal, scope, "organization.manage")
    member = target_member(db, scope, member_id)
    desired = set(payload.node_ids)
    for node_id in sorted(desired):
        node = load_node(db, scope, node_id)
        if not node.active:
            raise ApiError(409, "INACTIVE_UNIT", "Unidade deve estar ativa.")
        validate_parent(db, scope, node.kind, node.parent_id, True, node.id)
    rows = list(
        db.scalars(
            scoped(MembershipUnitScope, scope)
            .where(MembershipUnitScope.membership_id == member.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    fresh, *_ = revalidate(db, principal, scope)
    require_capability(db, fresh, scope, "organization.manage")
    if member.version != payload.expected_version:
        raise ApiError(
            409, "VERSION_CONFLICT", "Vínculo alterado. Atualize antes de confirmar."
        )
    if desired and (not member.active or member.blocked or member.invitation_pending):
        raise ApiError(409, "MEMBERSHIP_UNAVAILABLE", "Vínculo indisponível.")
    before = MembershipUnitScopeSnapshot(
        node_ids=unit_scope_view(db, scope, member)["node_ids"], version=member.version
    )
    present = {row.node_id for row in rows}
    for row in rows:
        row.active = row.node_id in desired
    for node_id in desired - present:
        db.add(
            MembershipUnitScope(
                tenant_id=scope.tenant_id,
                contract_id=scope.contract_id,
                membership_id=member.id,
                node_id=node_id,
                active=True,
            )
        )
    member.version += 1
    revoke_contexts(db, scope, [member.user_id])
    db.flush()
    result = unit_scope_view(db, scope, member)
    audit(
        db,
        request,
        fresh,
        "membership.unit_scope.updated",
        "membership",
        member.id,
        before=before,
        after=MembershipUnitScopeSnapshot(
            node_ids=result["node_ids"], version=member.version
        ),
        scope=scope,
    )
    require_capability(db, fresh, scope, "organization.manage")
    return result

"""Controlled tests only. Never imported by normal application startup."""

from uuid import UUID, uuid4

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.schemas import OrganizationNodeSnapshot
from app.grants.registry import MaintenanceAction, MaintenanceActionRegistry
from app.maintenance.registry import MaintenanceHandler
from app.maintenance.schemas import ClosedModel
from app.organization.models import OrganizationNode


class RenameInput(ClosedModel):
    name: str = Field(min_length=1, max_length=200)


def load(db, scope, entity_id, *, lock=False):
    query = select(OrganizationNode).where(
        OrganizationNode.id == entity_id,
        OrganizationNode.tenant_id == scope.tenant_id,
        OrganizationNode.contract_id == scope.contract_id,
        OrganizationNode.active.is_(True),
    )
    if lock:
        query = query.with_for_update()
    return db.scalar(query.execution_options(populate_existing=True))


def snapshot(entity):
    return OrganizationNodeSnapshot(
        **{
            key: getattr(entity, key)
            for key in ("kind", "name", "code", "parent_id", "active", "version")
        }
    )


def preview(entity, command):
    return snapshot(entity).model_copy(
        update={"name": command.name, "version": entity.version + 1}
    )


def apply(entity, command):
    entity.name = command.name
    entity.version += 1


def reprocess(db, entity, source):
    entity.name = "Reprocessed controlled node"
    entity.version += 1


def register_fixture_action(app):
    handler = MaintenanceHandler(
        RenameInput,
        OrganizationNodeSnapshot,
        load,
        preview,
        apply,
        "Renomear entidade controlada",
        ("Nome atualizado",),
        reprocess=reprocess,
        foundation_action=True,
        diagnostics_safe=True,
    )
    action = MaintenanceAction(
        "FIXTURE_NODE_RENAME",
        "Renomear entidade controlada",
        "organization_node",
        "maintenance.authorize",
        None,
        lambda db, scope, target: (
            target is not None and load(db, scope, target) is not None
        ),
        lambda *args: True,
        handler,
    )
    app.state.maintenance_registry = MaintenanceActionRegistry([action])
    return action


def seed_fixture_run(runtime, identifiers, entity_id, requested_by):
    from app.maintenance.models import ProcessingRun
    from app.tenancy.contexts import now
    from app.tenancy.models import AccessContext

    context_id = (
        UUID(str(requested_by["context_id"]))
        if isinstance(requested_by, dict)
        else UUID(str(requested_by))
    )
    with Session(runtime) as db, db.begin():
        context = db.get(AccessContext, context_id)
        run = ProcessingRun(
            id=uuid4(),
            tenant_id=identifiers["tenant_a"],
            contract_id=identifiers["contract_a"],
            action_code="FIXTURE_NODE_RENAME",
            entity_type="organization_node",
            entity_id=entity_id,
            operator_id=context.actor_id,
            operator_session_id=context.session_id,
            operator_role="PLATFORM_ADMIN",
            context_id=context.id,
            request_id=uuid4(),
            status="FAILED",
            result_code="HANDLER_FAILED",
            message_code="HANDLER_FAILED",
            classification="STANDARD",
            version=1,
            created_at=now(db),
            started_at=now(db),
            finished_at=now(db),
        )
        db.add(run)
        db.flush()
        return run.id

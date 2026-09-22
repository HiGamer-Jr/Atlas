from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.audit.schemas import AuditInput
from app.tenancy.models import Contract


def append_event(db: Session, event: AuditInput) -> UUID:
    values = event.model_dump(exclude={"before", "after"})
    environment = None
    if event.contract_id is not None:
        environment = db.scalar(
            select(Contract.environment).where(
                Contract.id == event.contract_id, Contract.tenant_id == event.tenant_id
            )
        )
        if environment is None:
            raise ValueError("Audit contract is outside the supplied tenant")
    record = AuditEvent(
        **values,
        environment=environment,
        before_state=event.before.model_dump(mode="json") if event.before else None,
        after_state=event.after.model_dump(mode="json") if event.after else None,
    )
    db.add(record)
    db.flush()
    return record.id

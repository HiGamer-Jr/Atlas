from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.datahub.models import DataHubDemand, DataHubRecord, DataHubStockPosition
from app.datahub.types import DatasetCode
from app.tenancy.schemas import AccessScope


def existing_records(
    db: Session,
    scope: AccessScope,
    dataset: DatasetCode,
    keys: Iterable[str],
    units: tuple[UUID, ...],
) -> dict[str, DataHubRecord]:
    query = select(DataHubRecord).where(
        DataHubRecord.tenant_id == scope.tenant_id,
        DataHubRecord.contract_id == scope.contract_id,
        DataHubRecord.dataset_code == dataset,
        DataHubRecord.business_key.in_(set(keys)),
    )
    detail = {
        DatasetCode.DEMANDS: DataHubDemand,
        DatasetCode.STOCK_POSITIONS: DataHubStockPosition,
    }.get(dataset)
    if detail is not None:
        query = query.join(detail, detail.record_id == DataHubRecord.id).where(
            detail.unit_id.in_(units)
        )
    return {row.business_key: row for row in db.scalars(query)}

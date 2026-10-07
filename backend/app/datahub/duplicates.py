"""Contextual identity and deterministic comparison; no overwrite policy."""

import hashlib
import json
from uuid import UUID

from app.datahub.schemas import NormalizedPayload
from app.datahub.types import DatasetCode


def canonical_payload(payload: NormalizedPayload, unit_id: UUID | None = None) -> dict:
    values = payload.model_dump(mode="json")
    if "unidade_codigo" in values and unit_id is not None:
        values.pop("unidade_codigo")
        values["unit_id"] = str(unit_id)
    return values


def fingerprint(
    dataset: DatasetCode, payload: NormalizedPayload, unit_id: UUID | None = None
) -> str:
    values = {
        "dataset": dataset,
        "schema_version": 1,
        "payload": canonical_payload(payload, unit_id),
    }
    return hashlib.sha256(
        json.dumps(
            values, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def business_key(
    dataset: DatasetCode, payload: NormalizedPayload, unit_id: UUID | None = None
) -> str:
    if dataset == DatasetCode.STOCK_POSITIONS:
        if unit_id is None:
            raise ValueError("Stock identity requires a resolved unit")
        return (
            f"{payload.produto_codigo}:{unit_id}:{payload.data_referencia.isoformat()}"
        )
    return payload.codigo

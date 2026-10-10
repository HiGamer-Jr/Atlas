"""Receipts preserve the complete original response within the request transaction."""

import hashlib
import json
from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select

from app.core.errors import ApiError
from app.procurement.requests import policy, queries
from app.procurement.requests.models import RequestCommandReceipt
from app.procurement.requests.schemas import RequestView


def canonical_digest(payload) -> str:
    value = (
        payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    )
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def run_idempotent(
    db,
    principal,
    scope,
    route: str,
    target_id: UUID | None,
    key: UUID,
    payload_digest: str,
    operation: Callable[[], RequestView],
) -> RequestView:
    # Context revalidation holds contract/user locks, serializing same-scope receipts,
    # including creation where target_id is NULL (NULLS NOT DISTINCT unique key).
    policy.tenant_actor(db, principal, scope)
    receipt = db.scalar(
        select(RequestCommandReceipt)
        .where(
            RequestCommandReceipt.tenant_id == scope.tenant_id,
            RequestCommandReceipt.contract_id == scope.contract_id,
            RequestCommandReceipt.actor_user_id == principal.user_id,
            RequestCommandReceipt.access_context_id == scope.id,
            RequestCommandReceipt.route == route,
            RequestCommandReceipt.target_id == target_id,
            RequestCommandReceipt.idempotency_key == key,
        )
        .execution_options(populate_existing=True)
    )
    if receipt:
        row = queries.read_row(db, principal, scope, receipt.request_id)
        if receipt.digest != payload_digest:
            raise ApiError(
                409, "IDEMPOTENCY_CONFLICT", "Chave já utilizada com outros dados."
            )
        # Caller reauthorizes the current action before entering. Read authorization
        # is fresh, but no original response is recomputed and no operation reruns.
        policy.authorize_request_read(db, principal, scope, row)
        return RequestView.model_validate(receipt.result)
    result = operation()
    db.add(
        RequestCommandReceipt(
            tenant_id=scope.tenant_id,
            contract_id=scope.contract_id,
            request_id=result.id,
            actor_user_id=principal.user_id,
            access_context_id=scope.id,
            auth_session_id=principal.session_id,
            route=route,
            target_id=target_id,
            idempotency_key=key,
            digest=payload_digest,
            result=result.model_dump(mode="json"),
            response_status=201 if target_id is None else 200,
        )
    )
    db.flush()
    return result

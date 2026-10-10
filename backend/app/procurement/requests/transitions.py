"""Closed workflow table. The approval mode comes only from server policy."""

from typing import Literal

from app.core.errors import ApiError
from app.procurement.requests.schemas import ApprovalMode, RequestStatus

RequestAction = Literal[
    "submit",
    "start-triage",
    "request-approval",
    "approve",
    "reject",
    "start-fulfillment",
    "cancel",
    "close",
]
TRANSITIONS = {
    ("DRAFT", "submit"): "SUBMITTED",
    ("SUBMITTED", "start-triage"): "IN_TRIAGE",
    ("IN_TRIAGE", "request-approval"): "AWAITING_APPROVAL",
    ("AWAITING_APPROVAL", "approve"): "APPROVED",
    ("IN_TRIAGE", "reject"): "REJECTED",
    ("AWAITING_APPROVAL", "reject"): "REJECTED",
    ("APPROVED", "start-fulfillment"): "IN_FULFILLMENT",
    ("FULFILLED", "close"): "CLOSED",
    **{
        (state, "cancel"): "CANCELLED"
        for state in (
            "DRAFT",
            "SUBMITTED",
            "IN_TRIAGE",
            "AWAITING_APPROVAL",
            "APPROVED",
            "IN_FULFILLMENT",
        )
    },
}


def transition_target(
    status: RequestStatus,
    command: RequestAction,
    approval_mode: ApprovalMode = "REQUIRED",
) -> RequestStatus:
    if approval_mode not in {"REQUIRED", "NOT_REQUIRED"}:
        raise ApiError(409, "INVALID_POLICY", "Política indisponível.")
    target = TRANSITIONS.get((status, command))
    if target is None:
        raise ApiError(409, "INVALID_TRANSITION", "Ação indisponível no estado atual.")
    if command == "request-approval" and approval_mode == "NOT_REQUIRED":
        return "APPROVED"
    return target

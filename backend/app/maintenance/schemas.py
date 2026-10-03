from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator

from app.grants.schemas import GrantStart


class ClosedModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        hide_input_in_errors=True,
        str_strip_whitespace=True,
        frozen=True,
    )


class ReasonCommand(ClosedModel):
    reason: str = Field(min_length=3, max_length=1000)
    reference: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("reason", "reference", mode="before")
    @classmethod
    def plain_text(cls, value):
        return GrantStart.plain_text(value)


class CorrectionCommand(ReasonCommand):
    action_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")
    entity_id: UUID
    expected_version: int = Field(ge=1, strict=True)


def command_schema(action, *, apply=False):
    fields = {"proposed_input": (action.handler.input_type, ...)}
    if apply:
        fields["preview_receipt"] = (str, Field(min_length=1, max_length=256))
    return create_model(
        action.action_code + ("Apply" if apply else "Preview"),
        __base__=CorrectionCommand,
        **fields,
    )


class CorrectionResult(ClosedModel):
    audit_event_id: UUID
    action_code: str
    entity_id: UUID
    version: int


class ReprocessCommand(ReasonCommand):
    idempotency_key: str = Field(
        min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_:-]+$"
    )
    expected_version: int = Field(ge=1, strict=True)


ProcessingStatus = Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED", "UNKNOWN"]
ResultCode = Literal["NONE", "COMPLETED", "HANDLER_FAILED", "NOT_ELIGIBLE"]


class ProcessingView(ClosedModel):
    id: UUID
    action_code: str
    status: ProcessingStatus
    result_code: ResultCode
    message_code: ResultCode
    request_id: UUID
    entity_id: UUID | None
    source_run_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    version: int
    can_reprocess: bool


class ProcessingPage(ClosedModel):
    items: list[ProcessingView]
    total: int
    limit: int
    offset: int

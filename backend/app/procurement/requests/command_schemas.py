"""Client commands contain candidates and intent, never server authority."""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated
from uuid import UUID

from pydantic import BeforeValidator, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.procurement.requests.schemas import (
    ApprovalMode,
    ClosedSchema,
    Priority,
    UomCode,
)


def exact_quantity(value):
    if not isinstance(value, (str, Decimal)):
        raise ValueError("Quantity must be an exact decimal string.")  # noqa: TRY004 -- Pydantic converts ValueError into a 422 validation error.
    try:
        quantity = Decimal(value)
    except InvalidOperation:
        raise ValueError("Invalid decimal quantity.") from None
    if not quantity.is_finite() or quantity <= 0 or quantity >= Decimal(1000000000000):
        raise ValueError("Quantity outside Numeric(18,6) range.")
    if quantity != quantity.quantize(Decimal("0.000001")):
        raise ValueError("Quantity supports at most six decimal places.")
    return quantity


ExactQuantity = Annotated[Decimal, BeforeValidator(exact_quantity)]


class RequestItemInput(ClosedSchema):
    id: UUID | None = None
    description: str = Field(min_length=1, max_length=2000)
    specification: str = Field(default="", max_length=4000)
    requested_quantity: ExactQuantity
    uom_code: UomCode

    @model_validator(mode="after")
    def package_content(self):
        if self.uom_code in ("CX", "PCT") and not self.specification:
            raise ValueError("Package content specification is required.")
        return self


class UnavailableReferences(ClosedSchema):
    project_id: None = None
    cost_center_id: None = None

    @field_validator("project_id", "cost_center_id", mode="before")
    @classmethod
    def unavailable_reference(cls, value):
        if value is not None:
            raise PydanticCustomError(
                "REFERENCE_DOMAIN_UNAVAILABLE", "Reference domain unavailable."
            )
        return value


class RequestCreate(UnavailableReferences):
    requesting_node_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    justification: str = Field(default="", max_length=4000)
    priority: Priority = "NORMAL"
    needed_on: date | None = None
    notes: str = Field(default="", max_length=4000)
    items: list[RequestItemInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def new_items(self):
        if any(item.id is not None for item in self.items):
            raise ValueError("New request items cannot specify server IDs.")
        return self


class VersionCommand(ClosedSchema):
    expected_version: int = Field(ge=1, strict=True)


class DraftPatch(UnavailableReferences, VersionCommand):
    requesting_node_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    justification: str | None = Field(default=None, max_length=4000)
    priority: Priority | None = None
    needed_on: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    items: list[RequestItemInput] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def non_nullable(self):
        for field in (
            "requesting_node_id",
            "title",
            "description",
            "justification",
            "priority",
            "notes",
            "items",
        ):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError("Field cannot be null.")
        if self.items:
            ids = [item.id for item in self.items if item.id is not None]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate item IDs.")
        return self


class ReasonCommand(VersionCommand):
    reason: str = Field(min_length=1, max_length=2000)


class AssignmentCommand(VersionCommand):
    buyer_membership_id: UUID


class ApprovalPolicyPatch(ClosedSchema):
    expected_version: int = Field(ge=0, strict=True)
    approval_mode: ApprovalMode
    reason: str = Field(min_length=1, max_length=2000)


class FulfillmentCommand(ReasonCommand):
    item_id: UUID
    quantity: ExactQuantity
    evidence: str = Field(min_length=1, max_length=4000)


class NoteCommand(VersionCommand):
    text: str = Field(min_length=1, max_length=4000)

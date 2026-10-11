from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.partners.capabilities import PARTNER_CAPABILITIES

PartnerCategory = Literal[
    "TRADE", "CUSTOMS_BROKER", "LOGISTICS_OPERATOR", "FREIGHT_FORWARDER", "OTHER"
]


class Input(BaseModel):
    model_config = ConfigDict(
        extra="forbid", hide_input_in_errors=True, str_strip_whitespace=True
    )


class PartnerOrganizationCreate(Input):
    name: str = Field(min_length=1, max_length=200)
    category: PartnerCategory
    expected_version: int = Field(default=0, ge=0, le=0, strict=True)


class PermissionsInput(Input):
    permissions: list[str] = Field(max_length=10)

    @field_validator("permissions")
    @classmethod
    def closed_permissions(cls, values):
        if len(values) != len(set(values)) or not set(values) <= PARTNER_CAPABILITIES:
            raise ValueError("Only unique known partner capabilities are accepted")
        return sorted(values)


class PartnerMembershipCreate(PermissionsInput):
    organization_id: UUID
    user_id: UUID
    expected_version: int = Field(default=0, ge=0, le=0, strict=True)


class PartnerMembershipReplace(PermissionsInput):
    active: StrictBool
    blocked: StrictBool
    expected_version: int = Field(gt=0, strict=True)
    reason: str = Field(min_length=1, max_length=2000)

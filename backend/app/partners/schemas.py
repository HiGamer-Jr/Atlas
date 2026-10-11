from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

from app.identity.mailboxes import single_mailbox
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


class PartnerAvailability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    status: Literal["DOMAIN_UNAVAILABLE"] = "DOMAIN_UNAVAILABLE"
    code: Literal["PARTNER_DOMAIN_UNAVAILABLE"] = "PARTNER_DOMAIN_UNAVAILABLE"


class PartnerContextInput(Input):
    membership_id: UUID
    client_link_id: UUID


class PartnerRecipientInput(Input):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return single_mailbox(value)


class PartnerMembershipInput(PermissionsInput):
    user_id: UUID | None = None
    recipient: PartnerRecipientInput | None = None
    expected_version: int = Field(default=0, ge=0, le=0, strict=True)

    @model_validator(mode="after")
    def exclusive_recipient(self):
        if (self.user_id is None) == (self.recipient is None):
            raise ValueError("Supply exactly one recipient target")
        return self


class PartnerInviteInput(Input):
    pass


class PartnerOrganizationView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    id: UUID
    name: str
    category: PartnerCategory
    active: bool
    version: int


class PartnerMembershipView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    organization_id: UUID
    user_id: UUID
    active: bool
    blocked: bool
    invitation_pending: bool
    version: int
    permissions: list[str]


class PartnerInviteView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["accepted"] = "accepted"
    membership_id: UUID
    version: int

from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, StrictBool, field_validator, model_validator

from app.identity.mailboxes import single_mailbox
from app.identity.schemas import Input


class RecoveryInput(Input):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return single_mailbox(value)


class TokenInput(Input):
    token: SecretStr = Field(min_length=1, max_length=128)


class ValidateTokenInput(TokenInput):
    purpose: Literal["INVITE", "PASSWORD_RESET"]


class ResetInput(TokenInput):
    new_password: SecretStr = Field(min_length=1, max_length=1024)


class AcceptInput(TokenInput):
    new_password: SecretStr | None = Field(default=None, max_length=1024)


class InviteInput(RecoveryInput):
    display_name: str = Field(min_length=1, max_length=200)
    role_id: UUID


class MembershipStatusInput(Input):
    active: StrictBool | None = None
    blocked: StrictBool | None = None
    expected_version: int = Field(ge=1)

    @model_validator(mode="after")
    def explicit_status(self):
        fields = self.model_fields_set - {"expected_version"}
        if not fields or any(getattr(self, name) is None for name in fields):
            raise ValueError("Supply explicit status")
        return self


class OperatorInviteConfirmation(RecoveryInput):
    role: Literal["PLATFORM_ADMIN", "PLATFORM_SUPPORT"]


class OperatorInviteInput(RecoveryInput):
    display_name: str = Field(min_length=1, max_length=200)
    role: Literal["PLATFORM_ADMIN", "PLATFORM_SUPPORT"]
    password: SecretStr = Field(min_length=1, max_length=1024)
    confirmation: OperatorInviteConfirmation

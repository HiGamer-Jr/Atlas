from dataclasses import dataclass
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StrictBool,
    field_validator,
    model_validator,
)

from app.audit.schemas import PlatformRole


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    session_id: UUID
    platform_role: PlatformRole | None


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class PasswordInput(Input):
    password: SecretStr = Field(min_length=1, max_length=1024)


class LoginInput(PasswordInput):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        value = value.strip().lower()
        if "@" not in value or any(char.isspace() for char in value):
            raise ValueError("Invalid email")
        return value


class IdentityView(BaseModel):
    user_id: UUID
    display_name: str
    platform_role: PlatformRole | None
    capabilities: list[str] = Field(default_factory=list)


class CsrfView(BaseModel):
    token: str


class RoleConfirmation(Input):
    target_user_id: UUID
    target_role: PlatformRole


class OperatorRoleInput(PasswordInput):
    role: PlatformRole
    confirmation: RoleConfirmation


class OperatorStatusInput(Input):
    active: StrictBool | None = None
    blocked: StrictBool | None = None

    @model_validator(mode="after")
    def explicit_status(self):
        if not self.model_fields_set or any(
            getattr(self, name) is None for name in self.model_fields_set
        ):
            raise ValueError("Supply explicit active/blocked booleans")
        return self


class OperatorView(BaseModel):
    user_id: UUID
    platform_role: PlatformRole | None
    active: bool
    blocked: bool

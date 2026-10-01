from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StrictBool, field_validator, model_validator

from app.platform.capabilities import CATALOG
from app.tenancy.schemas import Input

Classification = Literal["STANDARD", "ADMINISTRATIVE", "FINANCIAL_FISCAL", "SENSITIVE"]
PermissionCode = Annotated[str, Field(max_length=100)]


class RoleFields(Input):
    @field_validator("permissions", check_fields=False)
    @classmethod
    def known_permissions(cls, values):
        if values is not None and (
            len(values) != len(set(values))
            or any(
                value not in CATALOG or not CATALOG[value].tenant_role
                for value in values
            )
        ):
            raise ValueError("Only known tenant capabilities are accepted")
        return sorted(values) if values is not None else None

    @field_validator("name", check_fields=False)
    @classmethod
    def reserved_names(cls, value):
        if value and value.upper() in {
            "PLATFORM_ADMIN",
            "PLATFORM_SUPPORT",
            "ADMINISTRADOR HIATLAS",
            "SUPORTE HIATLAS",
        }:
            raise ValueError("Internal platform roles are not tenant profiles")
        return value


class RoleCreate(RoleFields):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Z][A-Z0-9_]+$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    classification: Classification = "STANDARD"
    support_assignable: StrictBool = False
    active: StrictBool = True
    permissions: list[PermissionCode] = Field(default_factory=list, max_length=100)

    @field_validator("code")
    @classmethod
    def reserved_code(cls, value):
        if value.startswith("PLATFORM_"):
            raise ValueError("Internal platform role")
        return value


class RolePatch(RoleFields):
    expected_version: int = Field(gt=0, strict=True)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    classification: Classification | None = None
    support_assignable: StrictBool | None = None
    active: StrictBool | None = None
    permissions: list[PermissionCode] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def explicit_changes(self):
        changes = self.model_fields_set - {"expected_version"}
        if not changes or any(getattr(self, name) is None for name in changes):
            raise ValueError("Supply explicit non-null changes")
        return self


class RoleAssignment(Input):
    role_id: UUID
    expected_version: int = Field(gt=0, strict=True)


class RoleView(BaseModel):
    description: str = ""
    member_count: int = 0
    id: UUID
    code: str
    name: str
    classification: Classification
    support_assignable: bool
    sensitivity_locked: bool
    support_eligible: bool
    active: bool
    permissions: list[str]
    version: int


class RoleList(BaseModel):
    items: list[RoleView]
    total: int
    limit: int
    offset: int

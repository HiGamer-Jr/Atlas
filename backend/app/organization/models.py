from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.columns import Timestamps


class OrganizationNode(Timestamps, Base):
    __tablename__ = "organization_nodes"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "contract_id", "id", name="uq_organization_node_scope"
        ),
        UniqueConstraint(
            "tenant_id", "contract_id", "code", name="uq_organization_node_code"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id"],
            ["contracts.tenant_id", "contracts.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "parent_id"],
            [
                "organization_nodes.tenant_id",
                "organization_nodes.contract_id",
                "organization_nodes.id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "kind IN ('COMPANY','BRANCH','UNIT','STORE','DISTRIBUTION_CENTER','WAREHOUSE','OFFICE','WORKSITE')",
            name="ck_organization_node_kind",
        ),
        CheckConstraint(
            "parent_id IS NULL OR parent_id <> id", name="ck_organization_node_self"
        ),
        CheckConstraint(
            "kind <> 'COMPANY' OR parent_id IS NULL",
            name="ck_organization_company_root",
        ),
        CheckConstraint("length(btrim(name)) > 0", name="ck_organization_node_name"),
        CheckConstraint(
            "code ~ '^[A-Z][A-Z0-9_-]{0,63}$'", name="ck_organization_node_code"
        ),
        CheckConstraint("version > 0", name="ck_organization_node_version"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    contract_id: Mapped[UUID] = mapped_column(index=True)
    parent_id: Mapped[UUID | None] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class ContractModule(Timestamps, Base):
    __tablename__ = "contract_modules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "contract_id", "code", name="uq_contract_module_code"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id"],
            ["contracts.tenant_id", "contracts.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "code IN ('PROCUREMENT','COMEX','INVENTORY','FINANCE','PROJECTS','DATAHUB')",
            name="ck_contract_module_code",
        ),
        CheckConstraint("NOT active OR contracted", name="ck_contract_module_active"),
        CheckConstraint("version > 0", name="ck_contract_module_version"),
    )
    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(index=True)
    contract_id: Mapped[UUID] = mapped_column(index=True)
    code: Mapped[str] = mapped_column(String(32))
    contracted: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))


class MembershipUnitScope(Timestamps, Base):
    __tablename__ = "membership_unit_scopes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "membership_id"],
            ["memberships.tenant_id", "memberships.contract_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "contract_id", "node_id"],
            [
                "organization_nodes.tenant_id",
                "organization_nodes.contract_id",
                "organization_nodes.id",
            ],
            ondelete="RESTRICT",
        ),
    )
    membership_id: Mapped[UUID] = mapped_column(primary_key=True)
    node_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    contract_id: Mapped[UUID]
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

"""Contract organization, module catalogue state and explicit membership unit scopes."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def guard():
    connection = op.get_bind()
    runtime = op.get_context().config.attributes.get("runtime_role")
    if (
        not runtime
        or runtime == connection.execute(sa.text("SELECT current_user")).scalar_one()
    ):
        raise RuntimeError("Distinct runtime role required")
    flags = connection.execute(
        sa.text("""
        SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls
          OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member=pg_roles.oid)
        FROM pg_roles WHERE rolname=:runtime
    """),
        {"runtime": runtime},
    ).scalar_one_or_none()
    owner_safe = connection.execute(
        sa.text("""
        SELECT NOT r.rolsuper AND d.datdba=r.oid
        FROM pg_roles r CROSS JOIN pg_database d
        WHERE r.rolname=current_user AND d.datname=current_database()
    """)
    ).scalar_one()
    if flags is None or flags or not owner_safe:
        raise RuntimeError("Migration requires safe distinct owner/runtime roles")
    return connection.dialect.identifier_preparer.quote_identifier(runtime)


def timestamps():
    return [
        sa.Column(
            name,
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
        for name in ("created_at", "updated_at")
    ]


def contract_fk():
    return sa.ForeignKeyConstraint(
        ["tenant_id", "contract_id"],
        ["contracts.tenant_id", "contracts.id"],
        ondelete="RESTRICT",
    )


def upgrade():
    runtime = guard()
    op.create_unique_constraint(
        "uq_membership_scope", "memberships", ["tenant_id", "contract_id", "id"]
    )
    op.create_table(
        "organization_nodes",
        sa.Column(
            "id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("tenant_id", UUID(), nullable=False),
        sa.Column("contract_id", UUID(), nullable=False),
        sa.Column("parent_id", UUID()),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        *timestamps(),
        contract_fk(),
        sa.UniqueConstraint(
            "tenant_id", "contract_id", "id", name="uq_organization_node_scope"
        ),
        sa.UniqueConstraint(
            "tenant_id", "contract_id", "code", name="uq_organization_node_code"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "contract_id", "parent_id"],
            [
                "organization_nodes.tenant_id",
                "organization_nodes.contract_id",
                "organization_nodes.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "kind IN ('COMPANY','BRANCH','UNIT','STORE','DISTRIBUTION_CENTER','WAREHOUSE','OFFICE','WORKSITE')",
            name="ck_organization_node_kind",
        ),
        sa.CheckConstraint(
            "parent_id IS NULL OR parent_id <> id", name="ck_organization_node_self"
        ),
        sa.CheckConstraint(
            "kind <> 'COMPANY' OR parent_id IS NULL",
            name="ck_organization_company_root",
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_organization_node_name"),
        sa.CheckConstraint(
            "code ~ '^[A-Z][A-Z0-9_-]{0,63}$'", name="ck_organization_node_code"
        ),
        sa.CheckConstraint("version > 0", name="ck_organization_node_version"),
    )
    for name in ("tenant_id", "contract_id", "parent_id"):
        op.create_index("ix_organization_nodes_" + name, "organization_nodes", [name])
    op.create_table(
        "contract_modules",
        sa.Column(
            "id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("tenant_id", UUID(), nullable=False),
        sa.Column("contract_id", UUID(), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column(
            "contracted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        *timestamps(),
        contract_fk(),
        sa.UniqueConstraint(
            "tenant_id", "contract_id", "code", name="uq_contract_module_code"
        ),
        sa.CheckConstraint(
            "code IN ('PROCUREMENT','COMEX','INVENTORY','FINANCE','PROJECTS','DATAHUB')",
            name="ck_contract_module_code",
        ),
        sa.CheckConstraint(
            "NOT active OR contracted", name="ck_contract_module_active"
        ),
        sa.CheckConstraint("version > 0", name="ck_contract_module_version"),
    )
    for name in ("tenant_id", "contract_id"):
        op.create_index("ix_contract_modules_" + name, "contract_modules", [name])
    op.create_table(
        "membership_unit_scopes",
        sa.Column("membership_id", UUID(), primary_key=True),
        sa.Column("node_id", UUID(), primary_key=True),
        sa.Column("tenant_id", UUID(), nullable=False),
        sa.Column("contract_id", UUID(), nullable=False),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["tenant_id", "contract_id", "membership_id"],
            ["memberships.tenant_id", "memberships.contract_id", "memberships.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "contract_id", "node_id"],
            [
                "organization_nodes.tenant_id",
                "organization_nodes.contract_id",
                "organization_nodes.id",
            ],
            ondelete="RESTRICT",
        ),
    )
    for table in ("organization_nodes", "contract_modules", "membership_unit_scopes"):
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, {runtime}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{table} TO {runtime}")


def downgrade():
    guard()
    op.drop_table("membership_unit_scopes")
    op.drop_table("contract_modules")
    op.drop_table("organization_nodes")
    op.drop_constraint("uq_membership_scope", "memberships", type_="unique")

"""Contract-bound roles, memberships and session-owned access contexts."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def scope_columns():
    return [
        sa.Column("tenant_id", pg.UUID(), nullable=False),
        sa.Column("contract_id", pg.UUID(), nullable=False),
    ]


def scope_fk():
    return sa.ForeignKeyConstraint(
        ["tenant_id", "contract_id"],
        ["contracts.tenant_id", "contracts.id"],
        ondelete="RESTRICT",
    )


def role_fk():
    return sa.ForeignKeyConstraint(
        ["tenant_id", "contract_id", "role_id"],
        ["tenant_roles.tenant_id", "tenant_roles.contract_id", "tenant_roles.id"],
        ondelete="RESTRICT",
    )


def upgrade():
    conn = op.get_bind()
    runtime = op.get_context().config.attributes.get("runtime_role")
    safe = conn.execute(
        sa.text("""
        SELECT NOT r.rolsuper AND NOT r.rolcreatedb AND NOT r.rolcreaterole AND NOT r.rolbypassrls
          AND NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid)
          AND r.rolname<>current_user
        FROM pg_roles r WHERE rolname=:role
    """),
        {"role": runtime},
    ).scalar_one_or_none()
    owner = conn.execute(
        sa.text("""
        SELECT NOT r.rolsuper AND r.oid=d.datdba FROM pg_roles r, pg_database d
        WHERE r.rolname=current_user AND d.datname=current_database()
    """)
    ).scalar_one()
    if not safe or not owner:
        raise RuntimeError("Migration requires safe distinct owner/runtime roles")
    op.create_unique_constraint(
        "uq_auth_session_actor", "auth_sessions", ["id", "user_id"]
    )
    op.create_table(
        "tenant_roles",
        sa.Column(
            "id",
            pg.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        *scope_columns(),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "classification", sa.String(32), nullable=False, server_default="STANDARD"
        ),
        sa.Column(
            "support_assignable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "sensitivity_locked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *timestamps(),
        scope_fk(),
        sa.UniqueConstraint(
            "tenant_id", "contract_id", "id", name="uq_tenant_role_scope"
        ),
        sa.UniqueConstraint("contract_id", "code", name="uq_tenant_role_code"),
        sa.CheckConstraint(
            "classification IN ('STANDARD','ADMINISTRATIVE','FINANCIAL_FISCAL','SENSITIVE')",
            name="ck_role_classification",
        ),
        sa.CheckConstraint(
            "code ~ '^[A-Z][A-Z0-9_]{1,63}$' AND left(code,9) <> 'PLATFORM_'",
            name="ck_tenant_role_code",
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_tenant_role_name"),
        sa.CheckConstraint("version > 0", name="ck_tenant_role_version"),
    )
    op.create_table(
        "tenant_role_permissions",
        sa.Column("role_id", pg.UUID(), primary_key=True),
        sa.Column("capability", sa.String(100), primary_key=True),
        *scope_columns(),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        role_fk(),
        sa.CheckConstraint(
            "capability IN ('memberships.read','roles.read','roles.manage','finance.read','fiscal.read')",
            name="ck_tenant_capability",
        ),
    )
    op.create_table(
        "memberships",
        sa.Column(
            "id",
            pg.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            pg.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        *scope_columns(),
        sa.Column("role_id", pg.UUID(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *timestamps(),
        scope_fk(),
        role_fk(),
        sa.UniqueConstraint(
            "user_id", "tenant_id", "contract_id", name="uq_membership_user_scope"
        ),
        sa.CheckConstraint("version > 0", name="ck_membership_version"),
    )
    op.create_table(
        "access_contexts",
        sa.Column(
            "id",
            pg.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("session_id", pg.UUID(), nullable=False),
        sa.Column("actor_id", pg.UUID(), nullable=False),
        *scope_columns(),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        scope_fk(),
        sa.ForeignKeyConstraint(
            ["session_id", "actor_id"],
            ["auth_sessions.id", "auth_sessions.user_id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_context_lifetime"),
    )
    op.create_index("ix_context_session", "access_contexts", ["session_id"])
    op.create_index(
        "ix_context_actor_scope", "access_contexts", ["actor_id", "contract_id"]
    )
    op.create_index("ix_membership_role", "memberships", ["role_id"])
    role = conn.dialect.identifier_preparer.quote_identifier(runtime)
    for table in (
        "tenant_roles",
        "tenant_role_permissions",
        "memberships",
        "access_contexts",
    ):
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, {role}")
        privilege = (
            "SELECT, INSERT, UPDATE, DELETE"
            if table == "access_contexts"
            else "SELECT, INSERT, UPDATE"
        )
        op.execute(f"GRANT {privilege} ON TABLE public.{table} TO {role}")


def downgrade():
    for table in (
        "access_contexts",
        "memberships",
        "tenant_role_permissions",
        "tenant_roles",
    ):
        op.drop_table(table)
    op.drop_constraint("uq_auth_session_actor", "auth_sessions", type_="unique")

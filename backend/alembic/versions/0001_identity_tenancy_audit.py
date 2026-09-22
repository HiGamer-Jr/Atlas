"""Phase 1: identity, tenancy and immutable event storage.

Revision ID: 0001
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

BUSINESS = ("users", "platform_role_assignments", "tenants", "contracts")
EVENTS = ("audit_events", "access_events")


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


def identity_column():
    return sa.Column(
        "id", pg.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )


def validate_roles(connection):
    runtime = op.get_context().config.attributes.get("runtime_role")
    if not isinstance(runtime, str) or not runtime:
        raise RuntimeError("An explicit runtime role is required for migration.")
    owner = connection.execute(sa.text("SELECT current_user")).scalar_one()
    if runtime == owner:
        raise RuntimeError("Migration owner and runtime roles must be distinct.")
    flags = connection.execute(
        sa.text("""
        SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls
          OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member=pg_roles.oid)
        FROM pg_roles WHERE rolname=:runtime
    """),
        {"runtime": runtime},
    ).scalar_one_or_none()
    if flags is None or flags:
        raise RuntimeError(
            "Runtime role must exist and have no administrative flags or memberships."
        )
    if connection.execute(
        sa.text("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")
    ).scalar_one():
        raise RuntimeError("Use a dedicated non-superuser migration owner.")
    database_owner = connection.execute(
        sa.text("""
        SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()
    """)
    ).scalar_one()
    if owner != database_owner:
        raise RuntimeError(
            "Migration role must own this dedicated application database."
        )
    return runtime


def upgrade():
    connection = op.get_bind()
    runtime = validate_roles(connection)
    op.create_table(
        "users",
        identity_column(),
        sa.Column("email_normalized", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        *timestamps(),
        sa.CheckConstraint(
            "email_normalized = lower(btrim(email_normalized)) AND length(email_normalized) > 0",
            name="ck_users_email_normalized",
        ),
        sa.CheckConstraint("length(btrim(display_name)) > 0", name="ck_users_name"),
    )
    op.create_table(
        "platform_role_assignments",
        sa.Column(
            "user_id",
            pg.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.CheckConstraint(
            "role IN ('PLATFORM_ADMIN','PLATFORM_SUPPORT')", name="ck_platform_role"
        ),
    )
    op.create_table(
        "tenants",
        identity_column(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_tenants_name"),
    )
    op.create_table(
        "contracts",
        identity_column(),
        sa.Column(
            "tenant_id",
            pg.UUID(),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("environment", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *timestamps(),
        sa.UniqueConstraint("tenant_id", "id", name="uq_contract_scope"),
        sa.CheckConstraint(
            "environment IN ('TEST','STAGING','PRODUCTION')",
            name="ck_contract_environment",
        ),
        sa.CheckConstraint("length(btrim(code)) > 0", name="ck_contract_code"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_contract_name"),
        sa.CheckConstraint("version > 0", name="ck_contract_version"),
    )
    op.create_index("ix_contracts_tenant_id", "contracts", ["tenant_id"])
    for name in EVENTS:
        snapshots = (
            [
                sa.Column("before_state", pg.JSONB()),
                sa.Column("after_state", pg.JSONB()),
            ]
            if name == "audit_events"
            else []
        )
        op.create_table(
            name,
            identity_column(),
            sa.Column(
                "occurred_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "actor_id", pg.UUID(), sa.ForeignKey("users.id", ondelete="RESTRICT")
            ),
            sa.Column("actor_role", sa.String(32)),
            sa.Column("tenant_id", pg.UUID()),
            sa.Column("contract_id", pg.UUID()),
            sa.Column("environment", sa.String(16)),
            sa.Column("entity_type", sa.String(64)),
            sa.Column("entity_id", pg.UUID()),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("outcome", sa.String(16), nullable=False),
            sa.Column("request_id", pg.UUID(), nullable=False),
            sa.Column("support_session_id", pg.UUID()),
            sa.Column("reason", sa.Text()),
            sa.Column("reference", sa.String(200)),
            *snapshots,
            sa.ForeignKeyConstraint(
                ["tenant_id", "contract_id"],
                ["contracts.tenant_id", "contracts.id"],
                ondelete="RESTRICT",
                name=f"fk_{name}_scope",
            ),
            sa.CheckConstraint(
                "(tenant_id IS NULL) = (contract_id IS NULL)", name=f"ck_{name}_context"
            ),
            sa.CheckConstraint(
                "outcome IN ('SUCCESS','DENIED','FAILURE')", name=f"ck_{name}_outcome"
            ),
            sa.CheckConstraint(
                "environment IS NULL OR environment IN ('TEST','STAGING','PRODUCTION')",
                name=f"ck_{name}_environment",
            ),
            sa.CheckConstraint(
                "actor_role IS NULL OR actor_role IN ('PLATFORM_ADMIN','PLATFORM_SUPPORT')",
                name=f"ck_{name}_actor_role",
            ),
            sa.CheckConstraint("length(btrim(action)) > 0", name=f"ck_{name}_action"),
        )
        op.create_index(
            f"ix_{name}_scope_time",
            name,
            ["tenant_id", "contract_id", "occurred_at", "id"],
        )
    # Grants are category-specific. No blanket grants on future technical tables.
    quote = connection.dialect.identifier_preparer.quote_identifier
    role = quote(runtime)
    database = quote(
        connection.execute(sa.text("SELECT current_database()")).scalar_one()
    )
    op.execute(f"REVOKE ALL ON SCHEMA public FROM PUBLIC, {role}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
    op.execute(f"REVOKE CREATE, TEMPORARY ON DATABASE {database} FROM PUBLIC")
    op.execute(f"REVOKE ALL ON DATABASE {database} FROM {role}")
    op.execute(f"GRANT CONNECT ON DATABASE {database} TO {role}")
    op.execute(f"ALTER DEFAULT PRIVILEGES REVOKE ALL ON TABLES FROM PUBLIC, {role}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC, {role}"
    )
    for name in (*BUSINESS, *EVENTS, "alembic_version"):
        op.execute(f"REVOKE ALL ON TABLE public.{name} FROM PUBLIC, {role}")
        privileges = "SELECT, INSERT, UPDATE" if name in BUSINESS else "SELECT, INSERT"
        if name != "alembic_version":
            op.execute(f"GRANT {privileges} ON TABLE public.{name} TO {role}")


def downgrade():
    # Infrastructure ACLs remain fail-closed. They are not broadened by a rollback.
    for name in (
        "access_events",
        "audit_events",
        "contracts",
        "tenants",
        "platform_role_assignments",
        "users",
    ):
        op.drop_table(name)

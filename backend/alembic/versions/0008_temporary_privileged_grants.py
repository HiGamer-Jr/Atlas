"""Exact-session temporary financial/fiscal and maintenance authorization."""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def guard():
    conn = op.get_bind()
    runtime = op.get_context().config.attributes.get("runtime_role")
    safe = conn.execute(
        sa.text("""
        SELECT NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolbypassrls
          AND NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=pg_roles.oid)
          AND rolname<>current_user FROM pg_roles WHERE rolname=:role
    """),
        {"role": runtime},
    ).scalar_one_or_none()
    owner = conn.execute(
        sa.text("""
        SELECT NOT r.rolsuper AND r.oid=d.datdba FROM pg_roles r,pg_database d
        WHERE r.rolname=current_user AND d.datname=current_database()
    """)
    ).scalar_one()
    if not safe or not owner:
        raise RuntimeError("Migration requires safe distinct owner/runtime roles")
    return conn.dialect.identifier_preparer.quote_identifier(runtime)


def upgrade():
    runtime = guard()
    op.create_table(
        "temporary_privileged_grants",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        *[
            sa.Column(name, sa.UUID(), nullable=False)
            for name in (
                "operator_id",
                "operator_session_id",
                "tenant_id",
                "contract_id",
                "parent_context_id",
                "context_id",
            )
        ],
        sa.Column("operator_role", sa.String(32), nullable=False),
        sa.Column("grant_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("reference", sa.String(100)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["operator_session_id", "operator_id"],
            ["auth_sessions.id", "auth_sessions.user_id"],
            ondelete="RESTRICT",
        ),
        *[
            sa.ForeignKeyConstraint(
                [
                    "tenant_id",
                    "contract_id",
                    name,
                    "operator_session_id",
                    "operator_id",
                ],
                [
                    "access_contexts.tenant_id",
                    "access_contexts.contract_id",
                    "access_contexts.id",
                    "access_contexts.session_id",
                    "access_contexts.actor_id",
                ],
                ondelete="RESTRICT",
            )
            for name in ("parent_context_id", "context_id")
        ],
        sa.UniqueConstraint("context_id", name="uq_grant_context"),
        sa.UniqueConstraint("tenant_id", "contract_id", "id", name="uq_grant_scope"),
        *[
            sa.CheckConstraint(expr, name=name)
            for name, expr in (
                ("ck_grant_operator", "operator_role='PLATFORM_ADMIN'"),
                ("ck_grant_type", "grant_type IN ('FINANCIAL_FISCAL','MAINTENANCE')"),
                ("ck_grant_status", "status IN ('ACTIVE','ENDED','EXPIRED','REVOKED')"),
                ("ck_grant_terminal", "(status='ACTIVE') = (ended_at IS NULL)"),
                ("ck_grant_revoked", "(status='REVOKED') = (revoked_at IS NOT NULL)"),
                (
                    "ck_grant_lifetime",
                    "expires_at > started_at AND (ended_at IS NULL OR ended_at >= started_at)",
                ),
                ("ck_grant_contexts", "parent_context_id <> context_id"),
                ("ck_grant_version", "version >= 1"),
                ("ck_grant_reason", "length(btrim(reason)) BETWEEN 3 AND 1000"),
                (
                    "ck_grant_reference",
                    "reference IS NULL OR length(btrim(reference)) BETWEEN 1 AND 100",
                ),
                (
                    "ck_grant_maintenance_reference",
                    "grant_type <> 'MAINTENANCE' OR reference IS NOT NULL",
                ),
            )
        ],
    )
    op.create_index(
        "uq_grant_active_parent",
        "temporary_privileged_grants",
        ["parent_context_id"],
        unique=True,
        postgresql_where=sa.text("status='ACTIVE'"),
    )
    op.create_index(
        "ix_grant_scope_time",
        "temporary_privileged_grants",
        ["tenant_id", "contract_id", "started_at", "id"],
    )
    op.create_table(
        "maintenance_grant_scopes",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        *[
            sa.Column(name, sa.UUID(), nullable=False)
            for name in ("grant_id", "tenant_id", "contract_id")
        ],
        sa.Column("action_code", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.UUID()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "contract_id", "grant_id"],
            [
                "temporary_privileged_grants.tenant_id",
                "temporary_privileged_grants.contract_id",
                "temporary_privileged_grants.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "action_code ~ '^[A-Z][A-Z0-9_]{0,63}$'", name="ck_maintenance_action"
        ),
        sa.CheckConstraint(
            "entity_type='organization_node'", name="ck_maintenance_entity"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "contract_id", "entity_id"],
            [
                "organization_nodes.tenant_id",
                "organization_nodes.contract_id",
                "organization_nodes.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "grant_id", "action_code", name="uq_maintenance_action_scope"
        ),
    )
    for name in ("temporary_privileged_grants", "maintenance_grant_scopes"):
        op.execute(f"REVOKE ALL ON TABLE public.{name} FROM PUBLIC, {runtime}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{name} TO {runtime}")


def downgrade():
    guard()
    op.drop_table("maintenance_grant_scopes")
    op.drop_table("temporary_privileged_grants")

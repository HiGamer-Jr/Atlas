"""READ_ONLY support with composite target/operator/session/context bindings."""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
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
    op.create_unique_constraint(
        "uq_membership_support_target",
        "memberships",
        ["tenant_id", "contract_id", "id", "user_id"],
    )
    op.create_unique_constraint(
        "uq_context_support_binding",
        "access_contexts",
        ["tenant_id", "contract_id", "id", "session_id", "actor_id"],
    )
    op.create_table(
        "support_sessions",
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
                "viewed_membership_id",
                "viewed_user_id",
            )
        ],
        sa.Column("operator_role", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("reference", sa.String(100)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.ForeignKeyConstraint(
            ["operator_session_id", "operator_id"],
            ["auth_sessions.id", "auth_sessions.user_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "contract_id", "viewed_membership_id", "viewed_user_id"],
            [
                "memberships.tenant_id",
                "memberships.contract_id",
                "memberships.id",
                "memberships.user_id",
            ],
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
        sa.UniqueConstraint("context_id", name="uq_support_derived_context"),
        *[
            sa.CheckConstraint(expr, name=name)
            for name, expr in (
                ("ck_support_mode", "mode = 'READ_ONLY'"),
                (
                    "ck_support_operator_role",
                    "operator_role IN ('PLATFORM_ADMIN','PLATFORM_SUPPORT')",
                ),
                (
                    "ck_support_status",
                    "status IN ('ACTIVE','ENDED','EXPIRED','REVOKED')",
                ),
                ("ck_support_terminal", "(status='ACTIVE') = (ended_at IS NULL)"),
                (
                    "ck_support_lifetime",
                    "expires_at > started_at AND (ended_at IS NULL OR ended_at >= started_at)",
                ),
                ("ck_support_contexts", "parent_context_id <> context_id"),
                ("ck_support_target", "operator_id <> viewed_user_id"),
                ("ck_support_reason", "length(btrim(reason)) BETWEEN 3 AND 1000"),
                (
                    "ck_support_reference",
                    "reference IS NULL OR length(reference) BETWEEN 1 AND 100",
                ),
            )
        ],
    )
    op.create_index(
        "uq_support_active_parent",
        "support_sessions",
        ["parent_context_id"],
        unique=True,
        postgresql_where=sa.text("status='ACTIVE'"),
    )
    op.create_index(
        "ix_support_scope_time",
        "support_sessions",
        ["tenant_id", "contract_id", "started_at", "id"],
    )
    op.execute(f"REVOKE ALL ON TABLE public.support_sessions FROM PUBLIC, {runtime}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE ON TABLE public.support_sessions TO {runtime}"
    )


def downgrade():
    guard()
    op.drop_table("support_sessions")
    op.drop_constraint("uq_context_support_binding", "access_contexts", type_="unique")
    op.drop_constraint("uq_membership_support_target", "memberships", type_="unique")

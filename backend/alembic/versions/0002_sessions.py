"""Persistent authentication sessions, preauthentication CSRF and failure counters."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
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
    op.create_table(
        "auth_sessions",
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
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("reauthenticated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("expires_at > created_at", name="ck_auth_session_lifetime"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expiry", "auth_sessions", ["expires_at"])
    op.create_table(
        "auth_preauth",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_preauth_expiry", "auth_preauth", ["expires_at"])
    op.create_table(
        "auth_rate_limits",
        sa.Column("bucket_key", sa.String(64), primary_key=True),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.CheckConstraint("failures >= 0", name="ck_auth_rate_failures"),
    )
    role = connection.dialect.identifier_preparer.quote_identifier(runtime)
    # Technical lifecycle only; never TRUNCATE, ownership or blanket future grants.
    for table in ("auth_sessions", "auth_preauth", "auth_rate_limits"):
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, {role}")
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{table} TO {role}"
        )


def downgrade():
    for table in ("auth_rate_limits", "auth_preauth", "auth_sessions"):
        op.drop_table(table)

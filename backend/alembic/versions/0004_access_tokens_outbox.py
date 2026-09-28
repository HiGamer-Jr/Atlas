"""Single-use security tokens and encrypted delivery outbox."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0004"
down_revision = "0003"
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
    op.add_column(
        "memberships",
        sa.Column(
            "invite_requires_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "memberships",
        sa.Column(
            "invitation_pending",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_table(
        "security_tokens",
        sa.Column(
            "id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column(
            "recipient_user_id",
            UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column(
            "membership_id",
            UUID(),
            sa.ForeignKey("memberships.id", ondelete="RESTRICT"),
        ),
        sa.Column("issuer_role", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "purpose IN ('INVITE','PASSWORD_RESET')", name="ck_security_purpose"
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_security_lifetime"),
    )
    op.create_index(
        "ix_security_tokens_recipient_user_id", "security_tokens", ["recipient_user_id"]
    )
    op.create_table(
        "email_outbox",
        sa.Column(
            "id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "token_id",
            UUID(),
            sa.ForeignKey("security_tokens.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("message_type", sa.String(32), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("ciphertext", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(64)),
        sa.CheckConstraint(
            "status IN ('QUEUED','DISPATCHING','SENT','FAILED','CANCELLED','UNKNOWN')",
            name="ck_outbox_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_outbox_attempts"),
    )
    conn = op.get_bind()
    runtime = op.get_context().config.attributes["runtime_role"]
    role = conn.dialect.identifier_preparer.quote_identifier(runtime)
    for table in ("security_tokens", "email_outbox"):
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, {role}")
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{table} TO {role}")


def downgrade():
    op.drop_table("email_outbox")
    op.drop_table("security_tokens")
    op.drop_column("memberships", "invitation_pending")
    op.drop_column("memberships", "invite_requires_admin")

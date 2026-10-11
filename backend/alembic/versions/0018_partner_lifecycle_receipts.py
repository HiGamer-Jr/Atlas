"""Immutable global lifecycle receipts, deliberately separate from process commands."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0018"
down_revision = "0017"
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
        "partner_lifecycle_receipts",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("auth_sessions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("route", sa.String(200), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("key", sa.Uuid(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("response_json", JSONB(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "user_id",
            "session_id",
            "route",
            "target_id",
            "key",
            name="uq_partner_lifecycle_receipt_key",
            postgresql_nulls_not_distinct=True,
        ),
        sa.CheckConstraint(
            "digest ~ '^[0-9a-f]{64}$'", name="ck_partner_lifecycle_receipt_digest"
        ),
        sa.CheckConstraint(
            "status_code BETWEEN 200 AND 299 AND length(btrim(route)) > 0",
            name="ck_partner_lifecycle_receipt_response",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(response_json)='object' AND octet_length(response_json::text)<=65536",
            name="ck_partner_lifecycle_receipt_body",
        ),
    )
    op.execute(
        "CREATE FUNCTION partner_lifecycle_receipt_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Partner lifecycle receipts are immutable'; END $$"
    )
    op.execute(
        "CREATE TRIGGER partner_lifecycle_receipt_immutable BEFORE UPDATE OR DELETE ON partner_lifecycle_receipts FOR EACH ROW EXECUTE FUNCTION partner_lifecycle_receipt_immutable()"
    )
    op.execute(
        f"REVOKE ALL ON TABLE public.partner_lifecycle_receipts FROM PUBLIC, {runtime}"
    )
    op.execute(
        f"GRANT SELECT,INSERT ON TABLE public.partner_lifecycle_receipts TO {runtime}"
    )


def downgrade():
    guard()
    op.drop_table("partner_lifecycle_receipts")
    op.execute("DROP FUNCTION partner_lifecycle_receipt_immutable()")

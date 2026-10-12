"""Separate partner organizations, individual memberships and closed permissions."""

import sqlalchemy as sa

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

TABLES = (
    "partner_organizations",
    "partner_memberships",
    "partner_membership_permissions",
)


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


def identity_columns():
    return [
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
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
    ]


def upgrade():
    runtime = guard()
    op.create_table(
        "partner_organizations",
        *identity_columns(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "length(btrim(name)) > 0", name="ck_partner_organization_name"
        ),
        sa.CheckConstraint(
            "category IN ('TRADE','CUSTOMS_BROKER','LOGISTICS_OPERATOR','FREIGHT_FORWARDER','OTHER')",
            name="ck_partner_organization_category",
        ),
        sa.CheckConstraint("version > 0", name="ck_partner_organization_version"),
    )
    op.create_table(
        "partner_memberships",
        *identity_columns(),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("partner_organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "invitation_pending",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.UniqueConstraint(
            "organization_id", "user_id", name="uq_partner_membership_user_org"
        ),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_partner_membership_scope"
        ),
        sa.CheckConstraint("version > 0", name="ck_partner_membership_version"),
    )
    op.create_index(
        "ix_partner_memberships_user_id", "partner_memberships", ["user_id"]
    )
    op.create_table(
        "partner_membership_permissions",
        sa.Column("organization_id", sa.Uuid(), primary_key=True),
        sa.Column("membership_id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(100), primary_key=True),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "membership_id"],
            ["partner_memberships.organization_id", "partner_memberships.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "code IN ('partner.processes.read','partner.timeline.read','partner.logistics.update','partner.processes.closure_report','partner.documents.create','partner.documents.read','partner.payment_requests.create','partner.payment_requests.read_org','partner.payment_requests.submit','partner.payment_requests.withdraw')",
            name="ck_partner_permission_code",
        ),
    )
    for table in TABLES:
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, {runtime}")
        op.execute(f"GRANT SELECT,INSERT,UPDATE ON TABLE public.{table} TO {runtime}")


def downgrade():
    guard()
    # Match invitation/lifecycle maintenance order before acquiring DDL table locks.
    op.execute("SELECT pg_advisory_xact_lock(720260925)")  # LIFECYCLE_LOCK
    op.execute("SELECT pg_advisory_xact_lock(720260922)")  # OPERATOR_LOCK
    conn = op.get_bind()
    op.execute("LOCK TABLE " + ", ".join(TABLES) + " IN ACCESS EXCLUSIVE MODE")
    for table in reversed(TABLES):
        if conn.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")).scalar_one():
            raise RuntimeError(
                f"Partner identity evidence must be empty before technical downgrade: {table}"
            )
    for table in reversed(TABLES):
        op.drop_table(table)

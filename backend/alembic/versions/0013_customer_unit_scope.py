"""Explicit membership unit policy; existing grants remain restricted."""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
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
    guard()
    op.add_column(
        "memberships",
        sa.Column(
            "unit_scope_mode",
            sa.String(10),
            nullable=False,
            server_default="RESTRICTED",
        ),
    )
    op.create_check_constraint(
        "ck_membership_unit_scope_mode",
        "memberships",
        "unit_scope_mode IN ('ALL', 'RESTRICTED')",
    )


def downgrade():
    guard()
    # ALL has no explicit grants: downgrading deliberately narrows it to zero units.
    op.drop_constraint("ck_membership_unit_scope_mode", "memberships", type_="check")
    op.drop_column("memberships", "unit_scope_mode")

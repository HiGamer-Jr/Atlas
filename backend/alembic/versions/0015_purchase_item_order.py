"""Atomic in-place item ordering with immediate scoped identity constraints."""

import sqlalchemy as sa

from alembic import op

revision = "0015"
down_revision = "0014"
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


def ordering_constraint(deferrable):
    guard()
    op.drop_constraint(
        "uq_purchase_request_item_position", "purchase_request_items", type_="unique"
    )
    op.create_unique_constraint(
        "uq_purchase_request_item_position",
        "purchase_request_items",
        ["request_id", "position"],
        deferrable=deferrable,
        initially="IMMEDIATE" if deferrable else None,
    )


def upgrade():
    ordering_constraint(True)


def downgrade():
    ordering_constraint(False)

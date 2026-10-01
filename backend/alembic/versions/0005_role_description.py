"""Contextual tenant role descriptions."""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
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
        "tenant_roles",
        sa.Column("description", sa.String(2000), nullable=False, server_default=""),
    )


def downgrade():
    op.drop_column("tenant_roles", "description")

"""Closed Data Hub tenant permissions and frozen preview unit references."""

import sqlalchemy as sa

from alembic import op

revision = "0012"
down_revision = "0011"
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


NEW_CHECK = "capability IN ('memberships.read','roles.read','roles.manage','finance.read','fiscal.read','datahub.read','datahub.template.download','datahub.import','datahub.export','datahub.products.read','datahub.products.import','datahub.products.export','datahub.partners.read','datahub.partners.import','datahub.partners.export','datahub.demands.read','datahub.demands.import','datahub.demands.export','datahub.stock_positions.read','datahub.stock_positions.import','datahub.stock_positions.export','datahub.comex_references.read','datahub.comex_references.import','datahub.comex_references.export','datahub.financial_forecasts.read','datahub.financial_forecasts.import','datahub.financial_forecasts.export')"
OLD_CHECK = "capability IN ('memberships.read','roles.read','roles.manage','finance.read','fiscal.read')"


def upgrade():
    guard()
    op.drop_constraint("ck_tenant_capability", "tenant_role_permissions", type_="check")
    op.create_check_constraint(
        "ck_tenant_capability", "tenant_role_permissions", NEW_CHECK
    )
    op.add_column("datahub_import_rows", sa.Column("unit_id", sa.Uuid(), nullable=True))
    op.add_column(
        "datahub_import_rows", sa.Column("unit_version", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_dh_row_unit",
        "datahub_import_rows",
        "organization_nodes",
        ["tenant_id", "contract_id", "unit_id"],
        ["tenant_id", "contract_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_dh_row_unit_version",
        "datahub_import_rows",
        "(unit_id IS NULL)=(unit_version IS NULL) AND (unit_version IS NULL OR unit_version>0)",
    )


def downgrade():
    guard()
    # Refuse loss of active permissions; operator must decide before downgrade.
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS(SELECT 1 FROM tenant_role_permissions WHERE capability LIKE 'datahub.%')"
            )
        )
        .scalar()
    ):
        raise RuntimeError(
            "Remove Data Hub role permissions explicitly before technical downgrade"
        )
    op.drop_constraint("ck_dh_row_unit_version", "datahub_import_rows", type_="check")
    op.drop_constraint("fk_dh_row_unit", "datahub_import_rows", type_="foreignkey")
    op.drop_column("datahub_import_rows", "unit_version")
    op.drop_column("datahub_import_rows", "unit_id")
    op.drop_constraint("ck_tenant_capability", "tenant_role_permissions", type_="check")
    op.create_check_constraint(
        "ck_tenant_capability", "tenant_role_permissions", OLD_CHECK
    )

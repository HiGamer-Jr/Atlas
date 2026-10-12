"""Discriminated partner invitation target, separate from TENANT membership."""

import sqlalchemy as sa

from alembic import op

revision = "0017"
down_revision = "0016"
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
    op.add_column(
        "security_tokens", sa.Column("partner_membership_id", sa.UUID(), nullable=True)
    )
    op.add_column(
        "security_tokens", sa.Column("issuer_user_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_security_partner_membership",
        "security_tokens",
        "partner_memberships",
        ["partner_membership_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_security_issuer_user",
        "security_tokens",
        "users",
        ["issuer_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    # Legacy INTERNAL onboarding has neither scoped FK; eligibility checks its actual role assignment.
    op.create_check_constraint(
        "ck_security_invitation_target",
        "security_tokens",
        "NOT (membership_id IS NOT NULL AND partner_membership_id IS NOT NULL) "
        "AND (purpose = 'INVITE' OR partner_membership_id IS NULL) "
        "AND (partner_membership_id IS NULL OR "
        "(issuer_role IS NOT NULL AND issuer_role = 'PLATFORM_ADMIN' AND issuer_user_id IS NOT NULL))",
    )


def downgrade():
    guard()
    # Match invitation/lifecycle maintenance order before acquiring DDL table locks.
    op.execute("SELECT pg_advisory_xact_lock(720260925)")  # LIFECYCLE_LOCK
    op.execute("SELECT pg_advisory_xact_lock(720260922)")  # OPERATOR_LOCK
    conn = op.get_bind()
    op.execute("LOCK TABLE security_tokens IN ACCESS EXCLUSIVE MODE")
    if conn.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM security_tokens "
            "WHERE partner_membership_id IS NOT NULL OR issuer_user_id IS NOT NULL)"
        )
    ).scalar_one():
        raise RuntimeError(
            "Partner invitation binding evidence must be empty before technical downgrade"
        )
    op.drop_constraint(
        "ck_security_invitation_target", "security_tokens", type_="check"
    )
    op.drop_constraint("fk_security_issuer_user", "security_tokens", type_="foreignkey")
    op.drop_constraint(
        "fk_security_partner_membership", "security_tokens", type_="foreignkey"
    )
    op.drop_column("security_tokens", "issuer_user_id")
    op.drop_column("security_tokens", "partner_membership_id")

"""Discriminated partner invitation target, separate from TENANT membership."""

import sqlalchemy as sa

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


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
    op.drop_constraint(
        "ck_security_invitation_target", "security_tokens", type_="check"
    )
    op.drop_constraint("fk_security_issuer_user", "security_tokens", type_="foreignkey")
    op.drop_constraint(
        "fk_security_partner_membership", "security_tokens", type_="foreignkey"
    )
    op.drop_column("security_tokens", "issuer_user_id")
    op.drop_column("security_tokens", "partner_membership_id")

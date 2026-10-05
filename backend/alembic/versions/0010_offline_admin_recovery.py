"""Least privilege offline recovery login grants; login is provisioned externally."""

import os

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

SELECT_TABLES = (
    "users",
    "platform_role_assignments",
    "auth_sessions",
    "access_contexts",
    "support_sessions",
    "temporary_privileged_grants",
    "security_tokens",
    "email_outbox",
)
UPDATES = {
    "security_tokens": "invalidated_at",
    "email_outbox": "status,ciphertext,failure_code",
    "users": "password_hash,active,blocked,updated_at",
    "platform_role_assignments": "active,updated_at",
    "auth_sessions": "revoked_at",
    "access_contexts": "revoked_at",
    "support_sessions": "status,ended_at",
    "temporary_privileged_grants": "status,ended_at,revoked_at,version",
}


def recovery_login():
    connection = op.get_bind()
    config = op.get_context().config
    role = config.attributes.get("recovery_role") or os.environ.get(
        "RECOVERY_DATABASE_ROLE"
    )
    if not role:
        return None
    runtime = config.attributes.get("runtime_role")
    valid = connection.execute(
        sa.text("""
        SELECT NOT r.rolsuper AND NOT r.rolcreatedb AND NOT r.rolcreaterole
          AND NOT r.rolbypassrls AND r.rolcanlogin AND r.rolname<>current_user
          AND NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=r.oid)
          AND NOT has_database_privilege(r.rolname,current_database(),'CREATE')
          AND NOT has_schema_privilege(r.rolname,'public','CREATE')
          AND NOT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                         WHERE n.nspname='public' AND c.relowner=r.oid)
        FROM pg_roles r WHERE rolname=:role
    """),
        {"role": role},
    ).scalar_one_or_none()
    owner = connection.execute(
        sa.text(
            "SELECT NOT r.rolsuper AND r.oid=d.datdba FROM pg_roles r,pg_database d WHERE r.rolname=current_user AND d.datname=current_database()"
        )
    ).scalar_one()
    if not valid or not owner or role == runtime:
        raise RuntimeError(
            "Recovery login must be safe and distinct from owner/runtime"
        )
    return connection.dialect.identifier_preparer.quote_identifier(role)


def revoke_columns(role):
    for table, columns in UPDATES.items():
        op.execute(f"REVOKE UPDATE ({columns}) ON TABLE public.{table} FROM {role}")
    op.execute(f"REVOKE SELECT (id,occurred_at,action,entity_id,reference) ON TABLE public.audit_events FROM {role}")


def upgrade():
    role = recovery_login()
    if role is None:
        return
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}")
    revoke_columns(role)
    op.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
    for table in SELECT_TABLES:
        op.execute(f"GRANT SELECT ON TABLE public.{table} TO {role}")
    for table, columns in UPDATES.items():
        op.execute(f"GRANT UPDATE ({columns}) ON TABLE public.{table} TO {role}")
    op.execute(f"GRANT INSERT ON TABLE public.audit_events TO {role}")
    op.execute(f"GRANT SELECT (id,occurred_at,action,entity_id,reference) ON TABLE public.audit_events TO {role}")


def downgrade():
    role = recovery_login()
    if role is not None:
        op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}")
        revoke_columns(role)

"""Controlled processing records with physical authorization/source binding."""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
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
    op.create_unique_constraint(
        "uq_grant_processing_binding",
        "temporary_privileged_grants",
        [
            "tenant_id",
            "contract_id",
            "id",
            "context_id",
            "operator_session_id",
            "operator_id",
            "grant_type",
        ],
    )
    op.create_unique_constraint(
        "uq_maintenance_processing_binding",
        "maintenance_grant_scopes",
        [
            "tenant_id",
            "contract_id",
            "grant_id",
            "action_code",
            "entity_type",
            "entity_id",
        ],
    )
    op.execute("""
CREATE TABLE processing_runs (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	tenant_id UUID NOT NULL,
	contract_id UUID NOT NULL,
	action_code VARCHAR(64) NOT NULL,
	entity_type VARCHAR(64) NOT NULL,
	entity_id UUID NOT NULL,
	source_run_id UUID,
	idempotency_key VARCHAR(100),
	command_fingerprint VARCHAR(64),
	operator_id UUID NOT NULL,
	operator_session_id UUID NOT NULL,
	operator_role VARCHAR(32) NOT NULL,
	context_id UUID NOT NULL,
	grant_id UUID,
	grant_type VARCHAR(32),
	request_id UUID NOT NULL,
	status VARCHAR(16) NOT NULL,
	result_code VARCHAR(32) NOT NULL,
	message_code VARCHAR(32) NOT NULL,
	classification VARCHAR(16) NOT NULL,
	reason VARCHAR(1000),
	reference VARCHAR(100),
	version INTEGER DEFAULT 1 NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE,
	finished_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id),
	FOREIGN KEY(tenant_id, contract_id) REFERENCES contracts (tenant_id, id) ON DELETE RESTRICT,
	FOREIGN KEY(tenant_id, contract_id, entity_id) REFERENCES organization_nodes (tenant_id, contract_id, id) ON DELETE RESTRICT,
	FOREIGN KEY(tenant_id, contract_id, context_id, operator_session_id, operator_id) REFERENCES access_contexts (tenant_id, contract_id, id, session_id, actor_id) ON DELETE RESTRICT,
	FOREIGN KEY(operator_session_id, operator_id) REFERENCES auth_sessions (id, user_id) ON DELETE RESTRICT,
	FOREIGN KEY(tenant_id, contract_id, grant_id, context_id, operator_session_id, operator_id, grant_type) REFERENCES temporary_privileged_grants (tenant_id, contract_id, id, context_id, operator_session_id, operator_id, grant_type) ON DELETE RESTRICT,
	FOREIGN KEY(tenant_id, contract_id, grant_id, action_code, entity_type, entity_id) REFERENCES maintenance_grant_scopes (tenant_id, contract_id, grant_id, action_code, entity_type, entity_id) ON DELETE RESTRICT,
	FOREIGN KEY(tenant_id, contract_id, source_run_id, action_code, entity_type, entity_id) REFERENCES processing_runs (tenant_id, contract_id, id, action_code, entity_type, entity_id) ON DELETE RESTRICT,
	CONSTRAINT uq_processing_source_scope UNIQUE (tenant_id, contract_id, id, action_code, entity_type, entity_id),
	CONSTRAINT uq_processing_idempotency UNIQUE (tenant_id, contract_id, source_run_id, idempotency_key),
	CONSTRAINT ck_processing_status CHECK (status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','UNKNOWN')),
	CONSTRAINT ck_processing_codes CHECK (result_code IN ('NONE','COMPLETED','HANDLER_FAILED','NOT_ELIGIBLE') AND message_code IN ('NONE','COMPLETED','HANDLER_FAILED','NOT_ELIGIBLE')),
	CONSTRAINT ck_processing_classification CHECK (classification IN ('STANDARD','SENSITIVE')),
	CONSTRAINT ck_processing_operator CHECK (operator_role='PLATFORM_ADMIN'),
	CONSTRAINT ck_processing_entity CHECK (entity_type='organization_node'),
	CONSTRAINT ck_processing_action CHECK (action_code ~ '^[A-Z][A-Z0-9_]{0,63}$'),
	CONSTRAINT ck_processing_version CHECK (version>=1),
	CONSTRAINT ck_processing_source_self CHECK (source_run_id IS NULL OR source_run_id<>id),
	CONSTRAINT ck_processing_retry CHECK ((source_run_id IS NULL AND idempotency_key IS NULL AND command_fingerprint IS NULL) OR (source_run_id IS NOT NULL AND idempotency_key IS NOT NULL AND command_fingerprint IS NOT NULL AND idempotency_key ~ '^[A-Za-z0-9_:-]{1,100}$' AND command_fingerprint ~ '^[0-9a-f]{64}$' AND grant_id IS NOT NULL AND grant_type='MAINTENANCE')),
	CONSTRAINT ck_processing_grant CHECK ((grant_id IS NULL)=(grant_type IS NULL)),
	CONSTRAINT ck_processing_started CHECK (started_at IS NULL OR started_at>=created_at),
	CONSTRAINT ck_processing_finished CHECK (finished_at IS NULL OR (started_at IS NOT NULL AND finished_at>=started_at))
)
""")
    op.execute(
        "CREATE INDEX ix_processing_scope_time ON processing_runs (tenant_id, contract_id, created_at, id)"
    )
    op.execute(f"REVOKE ALL ON TABLE public.processing_runs FROM PUBLIC, {runtime}")
    op.execute(
        f"GRANT SELECT,INSERT,UPDATE ON TABLE public.processing_runs TO {runtime}"
    )


def downgrade():
    guard()
    op.drop_table("processing_runs")
    op.drop_constraint(
        "uq_maintenance_processing_binding", "maintenance_grant_scopes", type_="unique"
    )
    op.drop_constraint(
        "uq_grant_processing_binding", "temporary_privileged_grants", type_="unique"
    )

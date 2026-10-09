"""Scoped purchase request aggregate, immutable evidence and least-privilege grants."""

import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
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


TABLES = (
    "purchase_requests",
    "purchase_request_items",
    "purchase_request_events",
    "request_fulfillment_entries",
    "request_attachments",
    "request_command_receipts",
    "contract_request_policies",
)
OLD_CHECK = "capability IN ('memberships.read','roles.read','roles.manage','finance.read','fiscal.read','datahub.read','datahub.template.download','datahub.import','datahub.export','datahub.products.read','datahub.products.import','datahub.products.export','datahub.partners.read','datahub.partners.import','datahub.partners.export','datahub.demands.read','datahub.demands.import','datahub.demands.export','datahub.stock_positions.read','datahub.stock_positions.import','datahub.stock_positions.export','datahub.comex_references.read','datahub.comex_references.import','datahub.comex_references.export','datahub.financial_forecasts.read','datahub.financial_forecasts.import','datahub.financial_forecasts.export')"
NEW_CHECK = "capability IN ('memberships.read','roles.read','roles.manage','finance.read','fiscal.read','datahub.read','datahub.template.download','datahub.import','datahub.export','datahub.products.read','datahub.products.import','datahub.products.export','datahub.partners.read','datahub.partners.import','datahub.partners.export','datahub.demands.read','datahub.demands.import','datahub.demands.export','datahub.stock_positions.read','datahub.stock_positions.import','datahub.stock_positions.export','datahub.comex_references.read','datahub.comex_references.import','datahub.comex_references.export','datahub.financial_forecasts.read','datahub.financial_forecasts.import','datahub.financial_forecasts.export','procurement.requests.create','procurement.requests.read_own','procurement.requests.read_unit','procurement.requests.triage','procurement.requests.approve','procurement.requests.assign','procurement.requests.fulfill','procurement.requests.cancel','procurement.requests.close','procurement.requests.comment')"
DDL = (
    "\nCREATE TABLE purchase_requests (\n\trequester_user_id UUID NOT NULL, \n\trequester_membership_id UUID NOT NULL, \n\trequesting_node_id UUID NOT NULL, \n\ttitle VARCHAR(200) NOT NULL, \n\tdescription VARCHAR(4000) DEFAULT '' NOT NULL, \n\tjustification VARCHAR(4000) DEFAULT '' NOT NULL, \n\tpriority VARCHAR(8) DEFAULT 'NORMAL' NOT NULL, \n\tneeded_on DATE, \n\tnotes VARCHAR(4000) DEFAULT '' NOT NULL, \n\tstatus VARCHAR(24) DEFAULT 'DRAFT' NOT NULL, \n\tbuyer_membership_id UUID, \n\tversion INTEGER DEFAULT 1 NOT NULL, \n\tapproval_mode VARCHAR(16), \n\tapproval_policy_version INTEGER, \n\tapproval_decision_kind VARCHAR(16), \n\tapprover_membership_id UUID, \n\tapprover_user_id UUID, \n\tsubmitted_at TIMESTAMP WITH TIME ZONE, \n\ttriage_started_at TIMESTAMP WITH TIME ZONE, \n\tapproval_requested_at TIMESTAMP WITH TIME ZONE, \n\tapproved_at TIMESTAMP WITH TIME ZONE, \n\tassigned_at TIMESTAMP WITH TIME ZONE, \n\tfulfillment_started_at TIMESTAMP WITH TIME ZONE, \n\tfulfilled_at TIMESTAMP WITH TIME ZONE, \n\tclosed_at TIMESTAMP WITH TIME ZONE, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_purchase_request_scope UNIQUE (tenant_id, contract_id, id), \n\tFOREIGN KEY(tenant_id, contract_id) REFERENCES contracts (tenant_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, requester_membership_id, requester_user_id) REFERENCES memberships (tenant_id, contract_id, id, user_id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, buyer_membership_id) REFERENCES memberships (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, approver_membership_id, approver_user_id) REFERENCES memberships (tenant_id, contract_id, id, user_id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, requesting_node_id) REFERENCES organization_nodes (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_purchase_request_status CHECK (status IN ('DRAFT','SUBMITTED','IN_TRIAGE','AWAITING_APPROVAL','APPROVED','IN_FULFILLMENT','FULFILLED','CLOSED','REJECTED','CANCELLED')), \n\tCONSTRAINT ck_purchase_request_priority CHECK (priority IN ('NORMAL','HIGH','URGENT')), \n\tCONSTRAINT ck_purchase_request_title CHECK (length(btrim(title)) BETWEEN 1 AND 200), \n\tCONSTRAINT ck_purchase_request_version CHECK (version>=1), \n\tCONSTRAINT ck_purchase_request_approval_mode CHECK (approval_mode IS NULL OR approval_mode IN ('REQUIRED','NOT_REQUIRED')), \n\tCONSTRAINT ck_purchase_request_policy_version CHECK ((approval_mode IS NULL)=(approval_policy_version IS NULL) AND (approval_policy_version IS NULL OR approval_policy_version>=0)), \n\tCONSTRAINT ck_purchase_request_decision_kind CHECK (approval_decision_kind IS NULL OR approval_decision_kind IN ('HUMAN','POLICY_WAIVER')), \n\tCONSTRAINT ck_purchase_request_approver CHECK (COALESCE((approver_membership_id IS NULL)=(approver_user_id IS NULL) AND ((approval_decision_kind IS NULL AND approver_user_id IS NULL) OR (approval_decision_kind='HUMAN' AND approval_mode IS NOT NULL AND approval_mode='REQUIRED' AND approver_user_id IS NOT NULL AND approver_user_id<>requester_user_id) OR (approval_decision_kind='POLICY_WAIVER' AND approval_mode IS NOT NULL AND approval_mode='NOT_REQUIRED' AND approver_user_id IS NULL)),false))\n)\n\n",
    "CREATE INDEX ix_purchase_request_needed_on ON purchase_requests (tenant_id, contract_id, needed_on)",
    "CREATE INDEX ix_purchase_request_scope_buyer ON purchase_requests (tenant_id, contract_id, buyer_membership_id)",
    "CREATE INDEX ix_purchase_request_scope_node ON purchase_requests (tenant_id, contract_id, requesting_node_id)",
    "CREATE INDEX ix_purchase_request_scope_requester ON purchase_requests (tenant_id, contract_id, requester_membership_id)",
    "CREATE INDEX ix_purchase_request_scope_status_time ON purchase_requests (tenant_id, contract_id, status, created_at, id)",
    "\nCREATE TABLE purchase_request_items (\n\trequest_id UUID NOT NULL, \n\tposition INTEGER NOT NULL, \n\tdescription VARCHAR(2000) NOT NULL, \n\tspecification VARCHAR(4000) DEFAULT '' NOT NULL, \n\trequested_quantity NUMERIC(18, 6) NOT NULL, \n\tuom_code VARCHAR(4) NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_purchase_request_item_scope UNIQUE (tenant_id, contract_id, request_id, id), \n\tCONSTRAINT uq_purchase_request_item_position UNIQUE (request_id, position), \n\tFOREIGN KEY(tenant_id, contract_id, request_id) REFERENCES purchase_requests (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_purchase_request_item_position CHECK (position BETWEEN 1 AND 100), \n\tCONSTRAINT ck_purchase_request_item_quantity CHECK (requested_quantity>0 AND requested_quantity<1000000000000), \n\tCONSTRAINT ck_purchase_request_item_uom CHECK (uom_code IN ('UN','KG','G','L','ML','M','M2','M3','CX','PCT')), \n\tCONSTRAINT ck_purchase_request_item_content CHECK (length(btrim(description))>0 AND (uom_code NOT IN ('CX','PCT') OR length(btrim(specification))>0))\n)\n\n",
    "CREATE INDEX ix_purchase_request_item_request ON purchase_request_items (tenant_id, contract_id, request_id)",
    "\nCREATE TABLE purchase_request_events (\n\trequest_id UUID NOT NULL, \n\tsequence INTEGER NOT NULL, \n\taggregate_version INTEGER NOT NULL, \n\taction VARCHAR(100) NOT NULL, \n\tactor_user_id UUID NOT NULL, \n\tactor_membership_id UUID NOT NULL, \n\ttenant_role_id UUID NOT NULL, \n\ttenant_role_code VARCHAR(64) NOT NULL, \n\toccurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\treason VARCHAR(2000), \n\tpayload JSONB NOT NULL, \n\taudit_event_id UUID NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(tenant_id, contract_id, request_id) REFERENCES purchase_requests (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, actor_membership_id, actor_user_id) REFERENCES memberships (tenant_id, contract_id, id, user_id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, tenant_role_id) REFERENCES tenant_roles (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_purchase_request_event_sequence UNIQUE (request_id, sequence), \n\tCONSTRAINT ck_purchase_request_event_version CHECK (sequence>=1 AND aggregate_version>=1), \n\tCONSTRAINT ck_purchase_request_event_payload CHECK (jsonb_typeof(payload)='object' AND octet_length(payload::text)<=65536), \n\tCONSTRAINT ck_purchase_request_event_action CHECK (length(btrim(action))>0), \n\tFOREIGN KEY(audit_event_id) REFERENCES audit_events (id) ON DELETE RESTRICT\n)\n\n",
    "CREATE INDEX ix_purchase_request_event_history ON purchase_request_events (tenant_id, contract_id, request_id, sequence)",
    "\nCREATE TABLE request_fulfillment_entries (\n\trequest_id UUID NOT NULL, \n\titem_id UUID NOT NULL, \n\tquantity NUMERIC(18, 6) NOT NULL, \n\tsign INTEGER DEFAULT 1 NOT NULL, \n\tuom_code VARCHAR(4) NOT NULL, \n\toriginal_entry_id UUID, \n\tactor_user_id UUID NOT NULL, \n\tactor_membership_id UUID NOT NULL, \n\toccurred_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tsource_kind VARCHAR(24) DEFAULT 'MANUAL_EXTERNAL' NOT NULL, \n\tevidence VARCHAR(4000) NOT NULL, \n\treason VARCHAR(2000) NOT NULL, \n\taggregate_version INTEGER NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(tenant_id, contract_id, request_id) REFERENCES purchase_requests (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, actor_membership_id, actor_user_id) REFERENCES memberships (tenant_id, contract_id, id, user_id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, request_id, item_id) REFERENCES purchase_request_items (tenant_id, contract_id, request_id, id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_request_fulfillment_entry_scope UNIQUE (tenant_id, contract_id, request_id, item_id, id), \n\tFOREIGN KEY(tenant_id, contract_id, request_id, item_id, original_entry_id) REFERENCES request_fulfillment_entries (tenant_id, contract_id, request_id, item_id, id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_request_fulfillment_reversal UNIQUE (original_entry_id), \n\tCONSTRAINT ck_request_fulfillment_quantity CHECK (quantity>0 AND quantity<1000000000000), \n\tCONSTRAINT ck_request_fulfillment_sign CHECK ((sign=1 AND original_entry_id IS NULL) OR (sign=-1 AND original_entry_id IS NOT NULL AND original_entry_id<>id)), \n\tCONSTRAINT ck_request_fulfillment_source CHECK (source_kind='MANUAL_EXTERNAL'), \n\tCONSTRAINT ck_request_fulfillment_uom CHECK (uom_code IN ('UN','KG','G','L','ML','M','M2','M3','CX','PCT')), \n\tCONSTRAINT ck_request_fulfillment_evidence CHECK (aggregate_version>=1 AND length(btrim(evidence))>0 AND length(btrim(reason))>0)\n)\n\n",
    "CREATE INDEX ix_request_fulfillment_item ON request_fulfillment_entries (tenant_id, contract_id, request_id, item_id)",
    "\nCREATE TABLE request_attachments (\n\trequest_id UUID NOT NULL, \n\titem_id UUID, \n\tuploader_user_id UUID NOT NULL, \n\tuploader_membership_id UUID NOT NULL, \n\tfilename VARCHAR(200) NOT NULL, \n\tmedia_type VARCHAR(64) NOT NULL, \n\tdigest VARCHAR(64) NOT NULL, \n\tsize INTEGER NOT NULL, \n\tcontent BYTEA NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(tenant_id, contract_id, request_id) REFERENCES purchase_requests (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, uploader_membership_id, uploader_user_id) REFERENCES memberships (tenant_id, contract_id, id, user_id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, request_id, item_id) REFERENCES purchase_request_items (tenant_id, contract_id, request_id, id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_request_attachment_digest CHECK (digest ~ '^[0-9a-f]{64}$'), \n\tCONSTRAINT ck_request_attachment_size CHECK (size BETWEEN 1 AND 5242880 AND size=octet_length(content)), \n\tCONSTRAINT ck_request_attachment_type CHECK (media_type IN ('application/pdf','image/png','image/jpeg','text/plain')), \n\tCONSTRAINT ck_request_attachment_filename CHECK (length(btrim(filename))>0 AND filename !~ '[/\\\\]')\n)\n\n",
    "CREATE INDEX ix_request_attachment_request ON request_attachments (tenant_id, contract_id, request_id)",
    "\nCREATE TABLE request_command_receipts (\n\trequest_id UUID NOT NULL, \n\tactor_user_id UUID NOT NULL, \n\taccess_context_id UUID NOT NULL, \n\tauth_session_id UUID NOT NULL, \n\troute VARCHAR(200) NOT NULL, \n\ttarget_id UUID, \n\tidempotency_key UUID NOT NULL, \n\tdigest VARCHAR(64) NOT NULL, \n\tresult JSONB NOT NULL, \n\tresponse_status INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(tenant_id, contract_id, request_id) REFERENCES purchase_requests (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, access_context_id, auth_session_id, actor_user_id) REFERENCES access_contexts (tenant_id, contract_id, id, session_id, actor_id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_request_command_receipt_key UNIQUE NULLS NOT DISTINCT (tenant_id, contract_id, actor_user_id, access_context_id, route, target_id, idempotency_key), \n\tCONSTRAINT ck_request_command_receipt_digest CHECK (digest ~ '^[0-9a-f]{64}$'), \n\tCONSTRAINT ck_request_command_receipt_result CHECK (COALESCE(jsonb_typeof(result)='object' AND result ?& ARRAY['schema_version','version','id','status','tenant_id','contract_id'] AND result->>'schema_version'='1' AND (result->>'version')::integer>=1 AND result->>'id'=request_id::text AND result->>'tenant_id'=tenant_id::text AND result->>'contract_id'=contract_id::text AND result->>'status' IN ('DRAFT','SUBMITTED','IN_TRIAGE','AWAITING_APPROVAL','APPROVED','IN_FULFILLMENT','FULFILLED','CLOSED','REJECTED','CANCELLED') AND octet_length(result::text)<=4194304,false)), \n\tCONSTRAINT ck_request_command_receipt_response CHECK (response_status BETWEEN 200 AND 299 AND length(btrim(route))>0)\n)\n\n",
    "\nCREATE TABLE contract_request_policies (\n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tapproval_mode VARCHAR(16) DEFAULT 'REQUIRED' NOT NULL, \n\tversion INTEGER DEFAULT 1 NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (tenant_id, contract_id), \n\tFOREIGN KEY(tenant_id, contract_id) REFERENCES contracts (tenant_id, id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_contract_request_policy_mode CHECK (approval_mode IN ('REQUIRED','NOT_REQUIRED')), \n\tCONSTRAINT ck_contract_request_policy_version CHECK (version>=1)\n)\n\n",
)


def upgrade():
    runtime = guard()
    for statement in DDL:
        op.execute(statement)
    op.drop_constraint("ck_tenant_capability", "tenant_role_permissions", type_="check")
    op.create_check_constraint(
        "ck_tenant_capability", "tenant_role_permissions", NEW_CHECK
    )
    for table in TABLES:
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, {runtime}")
        op.execute(f"GRANT SELECT,INSERT ON TABLE public.{table} TO {runtime}")
    request_columns = "requesting_node_id,title,description,justification,priority,needed_on,notes,status,buyer_membership_id,version,approval_mode,approval_policy_version,approval_decision_kind,approver_membership_id,approver_user_id,updated_at,submitted_at,triage_started_at,approval_requested_at,approved_at,assigned_at,fulfillment_started_at,fulfilled_at,closed_at"
    op.execute(
        f"GRANT UPDATE ({request_columns}) ON public.purchase_requests TO {runtime}"
    )
    op.execute(
        f"GRANT UPDATE (position,description,specification,requested_quantity,uom_code,updated_at) ON public.purchase_request_items TO {runtime}"
    )
    op.execute(
        f"GRANT DELETE ON public.purchase_request_items,public.request_attachments TO {runtime}"
    )
    op.execute(
        f"GRANT UPDATE (approval_mode,version,updated_at) ON public.contract_request_policies TO {runtime}"
    )
    op.execute("""
    CREATE FUNCTION purchase_request_guard_draft_child() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE request_status text;
    BEGIN
        SELECT status INTO request_status FROM purchase_requests
        WHERE tenant_id=CASE WHEN TG_OP='INSERT' THEN NEW.tenant_id ELSE OLD.tenant_id END
        AND contract_id=CASE WHEN TG_OP='INSERT' THEN NEW.contract_id ELSE OLD.contract_id END
        AND id=CASE WHEN TG_OP='INSERT' THEN NEW.request_id ELSE OLD.request_id END FOR UPDATE;
        IF request_status IS DISTINCT FROM 'DRAFT' THEN
            RAISE EXCEPTION 'Purchase request evidence is frozen after submission' USING ERRCODE='23514';
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END $$
    """)
    op.execute(
        "CREATE TRIGGER purchase_request_item_frozen BEFORE INSERT OR UPDATE OR DELETE ON purchase_request_items FOR EACH ROW EXECUTE FUNCTION purchase_request_guard_draft_child()"
    )
    op.execute(
        "CREATE TRIGGER purchase_request_attachment_frozen BEFORE DELETE ON request_attachments FOR EACH ROW EXECUTE FUNCTION purchase_request_guard_draft_child()"
    )
    op.execute("""
    CREATE FUNCTION purchase_request_guard_audit_scope() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM audit_events WHERE id=NEW.audit_event_id AND tenant_id=NEW.tenant_id AND contract_id=NEW.contract_id) THEN
            RAISE EXCEPTION 'Purchase request audit scope mismatch' USING ERRCODE='23503';
        END IF;
        RETURN NEW;
    END $$
    """)
    op.execute(
        "CREATE TRIGGER purchase_request_event_audit_scope BEFORE INSERT ON purchase_request_events FOR EACH ROW EXECUTE FUNCTION purchase_request_guard_audit_scope()"
    )


def downgrade():
    guard()
    conn = op.get_bind()
    for table in TABLES:
        if conn.execute(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")).scalar_one():
            raise RuntimeError(
                "Purchase request evidence must be empty before technical downgrade"
            )
    if conn.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM tenant_role_permissions WHERE capability LIKE 'procurement.requests.%')"
        )
    ).scalar_one():
        raise RuntimeError(
            "Remove purchase request role permissions explicitly before technical downgrade"
        )
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute("DROP FUNCTION purchase_request_guard_draft_child()")
    op.execute("DROP FUNCTION purchase_request_guard_audit_scope()")
    op.drop_constraint("ck_tenant_capability", "tenant_role_permissions", type_="check")
    op.create_check_constraint(
        "ck_tenant_capability", "tenant_role_permissions", OLD_CHECK
    )

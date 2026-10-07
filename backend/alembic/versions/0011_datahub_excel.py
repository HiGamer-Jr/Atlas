"""Typed Data Hub imports and informational record provenance, scoped physically."""

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
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
    "datahub_imports",
    "datahub_import_files",
    "datahub_import_rows",
    "datahub_import_issues",
    "datahub_records",
    "datahub_financial_forecasts",
    "datahub_partners",
    "datahub_products",
    "datahub_comex_references",
    "datahub_demands",
    "datahub_stock_positions",
)

DDL = (
    "\nCREATE TABLE datahub_imports (\n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\taccess_context_id UUID NOT NULL, \n\tauth_session_id UUID NOT NULL, \n\tactor_user_id UUID NOT NULL, \n\tconnector_code VARCHAR(16) DEFAULT 'XLSX' NOT NULL, \n\ttemplate_id VARCHAR(32) NOT NULL, \n\ttemplate_version INTEGER NOT NULL, \n\tsource_digest VARCHAR(64) NOT NULL, \n\tstatus VARCHAR(24) DEFAULT 'RECEIVED' NOT NULL, \n\tversion INTEGER DEFAULT 1 NOT NULL, \n\trequest_id UUID NOT NULL, \n\tvalidated_at TIMESTAMP WITH TIME ZONE, \n\tpreview_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tcommitted_at TIMESTAMP WITH TIME ZONE, \n\tfinished_at TIMESTAMP WITH TIME ZONE, \n\tidempotency_key UUID, \n\tresult_code VARCHAR(64) DEFAULT 'NONE' NOT NULL, \n\trow_count INTEGER DEFAULT 0 NOT NULL, \n\tinserted_count INTEGER DEFAULT 0 NOT NULL, \n\tskipped_count INTEGER DEFAULT 0 NOT NULL, \n\terror_count INTEGER DEFAULT 0 NOT NULL, \n\twarning_count INTEGER DEFAULT 0 NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_dh_import_scope UNIQUE (tenant_id, contract_id, id), \n\tFOREIGN KEY(tenant_id, contract_id) REFERENCES contracts (tenant_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, access_context_id, auth_session_id, actor_user_id) REFERENCES access_contexts (tenant_id, contract_id, id, session_id, actor_id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_dh_import_status CHECK (status IN ('RECEIVED','VALIDATING','READY_FOR_CONFIRMATION','REJECTED','EXPIRED','COMMITTED','FAILED')), \n\tCONSTRAINT ck_dh_import_connector CHECK (connector_code='XLSX'), \n\tCONSTRAINT ck_dh_import_template CHECK (template_id IN ('COORDENACAO','SUPERVISAO','COMPRADOR_NACIONAL','COMPRADOR_INTERNACIONAL','FINANCEIRO','DIRETORIA','LOJA','CENTRO_DISTRIBUICAO')), \n\tCONSTRAINT ck_dh_import_version CHECK (template_version=1 AND version>=1), \n\tCONSTRAINT ck_dh_import_digest CHECK (source_digest ~ '^[0-9a-f]{64}$'), \n\tCONSTRAINT ck_dh_import_expiry CHECK (preview_expires_at>created_at), \n\tCONSTRAINT ck_dh_import_validated CHECK (validated_at IS NULL OR validated_at>=created_at), \n\tCONSTRAINT ck_dh_import_finished CHECK (finished_at IS NULL OR finished_at>=created_at), \n\tCONSTRAINT ck_dh_import_committed CHECK ((status='COMMITTED')=(committed_at IS NOT NULL)), \n\tCONSTRAINT ck_dh_import_commit_time CHECK (committed_at IS NULL OR (committed_at>=created_at AND finished_at IS NOT NULL AND idempotency_key IS NOT NULL)), \n\tCONSTRAINT ck_dh_import_counts CHECK (row_count>=0 AND inserted_count>=0 AND skipped_count>=0 AND error_count>=0 AND warning_count>=0)\n)\n\n",
    "CREATE INDEX ix_datahub_imports_contract_id ON datahub_imports (contract_id)",
    "CREATE INDEX ix_datahub_imports_tenant_id ON datahub_imports (tenant_id)",
    "\nCREATE TABLE datahub_import_files (\n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\timport_id UUID NOT NULL, \n\tname VARCHAR(200) NOT NULL, \n\tdigest VARCHAR(64) NOT NULL, \n\tsize_bytes INTEGER NOT NULL, \n\tformat VARCHAR(8) DEFAULT 'XLSX' NOT NULL, \n\tsheet_count INTEGER DEFAULT 0 NOT NULL, \n\tentry_count INTEGER DEFAULT 0 NOT NULL, \n\traw_reference UUID, \n\tretention_policy VARCHAR(16) DEFAULT 'TEMPORARY' NOT NULL, \n\traw_expires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\traw_deleted_at TIMESTAMP WITH TIME ZONE, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_dh_one_file UNIQUE (import_id), \n\tCONSTRAINT uq_dh_file_scope UNIQUE (tenant_id, contract_id, id, import_id), \n\tFOREIGN KEY(tenant_id, contract_id, import_id) REFERENCES datahub_imports (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_dh_file_digest_size CHECK (digest ~ '^[0-9a-f]{64}$' AND size_bytes>0), \n\tCONSTRAINT ck_dh_file_retention CHECK (raw_expires_at>created_at AND (raw_deleted_at IS NULL OR raw_deleted_at>=created_at)), \n\tCONSTRAINT ck_dh_file_reference CHECK ((raw_reference IS NULL)=(raw_deleted_at IS NOT NULL)), \n\tCONSTRAINT ck_dh_file_metadata CHECK (format='XLSX' AND sheet_count>=0 AND entry_count>=0), \n\tCONSTRAINT ck_dh_file_policy CHECK (retention_policy='TEMPORARY')\n)\n\n",
    "CREATE INDEX ix_datahub_import_files_contract_id ON datahub_import_files (contract_id)",
    "CREATE INDEX ix_datahub_import_files_tenant_id ON datahub_import_files (tenant_id)",
    "\nCREATE TABLE datahub_import_rows (\n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\timport_id UUID NOT NULL, \n\tfile_id UUID NOT NULL, \n\tdataset_code VARCHAR(32) NOT NULL, \n\tschema_version INTEGER DEFAULT 1 NOT NULL, \n\tsheet VARCHAR(31) NOT NULL, \n\tsource_row INTEGER NOT NULL, \n\tnormalized_payload JSONB NOT NULL, \n\tvalidation_status VARCHAR(16) NOT NULL, \n\tfingerprint VARCHAR(64), \n\trecord_id UUID, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_dh_row_origin UNIQUE (tenant_id, contract_id, id, import_id, file_id, dataset_code), \n\tCONSTRAINT uq_dh_row_issue_scope UNIQUE (tenant_id, contract_id, id, import_id), \n\tCONSTRAINT uq_dh_source_row UNIQUE (import_id, sheet, source_row), \n\tFOREIGN KEY(tenant_id, contract_id, file_id, import_id) REFERENCES datahub_import_files (tenant_id, contract_id, id, import_id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_dh_row_dataset CHECK (dataset_code IN ('PRODUCTS','PARTNERS','DEMANDS','STOCK_POSITIONS','COMEX_REFERENCES','FINANCIAL_FORECASTS')), \n\tCONSTRAINT ck_dh_row_schema_position CHECK (schema_version=1 AND source_row>=13), \n\tCONSTRAINT ck_dh_row_status CHECK (validation_status IN ('VALID','INVALID','SKIPPED')), \n\tCONSTRAINT ck_dh_row_payload CHECK (jsonb_typeof(normalized_payload)='object'), \n\tCONSTRAINT ck_dh_row_fingerprint CHECK (fingerprint IS NULL OR fingerprint ~ '^[0-9a-f]{64}$'), \n\tCONSTRAINT ck_dh_row_valid_digest CHECK (validation_status='INVALID' OR fingerprint IS NOT NULL), \n\tCONSTRAINT ck_dh_row_invalid_record CHECK (validation_status<>'INVALID' OR record_id IS NULL)\n)\n\n",
    "CREATE INDEX ix_datahub_import_rows_contract_id ON datahub_import_rows (contract_id)",
    "CREATE INDEX ix_datahub_import_rows_tenant_id ON datahub_import_rows (tenant_id)",
    "\nCREATE TABLE datahub_import_issues (\n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\timport_id UUID NOT NULL, \n\timport_row_id UUID, \n\tsheet VARCHAR(31), \n\tsource_row INTEGER, \n\t\"column\" VARCHAR(64), \n\tseverity VARCHAR(8) NOT NULL, \n\tstable_error_code VARCHAR(64) NOT NULL, \n\tmessage VARCHAR(300) NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(tenant_id, contract_id, import_id) REFERENCES datahub_imports (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, import_row_id, import_id) REFERENCES datahub_import_rows (tenant_id, contract_id, id, import_id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_dh_issue_severity CHECK (severity IN ('ERROR','WARNING')), \n\tCONSTRAINT ck_dh_issue_code CHECK (stable_error_code ~ '^[A-Z][A-Z0-9_]{0,63}$')\n)\n\n",
    "CREATE INDEX ix_datahub_import_issues_contract_id ON datahub_import_issues (contract_id)",
    "CREATE INDEX ix_datahub_import_issues_tenant_id ON datahub_import_issues (tenant_id)",
    "\nCREATE TABLE datahub_records (\n\tid UUID DEFAULT gen_random_uuid() NOT NULL, \n\tdataset_code VARCHAR(32) NOT NULL, \n\tschema_version INTEGER DEFAULT 1 NOT NULL, \n\tbusiness_key VARCHAR(512) NOT NULL, \n\tfingerprint VARCHAR(64) NOT NULL, \n\tsource_import_id UUID NOT NULL, \n\tsource_file_id UUID NOT NULL, \n\tsource_row_id UUID NOT NULL, \n\tversion INTEGER DEFAULT 1 NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT uq_dh_record_scope_kind UNIQUE (tenant_id, contract_id, id, dataset_code), \n\tCONSTRAINT uq_dh_record_business_key UNIQUE (tenant_id, contract_id, dataset_code, business_key), \n\tFOREIGN KEY(tenant_id, contract_id, source_row_id, source_import_id, source_file_id, dataset_code) REFERENCES datahub_import_rows (tenant_id, contract_id, id, import_id, file_id, dataset_code) ON DELETE RESTRICT, \n\tCONSTRAINT ck_dh_record_dataset CHECK (dataset_code IN ('PRODUCTS','PARTNERS','DEMANDS','STOCK_POSITIONS','COMEX_REFERENCES','FINANCIAL_FORECASTS')), \n\tCONSTRAINT ck_dh_record_version CHECK (schema_version=1 AND version>=1), \n\tCONSTRAINT ck_dh_record_key_digest CHECK (fingerprint ~ '^[0-9a-f]{64}$' AND length(business_key)>0)\n)\n\n",
    "CREATE INDEX ix_datahub_records_contract_id ON datahub_records (contract_id)",
    "CREATE INDEX ix_datahub_records_tenant_id ON datahub_records (tenant_id)",
    "\nCREATE TABLE datahub_financial_forecasts (\n\tcodigo VARCHAR(64) NOT NULL, \n\treferencia_externa VARCHAR(128) DEFAULT '' NOT NULL, \n\tunit_id UUID NOT NULL, \n\tmoeda VARCHAR(3) NOT NULL, \n\tvalor NUMERIC(20, 4) NOT NULL, \n\tvencimento DATE NOT NULL, \n\tnatureza VARCHAR(8) NOT NULL, \n\trecord_id UUID NOT NULL, \n\tdataset_code VARCHAR(32) NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tPRIMARY KEY (record_id), \n\tFOREIGN KEY(tenant_id, contract_id, record_id, dataset_code) REFERENCES datahub_records (tenant_id, contract_id, id, dataset_code) ON DELETE RESTRICT, \n\tCONSTRAINT uq_dh_financial_forecasts_scope UNIQUE (tenant_id, contract_id, record_id), \n\tCONSTRAINT ck_dh_financial_forecasts_kind CHECK (dataset_code='FINANCIAL_FORECASTS'), \n\tFOREIGN KEY(tenant_id, contract_id, unit_id) REFERENCES organization_nodes (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_dh_financial_values CHECK (valor>0 AND moeda IN ('BRL','USD','EUR','GBP','CNY') AND natureza IN ('ENTRADA','SAIDA'))\n)\n\n",
    "CREATE INDEX ix_datahub_financial_forecasts_contract_id ON datahub_financial_forecasts (contract_id)",
    "CREATE INDEX ix_datahub_financial_forecasts_tenant_id ON datahub_financial_forecasts (tenant_id)",
    "\nCREATE TABLE datahub_partners (\n\tcodigo VARCHAR(64) NOT NULL, \n\tnome VARCHAR(200) NOT NULL, \n\ttipo VARCHAR(16) NOT NULL, \n\tpais_iso VARCHAR(2) NOT NULL, \n\tativo BOOLEAN NOT NULL, \n\trecord_id UUID NOT NULL, \n\tdataset_code VARCHAR(32) NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tPRIMARY KEY (record_id), \n\tFOREIGN KEY(tenant_id, contract_id, record_id, dataset_code) REFERENCES datahub_records (tenant_id, contract_id, id, dataset_code) ON DELETE RESTRICT, \n\tCONSTRAINT uq_dh_partners_scope UNIQUE (tenant_id, contract_id, record_id), \n\tCONSTRAINT ck_dh_partners_kind CHECK (dataset_code='PARTNERS'), \n\tCONSTRAINT ck_dh_partner_type_country CHECK (tipo IN ('FORNECEDOR','CLIENTE','TRANSPORTADOR') AND pais_iso ~ '^[A-Z]{2}$')\n)\n\n",
    "CREATE INDEX ix_datahub_partners_contract_id ON datahub_partners (contract_id)",
    "CREATE INDEX ix_datahub_partners_tenant_id ON datahub_partners (tenant_id)",
    "\nCREATE TABLE datahub_products (\n\tcodigo VARCHAR(64) NOT NULL, \n\tdescricao VARCHAR(200) NOT NULL, \n\tunidade_medida VARCHAR(8) NOT NULL, \n\tcategoria VARCHAR(120) DEFAULT '' NOT NULL, \n\tativo BOOLEAN NOT NULL, \n\trecord_id UUID NOT NULL, \n\tdataset_code VARCHAR(32) NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tPRIMARY KEY (record_id), \n\tFOREIGN KEY(tenant_id, contract_id, record_id, dataset_code) REFERENCES datahub_records (tenant_id, contract_id, id, dataset_code) ON DELETE RESTRICT, \n\tCONSTRAINT uq_dh_products_scope UNIQUE (tenant_id, contract_id, record_id), \n\tCONSTRAINT ck_dh_products_kind CHECK (dataset_code='PRODUCTS'), \n\tCONSTRAINT ck_dh_product_uom CHECK (unidade_medida IN ('UN','KG','TON','L','M','M2','M3','CX','PAL'))\n)\n\n",
    "CREATE INDEX ix_datahub_products_contract_id ON datahub_products (contract_id)",
    "CREATE INDEX ix_datahub_products_tenant_id ON datahub_products (tenant_id)",
    "\nCREATE TABLE datahub_comex_references (\n\tcodigo VARCHAR(64) NOT NULL, \n\tpartner_id UUID NOT NULL, \n\tmoeda VARCHAR(3) NOT NULL, \n\tincoterm VARCHAR(3) NOT NULL, \n\tdata_prevista DATE NOT NULL, \n\tstatus VARCHAR(16) NOT NULL, \n\trecord_id UUID NOT NULL, \n\tdataset_code VARCHAR(32) NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tPRIMARY KEY (record_id), \n\tFOREIGN KEY(tenant_id, contract_id, record_id, dataset_code) REFERENCES datahub_records (tenant_id, contract_id, id, dataset_code) ON DELETE RESTRICT, \n\tCONSTRAINT uq_dh_comex_references_scope UNIQUE (tenant_id, contract_id, record_id), \n\tCONSTRAINT ck_dh_comex_references_kind CHECK (dataset_code='COMEX_REFERENCES'), \n\tFOREIGN KEY(tenant_id, contract_id, partner_id) REFERENCES datahub_partners (tenant_id, contract_id, record_id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_dh_comex_values CHECK (moeda IN ('BRL','USD','EUR','GBP','CNY') AND incoterm IN ('EXW','FCA','CPT','CIP','DAP','DPU','DDP','FAS','FOB','CFR','CIF') AND status IN ('PLANEJADO','EM_ANDAMENTO','CONCLUIDO','CANCELADO'))\n)\n\n",
    "CREATE INDEX ix_datahub_comex_references_contract_id ON datahub_comex_references (contract_id)",
    "CREATE INDEX ix_datahub_comex_references_tenant_id ON datahub_comex_references (tenant_id)",
    "\nCREATE TABLE datahub_demands (\n\tcodigo VARCHAR(64) NOT NULL, \n\tproduct_id UUID NOT NULL, \n\tunit_id UUID NOT NULL, \n\tquantidade NUMERIC(20, 4) NOT NULL, \n\tdata_necessidade DATE NOT NULL, \n\tmodalidade VARCHAR(16) NOT NULL, \n\tprioridade VARCHAR(8) NOT NULL, \n\trecord_id UUID NOT NULL, \n\tdataset_code VARCHAR(32) NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tPRIMARY KEY (record_id), \n\tFOREIGN KEY(tenant_id, contract_id, record_id, dataset_code) REFERENCES datahub_records (tenant_id, contract_id, id, dataset_code) ON DELETE RESTRICT, \n\tCONSTRAINT uq_dh_demands_scope UNIQUE (tenant_id, contract_id, record_id), \n\tCONSTRAINT ck_dh_demands_kind CHECK (dataset_code='DEMANDS'), \n\tFOREIGN KEY(tenant_id, contract_id, unit_id) REFERENCES organization_nodes (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, product_id) REFERENCES datahub_products (tenant_id, contract_id, record_id) ON DELETE RESTRICT, \n\tCONSTRAINT ck_dh_demand_values CHECK (quantidade>0 AND modalidade IN ('NACIONAL','INTERNACIONAL') AND prioridade IN ('BAIXA','NORMAL','ALTA','URGENTE'))\n)\n\n",
    "CREATE INDEX ix_datahub_demands_contract_id ON datahub_demands (contract_id)",
    "CREATE INDEX ix_datahub_demands_tenant_id ON datahub_demands (tenant_id)",
    "\nCREATE TABLE datahub_stock_positions (\n\tproduct_id UUID NOT NULL, \n\tunit_id UUID NOT NULL, \n\tquantidade_disponivel NUMERIC(20, 4) NOT NULL, \n\tdata_referencia DATE NOT NULL, \n\trecord_id UUID NOT NULL, \n\tdataset_code VARCHAR(32) NOT NULL, \n\ttenant_id UUID NOT NULL, \n\tcontract_id UUID NOT NULL, \n\tPRIMARY KEY (record_id), \n\tFOREIGN KEY(tenant_id, contract_id, record_id, dataset_code) REFERENCES datahub_records (tenant_id, contract_id, id, dataset_code) ON DELETE RESTRICT, \n\tCONSTRAINT uq_dh_stock_positions_scope UNIQUE (tenant_id, contract_id, record_id), \n\tCONSTRAINT ck_dh_stock_positions_kind CHECK (dataset_code='STOCK_POSITIONS'), \n\tFOREIGN KEY(tenant_id, contract_id, unit_id) REFERENCES organization_nodes (tenant_id, contract_id, id) ON DELETE RESTRICT, \n\tFOREIGN KEY(tenant_id, contract_id, product_id) REFERENCES datahub_products (tenant_id, contract_id, record_id) ON DELETE RESTRICT, \n\tCONSTRAINT uq_dh_stock_position UNIQUE (tenant_id, contract_id, product_id, unit_id, data_referencia), \n\tCONSTRAINT ck_dh_stock_amount CHECK (quantidade_disponivel>=0)\n)\n\n",
    "CREATE INDEX ix_datahub_stock_positions_contract_id ON datahub_stock_positions (contract_id)",
    "CREATE INDEX ix_datahub_stock_positions_tenant_id ON datahub_stock_positions (tenant_id)",
    "ALTER TABLE datahub_import_rows ADD CONSTRAINT fk_dh_row_record FOREIGN KEY(tenant_id, contract_id, record_id, dataset_code) REFERENCES datahub_records (tenant_id, contract_id, id, dataset_code) ON DELETE RESTRICT",
)


def upgrade():
    runtime = guard()
    for statement in DDL:
        op.execute(statement)
    for table in TABLES:
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, {runtime}")
        op.execute(f"GRANT SELECT,INSERT,UPDATE ON TABLE public.{table} TO {runtime}")


def downgrade():
    guard()
    op.drop_constraint("fk_dh_row_record", "datahub_import_rows", type_="foreignkey")
    for table in reversed(TABLES):
        op.drop_table(table)

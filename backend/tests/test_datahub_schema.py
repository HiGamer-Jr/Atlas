import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

TABLES = {
    "datahub_imports",
    "datahub_import_files",
    "datahub_import_rows",
    "datahub_import_issues",
    "datahub_records",
    "datahub_products",
    "datahub_partners",
    "datahub_demands",
    "datahub_stock_positions",
    "datahub_comex_references",
    "datahub_financial_forecasts",
}


def test_five_entities_are_separate(db_runtime):
    with db_runtime.connect() as conn:
        assert TABLES <= set(inspect(conn).get_table_names())


@pytest.mark.parametrize("table", sorted(TABLES))
@pytest.mark.parametrize("verb", ["DELETE FROM", "TRUNCATE"])
def test_runtime_cannot_delete_records(db_runtime, table, verb):
    with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
        conn.execute(text(f"{verb} {table}"))
    assert error.value.orig.sqlstate == "42501"


def import_row(conn, context_id, tenant_id, contract_id):
    from uuid import uuid4

    identity = conn.execute(
        text("SELECT session_id,actor_id FROM access_contexts WHERE id=:id"),
        {"id": context_id},
    ).one()
    import_id = uuid4()
    conn.execute(
        text("""INSERT INTO datahub_imports
        (id,tenant_id,contract_id,access_context_id,auth_session_id,actor_user_id,
        template_id,template_version,source_digest,request_id,preview_expires_at)
        VALUES (:id,:tenant,:contract,:context,:session,:actor,'COORDENACAO',1,:digest,:request,now()+interval '20 minutes')"""),
        {
            "id": import_id,
            "tenant": tenant_id,
            "contract": contract_id,
            "context": context_id,
            "session": identity[0],
            "actor": identity[1],
            "digest": "a" * 64,
            "request": uuid4(),
        },
    )
    return import_id


def test_foreign_provenance_fk_rejected(db_runtime, scope_ids, admin):
    from tests.helpers import select_context

    ctx = select_context(admin, scope_ids["contract_a"])["X-HiAtlas-Context"]
    with db_runtime.begin() as conn:
        assert "datahub_imports" in inspect(conn).get_table_names(), (
            "Imports not implemented"
        )
        import_id = import_row(
            conn, ctx, scope_ids["tenant_a"], scope_ids["contract_a"]
        )
    with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
        conn.execute(
            text("""INSERT INTO datahub_import_files
            (tenant_id,contract_id,import_id,name,digest,size_bytes,raw_reference,raw_expires_at)
            VALUES (:tenant,:contract,:import,'synthetic.xlsx',:digest,100,gen_random_uuid(),now()+interval '24 hours')"""),
            {
                "tenant": scope_ids["tenant_a"],
                "contract": scope_ids["contract_a2"],
                "import": import_id,
                "digest": "a" * 64,
            },
        )
    assert error.value.orig.sqlstate == "23503"


@pytest.mark.parametrize(
    "change",
    [
        "status='UNKNOWN'",
        "version=0",
        "template_version=0",
        "source_digest='not-a-digest'",
        "preview_expires_at=created_at",
    ],
)
def test_import_physical_constraints(db_runtime, scope_ids, admin, change):
    from tests.helpers import select_context

    ctx = select_context(admin, scope_ids["contract_a"])["X-HiAtlas-Context"]
    with db_runtime.begin() as conn:
        assert "datahub_imports" in inspect(conn).get_table_names(), (
            "Imports not implemented"
        )
        id = import_row(conn, ctx, scope_ids["tenant_a"], scope_ids["contract_a"])
    with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
        conn.execute(
            text(f"UPDATE datahub_imports SET {change} WHERE id=:id"), {"id": id}
        )
    assert error.value.orig.sqlstate == "23514"


# Test-only synthetic records exercise the physical constraints, not ingestion authorization.
def seed_record(conn, ctx, tenant, contract, dataset="PRODUCTS", key="P1"):
    from uuid import uuid4

    import_id = import_row(conn, ctx, tenant, contract)
    file_id, row_id, record_id = uuid4(), uuid4(), uuid4()
    values = {
        "tenant": tenant,
        "contract": contract,
        "import": import_id,
        "file": file_id,
        "row": row_id,
        "record": record_id,
        "dataset": dataset,
        "key": key,
        "digest": "a" * 64,
    }
    conn.execute(
        text("""INSERT INTO datahub_import_files
      (id,tenant_id,contract_id,import_id,name,digest,size_bytes,raw_reference,raw_expires_at)
      VALUES (:file,:tenant,:contract,:import,'synthetic.xlsx',:digest,100,gen_random_uuid(),now()+interval '24 hours')"""),
        values,
    )
    conn.execute(
        text("""INSERT INTO datahub_import_rows
      (id,tenant_id,contract_id,import_id,file_id,dataset_code,sheet,source_row,normalized_payload,validation_status,fingerprint)
      VALUES (:row,:tenant,:contract,:import,:file,:dataset,'Synthetic',13,'{}','VALID',:digest)"""),
        values,
    )
    conn.execute(
        text("""INSERT INTO datahub_records
      (id,tenant_id,contract_id,dataset_code,business_key,fingerprint,source_import_id,source_file_id,source_row_id)
      VALUES (:record,:tenant,:contract,:dataset,:key,:digest,:import,:file,:row)"""),
        values,
    )
    if dataset == "PRODUCTS":
        conn.execute(
            text("""INSERT INTO datahub_products
          (record_id,tenant_id,contract_id,dataset_code,codigo,descricao,unidade_medida,ativo)
          VALUES (:record,:tenant,:contract,:dataset,:key,'Produto sintético','UN',true)"""),
            values,
        )
    if dataset == "PARTNERS":
        conn.execute(
            text("""INSERT INTO datahub_partners
          (record_id,tenant_id,contract_id,dataset_code,codigo,nome,tipo,pais_iso,ativo)
          VALUES (:record,:tenant,:contract,:dataset,:key,'Parceiro sintético','FORNECEDOR','BR',true)"""),
            values,
        )
    return values


@pytest.fixture
def physical_case(db_runtime, scope_ids, admin):
    from tests.helpers import select_context

    case = {"scopes": scope_ids, "contexts": {}, "records": {}}
    for suffix in ("a", "a2", "b"):
        case["contexts"][suffix] = select_context(
            admin, scope_ids[f"contract_{suffix}"]
        )["X-HiAtlas-Context"]
    with db_runtime.begin() as conn:
        for suffix in ("a", "a2", "b"):
            tenant = scope_ids["tenant_b" if suffix == "b" else "tenant_a"]
            case["records"][suffix] = seed_record(
                conn, case["contexts"][suffix], tenant, scope_ids[f"contract_{suffix}"]
            )
        case["partner_b"] = seed_record(
            conn,
            case["contexts"]["b"],
            scope_ids["tenant_b"],
            scope_ids["contract_b"],
            "PARTNERS",
            "PARTNER1",
        )
        case["other_a"] = seed_record(
            conn,
            case["contexts"]["a"],
            scope_ids["tenant_a"],
            scope_ids["contract_a"],
            key="P2",
        )
        from uuid import uuid4

        case["foreign_unit"] = uuid4()
        conn.execute(
            text(
                "INSERT INTO organization_nodes (id,tenant_id,contract_id,kind,name,code) VALUES (:id,:tenant,:contract,'UNIT','Unidade sintética B','UNIT1')"
            ),
            {
                "id": case["foreign_unit"],
                "tenant": scope_ids["tenant_b"],
                "contract": scope_ids["contract_b"],
            },
        )
        case["unit"] = uuid4()
        conn.execute(
            text("""INSERT INTO organization_nodes (id,tenant_id,contract_id,kind,name,code)
          VALUES (:id,:tenant,:contract,'UNIT','Unidade sintética','UNIT1')"""),
            {
                "id": case["unit"],
                "tenant": scope_ids["tenant_a"],
                "contract": scope_ids["contract_a"],
            },
        )
    return case


@pytest.mark.parametrize(
    "case",
    [
        "record_foreign_row",
        "record_wrong_dataset",
        "issue_wrong_import",
        "detail_wrong_kind",
        "foreign_product",
        "foreign_partner",
        "foreign_unit",
    ],
)
def test_physical_record_and_issue_scope_rejected(db_runtime, physical_case, case):
    from uuid import uuid4

    p = physical_case
    a = p["records"]["a"]
    b = p["records"]["b"]
    with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
        if case in {"record_foreign_row", "record_wrong_dataset"}:
            origin = b if case == "record_foreign_row" else a
            conn.execute(
                text("""INSERT INTO datahub_records
              (tenant_id,contract_id,dataset_code,business_key,fingerprint,source_import_id,source_file_id,source_row_id)
              VALUES (:tenant,:contract,:dataset,'SECOND',:digest,:import,:file,:row)"""),
                origin
                | {
                    "tenant": a["tenant"],
                    "contract": a["contract"],
                    "dataset": "STOCK_POSITIONS"
                    if case == "record_wrong_dataset"
                    else "PRODUCTS",
                },
            )
        elif case == "issue_wrong_import":
            conn.execute(
                text("""INSERT INTO datahub_import_issues
              (tenant_id,contract_id,import_id,import_row_id,severity,stable_error_code,message)
              VALUES (:tenant,:contract,:import,:row,'ERROR','INVALID_REFERENCE','Referência inválida')"""),
                a | {"row": p["other_a"]["row"]},
            )
        elif case == "detail_wrong_kind":
            conn.execute(
                text("""INSERT INTO datahub_stock_positions
              (record_id,tenant_id,contract_id,dataset_code,product_id,unit_id,quantidade_disponivel,data_referencia)
              VALUES (:record,:tenant,:contract,'PRODUCTS',:record,:unit,0,'2026-10-06')"""),
                a | {"unit": p["unit"]},
            )
        else:
            d = seed_record(
                conn,
                p["contexts"]["a"],
                a["tenant"],
                a["contract"],
                "COMEX_REFERENCES" if case == "foreign_partner" else "DEMANDS",
                str(uuid4()),
            )
            if case == "foreign_partner":
                conn.execute(
                    text("""INSERT INTO datahub_comex_references
                  (record_id,tenant_id,contract_id,dataset_code,codigo,partner_id,moeda,incoterm,data_prevista,status)
                  VALUES (:record,:tenant,:contract,:dataset,'CX1',:partner,'USD','FOB','2026-10-06','PLANEJADO')"""),
                    d | {"partner": p["partner_b"]["record"]},
                )
            else:
                conn.execute(
                    text("""INSERT INTO datahub_demands
                  (record_id,tenant_id,contract_id,dataset_code,codigo,product_id,unit_id,quantidade,data_necessidade,modalidade,prioridade)
                  VALUES (:record,:tenant,:contract,:dataset,'D1',:product,:unit,1,'2026-10-06','NACIONAL','NORMAL')"""),
                    d
                    | {
                        "product": b["record"]
                        if case == "foreign_product"
                        else a["record"],
                        "unit": p["foreign_unit"]
                        if case == "foreign_unit"
                        else p["unit"],
                    },
                )
    assert error.value.orig.sqlstate == (
        "23514" if case == "detail_wrong_kind" else "23503"
    )


def test_business_key_is_unique_within_contract_but_allowed_in_a2_b(
    db_runtime, physical_case
):
    p = physical_case
    a = p["records"]["a"]
    assert all(x["key"] == "P1" for x in p["records"].values())
    with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
        seed_record(conn, p["contexts"]["a"], a["tenant"], a["contract"], key="P1")
    assert error.value.orig.sqlstate == "23505"


def test_stock_tuple_has_physical_uniqueness(db_runtime, physical_case):
    p = physical_case
    a = p["records"]["a"]
    statement = text("""INSERT INTO datahub_stock_positions
      (record_id,tenant_id,contract_id,dataset_code,product_id,unit_id,quantidade_disponivel,data_referencia)
      VALUES (:record,:tenant,:contract,:dataset,:product,:unit,0,'2026-10-06')""")
    with db_runtime.begin() as conn:
        d = seed_record(
            conn,
            p["contexts"]["a"],
            a["tenant"],
            a["contract"],
            "STOCK_POSITIONS",
            "position-1",
        )
        conn.execute(statement, d | {"product": a["record"], "unit": p["unit"]})
    with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
        d = seed_record(
            conn,
            p["contexts"]["a"],
            a["tenant"],
            a["contract"],
            "STOCK_POSITIONS",
            "position-2",
        )
        conn.execute(statement, d | {"product": a["record"], "unit": p["unit"]})
    assert error.value.orig.sqlstate == "23505"


@pytest.mark.parametrize("unsafe", ["owner", "superuser", "missing"])
def test_incremental_datahub_migration_rejects_unsafe_runtime(
    db_owner, db_runtime, migration_config, unsafe
):
    from alembic import command

    good = migration_config.attributes["runtime_role"]
    try:
        with db_owner.begin() as conn:
            migration_config.attributes["connection"] = conn
            command.downgrade(migration_config, "0010")
            bad = (
                db_owner.url.username
                if unsafe == "owner"
                else conn.execute(
                    text("SELECT rolname FROM pg_roles WHERE rolsuper LIMIT 1")
                ).scalar_one()
                if unsafe == "superuser"
                else None
            )
            migration_config.attributes["runtime_role"] = bad
            with pytest.raises(RuntimeError, match="role"):
                command.upgrade(migration_config, "0011")
            assert not TABLES & set(inspect(conn).get_table_names())
            migration_config.attributes["runtime_role"] = good
            command.upgrade(migration_config, "head")
    finally:
        migration_config.attributes.pop("connection", None)
        migration_config.attributes["runtime_role"] = good


@pytest.mark.parametrize("case", ["foreign_unit", "missing_version", "invalid_version"])
def test_preview_unit_binding_is_physically_scoped(db_runtime, physical_case, case):
    p = physical_case
    record = p["records"]["a"]
    with pytest.raises(DBAPIError) as error, db_runtime.begin() as conn:
        conn.execute(
            text(
                "UPDATE datahub_import_rows SET unit_id=:unit, unit_version=:version WHERE id=:row"
            ),
            {
                "unit": p["foreign_unit"] if case == "foreign_unit" else p["unit"],
                "version": None
                if case == "missing_version"
                else 0
                if case == "invalid_version"
                else 1,
                "row": record["row"],
            },
        )
    assert error.value.orig.sqlstate == ("23503" if case == "foreign_unit" else "23514")

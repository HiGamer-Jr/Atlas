from datetime import UTC, datetime
from importlib.util import find_spec
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.datahub.models import (
    DataHubImport,
    DataHubImportRow,
    DataHubProduct,
    DataHubRecord,
)
from tests.test_datahub_policy import context_values
from tests.test_datahub_preview import policy_configured as _policy_fixture
from tests.test_datahub_preview import preview_case as _preview_case_fixture
from tests.test_datahub_preview import product, upload

preview_case = _preview_case_fixture
policy_configured = _policy_fixture


def confirmation_service():
    from app.datahub import services

    assert hasattr(services, "confirm_import"), "Atomic confirmation service missing"
    return services.confirm_import


def confirm(
    engine,
    case,
    preview,
    *,
    key=None,
    version=None,
    clock=None,
    header=None,
    enabled=True,
    orchestrated=False,
):
    from app.datahub import schemas

    assert hasattr(schemas, "ConfirmationInput"), "Closed confirmation contract missing"
    from cryptography.fernet import Fernet

    settings = Settings(
        datahub_enabled=enabled,
        datahub_raw_root=case[2] / "raw",
        datahub_raw_key=Fernet.generate_key().decode(),
    )
    request = Request(
        {
            "type": "http",
            "headers": [],
            "state": {"request_id": uuid4()},
            "app": SimpleNamespace(state=SimpleNamespace(settings=settings)),
        }
    )
    if orchestrated:
        assert find_spec("app.datahub.confirmation"), (
            "Confirmation Unit of Work missing"
        )
        from app.datahub.confirmation import ConfirmationOrchestrator

        request.app.state.clock = clock or (lambda: datetime.now(UTC))
        with Session(engine) as db:
            principal, scope = context_values(db, header or case[1])
        return ConfirmationOrchestrator(engine, request).run(
            principal,
            scope,
            preview.id,
            schemas.ConfirmationInput(
                expected_version=version or preview.version,
                idempotency_key=key or uuid4(),
            ),
        )
    with Session(engine) as db, db.begin():
        principal, scope = context_values(db, header or case[1])
        db.info.update(settings=settings, clock=clock or (lambda: datetime.now(UTC)))
        return confirmation_service()(
            db,
            request,
            principal,
            scope,
            preview.id,
            schemas.ConfirmationInput(
                expected_version=version or preview.version,
                idempotency_key=key or uuid4(),
            ),
        )


def count(engine, cls):
    with Session(engine) as db:
        return db.scalar(select(func.count()).select_from(cls))


def test_confirm_requires_bound_preview(preview_case, db_runtime):
    confirmation_service()
    from app.datahub.schemas import ImportSummary

    missing = ImportSummary(
        id=uuid4(),
        status="READY_FOR_CONFIRMATION",
        version=3,
        template_id="COMPRADOR_NACIONAL",
        template_version=1,
        row_count=1,
        error_count=0,
        warning_count=0,
        inserted_count=0,
        skipped_count=0,
        preview_expires_at=datetime.now(UTC),
        result_code="PREVIEW_READY",
    )
    with pytest.raises(ApiError) as error:
        confirm(db_runtime, preview_case, missing)
    assert error.value.status == 404
    assert count(db_runtime, DataHubRecord) == 0


def test_confirmation_inserts_typed_records_and_provenance(preview_case, db_runtime):
    preview = upload(db_runtime, preview_case, (product(),))
    result = confirm(db_runtime, preview_case, preview)
    assert result.status == "COMMITTED"
    assert result.inserted_count == 1
    with Session(db_runtime) as db:
        record = db.scalar(select(DataHubRecord))
        row = db.scalar(select(DataHubImportRow))
        assert record.source_import_id == preview.id
        assert record.source_row_id == row.id
        assert row.record_id == record.id
        detail = db.scalar(select(DataHubProduct))
        assert detail.codigo == "000123"
        assert detail.categoria == ""


def test_same_command_replay_has_one_effect(preview_case, db_runtime):
    preview = upload(db_runtime, preview_case, (product(),))
    key = uuid4()
    result = confirm(db_runtime, preview_case, preview, key=key)
    replay = confirm(db_runtime, preview_case, preview, key=key)
    assert result == replay
    assert count(db_runtime, DataHubRecord) == 1
    from app.audit.models import AuditEvent

    with Session(db_runtime) as db:
        assert (
            len(
                list(
                    db.scalars(
                        select(AuditEvent).where(
                            AuditEvent.action == "datahub.import.committed"
                        )
                    )
                )
            )
            == 1
        )
    with pytest.raises(ApiError) as error:
        confirm(db_runtime, preview_case, preview, key=uuid4())
    assert error.value.status == 409


def test_all_skipped_can_commit(preview_case, db_runtime):
    first = upload(db_runtime, preview_case, (product(),))
    confirm(db_runtime, preview_case, first)
    second = upload(db_runtime, preview_case, (product(),))
    assert second.status == "READY_FOR_CONFIRMATION"
    assert second.skipped_count == 1
    result = confirm(db_runtime, preview_case, second)
    assert result.inserted_count == 0 and result.skipped_count == 1
    assert count(db_runtime, DataHubRecord) == 1


def test_audit_failure_rolls_back(preview_case, db_runtime, monkeypatch):
    from app.audit import service as audit_module

    preview = upload(db_runtime, preview_case, (product(),))
    original = audit_module.append_event

    def fail_commit(db, event):
        if event.action == "datahub.import.committed":
            raise RuntimeError("synthetic audit failure")
        return original(db, event)

    monkeypatch.setattr(audit_module, "append_event", fail_commit)
    with pytest.raises(RuntimeError):
        confirm(db_runtime, preview_case, preview)
    assert count(db_runtime, DataHubRecord) == 0
    with Session(db_runtime) as db:
        assert db.get(DataHubImport, preview.id).status == "READY_FOR_CONFIRMATION"
        assert db.scalar(select(DataHubImportRow)).record_id is None


@pytest.mark.parametrize(
    "cause",
    [
        "rejected",
        "expired",
        "version",
        "dataset_revoked",
        "unit_removed",
        "new_context",
    ],
)
def test_confirmation_rechecks_current_authority(
    preview_case, db_runtime, member, cause
):
    from tests.helpers import select_context

    preview = upload(
        db_runtime, preview_case, () if cause == "rejected" else (product(),)
    )
    clock, version, header = None, None, None
    if cause == "expired":
        with db_runtime.begin() as conn:
            conn.execute(
                text(
                    "UPDATE datahub_imports SET preview_expires_at=created_at+interval '1 millisecond' WHERE id=:id"
                ),
                {"id": preview.id},
            )
    elif cause == "version":
        version = preview.version + 1
    elif cause == "dataset_revoked":
        with db_runtime.begin() as conn:
            conn.execute(
                text(
                    "UPDATE tenant_role_permissions SET active=false WHERE role_id=:r AND capability='datahub.products.import'"
                ),
                {"r": preview_case[0]["role_basic"]},
            )
    elif cause == "unit_removed":
        with db_runtime.begin() as conn:
            conn.execute(
                text("UPDATE memberships SET blocked=true WHERE id=:m"),
                {"m": preview_case[0]["member_a"]},
            )
    elif cause == "new_context":
        header = select_context(member, preview_case[0]["contract_a"])
    with pytest.raises(ApiError) as error:
        confirm(
            db_runtime,
            preview_case,
            preview,
            clock=clock,
            version=version,
            header=header,
        )
    assert error.value.status in (401, 403, 404, 409)
    assert count(db_runtime, DataHubRecord) == 0


def test_commit_five_nonfinancial_datasets_with_forward_references(
    preview_case, db_runtime
):
    from dataclasses import replace
    from datetime import date

    from app.datahub.models import (
        DataHubComexReference,
        DataHubDemand,
        DataHubPartner,
        DataHubStockPosition,
    )
    from app.datahub.schemas import (
        ComexPayload,
        DemandPayload,
        PartnerPayload,
        StockPayload,
    )
    from app.datahub.types import NormalizedRow
    from tests.test_datahub_policy import invoke

    with db_runtime.begin() as c:
        for cap in ("datahub.comex_references.read", "datahub.comex_references.import"):
            c.execute(
                text(
                    "INSERT INTO tenant_role_permissions (tenant_id,contract_id,role_id,capability) VALUES (:t,:c,:r,:p)"
                ),
                {
                    "t": preview_case[0]["tenant_a"],
                    "c": preview_case[0]["contract_a"],
                    "r": preview_case[0]["role_basic"],
                    "p": cap,
                },
            )
    selection = replace(
        invoke(db_runtime, preview_case[1], "COORDENACAO"),
        datasets=(
            "DEMANDS",
            "STOCK_POSITIONS",
            "COMEX_REFERENCES",
            "PRODUCTS",
            "PARTNERS",
        ),
    )
    rows = (
        NormalizedRow(
            "DEMANDS",
            1,
            "Demandas",
            13,
            DemandPayload(
                codigo="DEM-SYN",
                produto_codigo="000123",
                unidade_codigo="DH-UNIT",
                quantidade="12.5000",
                data_necessidade=date(2026, 10, 20),
                modalidade="NACIONAL",
                prioridade="NORMAL",
            ),
        ),
        NormalizedRow(
            "STOCK_POSITIONS",
            1,
            "Estoque",
            13,
            StockPayload(
                produto_codigo="000123",
                unidade_codigo="DH-UNIT",
                quantidade_disponivel="12.5000",
                data_referencia=date(2026, 10, 7),
            ),
        ),
        NormalizedRow(
            "COMEX_REFERENCES",
            1,
            "COMEX",
            13,
            ComexPayload(
                codigo="COMEX-SYN",
                parceiro_codigo="PART-SYN",
                moeda="USD",
                incoterm="FOB",
                data_prevista=date(2026, 10, 20),
                status="PLANEJADO",
            ),
        ),
        product(),
        NormalizedRow(
            "PARTNERS",
            1,
            "Parceiros",
            13,
            PartnerPayload(
                codigo="PART-SYN",
                nome="Fornecedor sintético",
                tipo="FORNECEDOR",
                pais_iso="BR",
                ativo=True,
            ),
        ),
    )
    preview = upload(db_runtime, preview_case, rows, selection=selection)
    assert preview.status == "READY_FOR_CONFIRMATION"
    result = confirm(db_runtime, preview_case, preview)
    assert result.inserted_count == 5
    for cls in (
        DataHubProduct,
        DataHubPartner,
        DataHubDemand,
        DataHubStockPosition,
        DataHubComexReference,
    ):
        assert count(db_runtime, cls) == 1
    with Session(db_runtime) as db:
        stock = db.scalar(select(DataHubStockPosition))
        demand = db.scalar(select(DataHubDemand))
        assert stock.product_id == demand.product_id
        assert stock.unit_id == preview_case[0]["datahub_unit"]
        assert str(stock.quantidade_disponivel) == "12.5000"
    repeated = upload(db_runtime, preview_case, rows, selection=selection)
    result = confirm(db_runtime, preview_case, repeated)
    assert result.inserted_count == 0 and result.skipped_count == 5


def test_post_preview_conflict_does_not_overwrite(preview_case, db_runtime):
    first = upload(db_runtime, preview_case, (product(),))
    second = upload(
        db_runtime, preview_case, (product(description="Outra descrição sintética"),)
    )
    confirm(db_runtime, preview_case, first)
    with pytest.raises(ApiError) as error:
        confirm(db_runtime, preview_case, second)
    assert error.value.status == 409
    assert count(db_runtime, DataHubRecord) == 1
    with Session(db_runtime) as db:
        assert db.scalar(select(DataHubProduct)).descricao == "Produto sintético"
        assert db.get(DataHubImport, second.id).status == "READY_FOR_CONFIRMATION"


def test_replay_rechecks_dataset_read(preview_case, db_runtime):
    preview = upload(db_runtime, preview_case, (product(),))
    key = uuid4()
    confirm(db_runtime, preview_case, preview, key=key)
    with db_runtime.begin() as c:
        c.execute(
            text(
                "UPDATE tenant_role_permissions SET active=false WHERE role_id=:r AND capability='datahub.products.read'"
            ),
            {"r": preview_case[0]["role_basic"]},
        )
    with pytest.raises(ApiError) as error:
        confirm(db_runtime, preview_case, preview, key=key)
    assert error.value.status == 403


@pytest.mark.parametrize("change", ["version", "scope", "module"])
def test_unit_and_module_changes_reject_pending_stock(preview_case, db_runtime, change):
    from datetime import date

    from app.datahub.schemas import StockPayload
    from app.datahub.types import NormalizedRow
    from tests.test_datahub_policy import invoke

    stock = NormalizedRow(
        "STOCK_POSITIONS",
        1,
        "Estoque",
        13,
        StockPayload(
            produto_codigo="000123",
            unidade_codigo="DH-UNIT",
            quantidade_disponivel="1",
            data_referencia=date(2026, 10, 7),
        ),
    )
    preview = upload(
        db_runtime,
        preview_case,
        (product(), stock),
        selection=invoke(db_runtime, preview_case[1], "CENTRO_DISTRIBUICAO"),
    )
    with db_runtime.begin() as c:
        if change == "version":
            c.execute(
                text("UPDATE organization_nodes SET version=version+1 WHERE id=:n"),
                {"n": preview_case[0]["datahub_unit"]},
            )
        elif change == "scope":
            c.execute(
                text(
                    "UPDATE membership_unit_scopes SET active=false WHERE membership_id=:m"
                ),
                {"m": preview_case[0]["member_a"]},
            )
        else:
            c.execute(
                text(
                    "UPDATE contract_modules SET active=false WHERE contract_id=:c AND code='INVENTORY'"
                ),
                {"c": preview_case[0]["contract_a"]},
            )
    with pytest.raises(ApiError) as error:
        confirm(db_runtime, preview_case, preview)
    assert error.value.status in (403, 409)
    assert count(db_runtime, DataHubRecord) == 0


def test_confirmation_fails_closed_when_feature_disabled(preview_case, db_runtime):
    preview = upload(db_runtime, preview_case, (product(),))
    with pytest.raises(ApiError) as error:
        confirm(db_runtime, preview_case, preview, enabled=False)
    assert error.value.status == 503
    assert count(db_runtime, DataHubRecord) == 0


@pytest.mark.parametrize("audit_available", [True, False])
def test_confirmation_failure_has_independent_atomic_status(
    preview_case, db_runtime, monkeypatch, audit_available
):
    from app.audit import service as audit_module

    preview = upload(db_runtime, preview_case, (product(),))
    original = audit_module.append_event

    def unavailable(db, event):
        if event.action == "datahub.import.committed" or (
            not audit_available and event.action == "datahub.import.failed"
        ):
            raise RuntimeError("synthetic sensitive audit failure")
        return original(db, event)

    monkeypatch.setattr(audit_module, "append_event", unavailable)
    with pytest.raises(ApiError) as error:
        confirm(db_runtime, preview_case, preview, orchestrated=True)
    assert error.value.code == "DATAHUB_CONFIRMATION_FAILED"
    assert "sensitive" not in error.value.message
    assert count(db_runtime, DataHubRecord) == 0
    with Session(db_runtime) as db:
        row = db.get(DataHubImport, preview.id)
        assert row.status == ("FAILED" if audit_available else "READY_FOR_CONFIRMATION")
        assert db.scalar(select(DataHubImportRow)).record_id is None


def test_hidden_unit_business_key_collision_is_sanitized_conflict(
    preview_case, db_runtime
):
    from datetime import date

    from app.datahub.schemas import DemandPayload
    from app.datahub.types import NormalizedRow
    from tests.test_datahub_policy import invoke

    demand = NormalizedRow(
        "DEMANDS",
        1,
        "Demandas",
        13,
        DemandPayload(
            codigo="DEM-SYN",
            produto_codigo="000123",
            unidade_codigo="DH-UNIT",
            quantidade="1",
            data_necessidade=date(2026, 10, 20),
            modalidade="NACIONAL",
            prioridade="NORMAL",
        ),
    )
    first = upload(db_runtime, preview_case, (product(), demand))
    confirm(db_runtime, preview_case, first)
    new_unit = uuid4()
    ids = preview_case[0]
    with db_runtime.begin() as c:
        c.execute(
            text(
                "INSERT INTO organization_nodes (id,tenant_id,contract_id,kind,name,code) VALUES (:n,:t,:c,'STORE','Outra unidade sintética','UNIT-TWO')"
            ),
            {"n": new_unit, "t": ids["tenant_a"], "c": ids["contract_a"]},
        )
        c.execute(
            text(
                "UPDATE membership_unit_scopes SET active=false WHERE membership_id=:m"
            ),
            {"m": ids["member_a"]},
        )
        c.execute(
            text(
                "INSERT INTO membership_unit_scopes (tenant_id,contract_id,membership_id,node_id) VALUES (:t,:c,:m,:n)"
            ),
            {
                "t": ids["tenant_a"],
                "c": ids["contract_a"],
                "m": ids["member_a"],
                "n": new_unit,
            },
        )
    demand = NormalizedRow(
        "DEMANDS",
        1,
        "Demandas",
        13,
        demand.payload.model_copy(update={"unidade_codigo": "UNIT-TWO"}),
    )
    second = upload(
        db_runtime,
        preview_case,
        (demand,),
        selection=invoke(db_runtime, preview_case[1], "COMPRADOR_NACIONAL"),
    )
    assert second.status == "READY_FOR_CONFIRMATION"
    with pytest.raises(ApiError) as error:
        confirm(db_runtime, preview_case, second)
    assert error.value.status == 409
    assert (
        "UNIT" not in error.value.message and str(first.id) not in error.value.message
    )
    assert count(db_runtime, DataHubRecord) == 2

from dataclasses import replace
from datetime import UTC, date, datetime
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.datahub.models import (
    DataHubImportIssue,
    DataHubImportRow,
    DataHubRecord,
)
from app.datahub.schemas import DemandPayload, ProductPayload
from app.datahub.types import NormalizedRow, WorkbookContext
from tests.helpers import select_context
from tests.test_datahub_policy import (
    configured as _configured_fixture,
)
from tests.test_datahub_policy import (
    context_values,
    grant_caps,
    invoke,
)

policy_configured = _configured_fixture


def service():
    assert find_spec("app.datahub.services"), "Persistent preview service missing"
    from app.datahub.services import create_preview

    return create_preview


def store_type():
    assert find_spec("app.datahub.raw_store"), "Private encrypted RawStore missing"
    from app.datahub.raw_store import RawStore

    return RawStore


@pytest.fixture
def preview_case(member, policy_configured, db_runtime, tmp_path):
    grant_caps(db_runtime, policy_configured)
    header = select_context(member, policy_configured["contract_a"])
    return policy_configured, header, tmp_path


def upload(
    engine,
    case,
    rows=(),
    *,
    selection=None,
    filename="synthetic.xlsx",
    content=None,
    orchestrated=False,
    settings_overrides=None,
):
    from app.datahub.connectors.excel import ExcelConnector

    _ids, header, path = case
    selection = selection or invoke(engine, header, "COMPRADOR_NACIONAL")
    connector = ExcelConnector(
        Path(__file__).resolve().parents[2] / "frontend/src/assets/hiatlas-light.png"
    )
    content = (
        content
        if content is not None
        else connector.generate(
            selection,
            WorkbookContext(
                "Empresa sintética",
                "SYN-001",
                "Perfil sintético",
                "DH-UNIT",
                datetime.now(UTC),
            ),
            rows,
        )
    )
    settings = Settings(
        datahub_enabled=True,
        datahub_raw_root=path / "raw",
        datahub_raw_key=Fernet.generate_key().decode(),
        **(settings_overrides or {}),
    )
    request = Request(
        {
            "type": "http",
            "app": SimpleNamespace(
                state=SimpleNamespace(
                    settings=settings,
                    datahub_connector=connector,
                    datahub_raw_store=store_type()(settings),
                )
            ),
            "headers": [],
            "state": {"request_id": uuid4()},
        }
    )
    if orchestrated:
        assert find_spec("app.datahub.preview"), (
            "Multi-phase preview orchestration missing"
        )
        from app.datahub.preview import PreviewOrchestrator

        with Session(engine) as db:
            principal, scope = context_values(db, header)
        return PreviewOrchestrator(engine, request).run(
            principal, scope, filename, content
        )
    with Session(engine) as db, db.begin():
        principal, scope = context_values(db, header)
        db.info.update(settings=settings, clock=lambda: datetime.now(UTC))
        return service()(db, request, principal, scope, filename, content)


def product(code="000123", description="Produto sintético"):
    return NormalizedRow(
        "PRODUCTS",
        1,
        "Produtos",
        13,
        ProductPayload(
            codigo=code, descricao=description, unidade_medida="UN", ativo=True
        ),
    )


def codes(engine, import_id):
    with Session(engine) as db:
        return set(
            db.scalars(
                select(DataHubImportIssue.stable_error_code).where(
                    DataHubImportIssue.import_id == import_id
                )
            )
        )


def test_preview_writes_no_records(preview_case, db_runtime):
    result = upload(db_runtime, preview_case, (product(),))
    assert result.status == "READY_FOR_CONFIRMATION"
    assert result.row_count == 1
    with Session(db_runtime) as db:
        assert db.scalar(select(func.count()).select_from(DataHubRecord)) == 0
        row = db.scalar(
            select(DataHubImportRow).where(DataHubImportRow.import_id == result.id)
        )
        assert row.normalized_payload["codigo"] == "000123"
        assert row.normalized_payload["categoria"] == ""


def test_empty_import_rejected(preview_case, db_runtime):
    result = upload(db_runtime, preview_case)
    assert result.status == "REJECTED"
    assert "EMPTY_IMPORT" in codes(db_runtime, result.id)


def test_forward_reference_resolves(preview_case, db_runtime):
    selection = replace(
        invoke(db_runtime, preview_case[1], "COMPRADOR_NACIONAL"),
        datasets=("DEMANDS", "PRODUCTS"),
    )
    demand = NormalizedRow(
        "DEMANDS",
        1,
        "Demandas",
        13,
        DemandPayload(
            codigo="DEM-SYN",
            produto_codigo="000123",
            unidade_codigo="DH-UNIT",
            quantidade="1.0000",
            data_necessidade=date(2026, 10, 20),
            modalidade="NACIONAL",
            prioridade="NORMAL",
        ),
    )
    result = upload(db_runtime, preview_case, (demand, product()), selection=selection)
    assert result.status == "READY_FOR_CONFIRMATION"
    with Session(db_runtime) as db:
        row = db.scalar(
            select(DataHubImportRow).where(
                DataHubImportRow.import_id == result.id,
                DataHubImportRow.dataset_code == "DEMANDS",
            )
        )
        assert row.unit_id == preview_case[0]["datahub_unit"]
        assert row.unit_version == 1


def test_existing_changed_key_is_error(preview_case, db_runtime):
    from tests.test_datahub_schema import seed_record

    with db_runtime.begin() as conn:
        seed_record(
            conn,
            preview_case[1]["X-HiAtlas-Context"],
            preview_case[0]["tenant_a"],
            preview_case[0]["contract_a"],
            key="000123",
        )
    result = upload(
        db_runtime, preview_case, (product(description="Outra descrição sintética"),)
    )
    assert result.status == "REJECTED"
    assert "DUPLICATE_CONFLICT" in codes(db_runtime, result.id)


def test_intra_file_identical_is_warning(preview_case, db_runtime):
    result = upload(db_runtime, preview_case, (product(), product()))
    assert result.status == "READY_FOR_CONFIRMATION"
    assert result.warning_count == 1
    assert "DUPLICATE_IDENTICAL" in codes(db_runtime, result.id)


def test_intra_file_changed_key_rejected(preview_case, db_runtime):
    result = upload(
        db_runtime,
        preview_case,
        (product(), product(description="Outra descrição sintética")),
    )
    assert result.status == "REJECTED"
    assert "DUPLICATE_CONFLICT" in codes(db_runtime, result.id)


def test_raw_not_public_and_key_missing_fails_closed(tmp_path):
    raw_type = store_type()
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(datahub_enabled=True, datahub_raw_root=tmp_path / "private")
    key = Fernet.generate_key().decode()
    settings = Settings(
        datahub_enabled=True, datahub_raw_key=key, datahub_raw_root=tmp_path / "private"
    )
    store = raw_type(settings)
    reference = store.put(uuid4(), b"synthetic private bytes")
    files = list((tmp_path / "private").glob("*.enc"))
    assert len(files) == 1
    assert b"synthetic private bytes" not in files[0].read_bytes()
    assert (
        Fernet(key.encode()).decrypt(files[0].read_bytes())
        == b"synthetic private bytes"
    )
    store.remove(reference)
    store.remove(reference)
    assert not files[0].exists()


def test_raw_public_directory_is_rejected(tmp_path):
    store_type()
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(
            datahub_enabled=True,
            datahub_raw_key=Fernet.generate_key().decode(),
            datahub_raw_root=Path(__file__).resolve().parents[2] / "frontend/public",
        )


def test_raw_collision_does_not_delete_existing_file(tmp_path, monkeypatch):
    raw_type = store_type()
    import app.datahub.raw_store as raw_module
    from app.core.errors import ApiError

    key = Fernet.generate_key().decode()
    settings = Settings(
        datahub_enabled=True, datahub_raw_key=key, datahub_raw_root=tmp_path / "private"
    )
    store = raw_type(settings)
    identity = uuid4()
    existing = tmp_path / "private" / f"{identity}.enc"
    existing.write_bytes(b"existing synthetic ciphertext")
    monkeypatch.setattr(raw_module, "uuid4", lambda: identity)
    with pytest.raises(ApiError):
        store.put(uuid4(), b"new synthetic bytes")
    assert existing.read_bytes() == b"existing synthetic ciphertext"


def test_preview_audit_failure_rolls_back_and_removes_raw(
    preview_case, db_runtime, monkeypatch
):
    from app.audit import service as audit_module

    def fail_audit(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(audit_module, "append_event", fail_audit)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        upload(db_runtime, preview_case, (product(),))
    from app.datahub.models import DataHubImport

    with Session(db_runtime) as db:
        assert db.scalar(select(func.count()).select_from(DataHubImport)) == 0
    assert not list((preview_case[2] / "raw").glob("*.enc"))


def test_committed_raw_survives_later_session_rollback(preview_case, db_runtime):
    from app.datahub.connectors.excel import ExcelConnector
    from app.datahub.raw_store import RawStore

    selection = invoke(db_runtime, preview_case[1], "COMPRADOR_NACIONAL")
    connector = ExcelConnector(
        Path(__file__).resolve().parents[2] / "frontend/src/assets/hiatlas-light.png"
    )
    content = connector.generate(
        selection,
        WorkbookContext(
            "Empresa sintética",
            "SYN-001",
            "Perfil sintético",
            "DH-UNIT",
            datetime.now(UTC),
        ),
        (product(),),
    )
    settings = Settings(
        datahub_enabled=True,
        datahub_raw_root=preview_case[2] / "raw",
        datahub_raw_key=Fernet.generate_key().decode(),
    )
    request = Request(
        {
            "type": "http",
            "app": SimpleNamespace(
                state=SimpleNamespace(
                    settings=settings,
                    datahub_connector=connector,
                    datahub_raw_store=RawStore(settings),
                )
            ),
            "headers": [],
            "state": {"request_id": uuid4()},
        }
    )
    with Session(db_runtime) as db:
        db.info.update(settings=settings, clock=lambda: datetime.now(UTC))
        with db.begin():
            principal, scope = context_values(db, preview_case[1])
            service()(db, request, principal, scope, "synthetic.xlsx", content)
        with pytest.raises(RuntimeError), db.begin():
            raise RuntimeError("later transaction")
    assert len(list((preview_case[2] / "raw").glob("*.enc"))) == 1


def test_orchestrator_commits_validating_before_validation(
    preview_case, db_runtime, monkeypatch
):
    from app.datahub import services
    from app.datahub.models import DataHubImport

    original = services.validate_rows
    observed = []

    def inspect_receipt(db, selection, parsed):
        with Session(db_runtime) as other:
            rows = list(other.scalars(select(DataHubImport)))
            observed.append([r.status for r in rows])
            assert other.scalar(select(func.count()).select_from(DataHubRecord)) == 0
        return original(db, selection, parsed)

    monkeypatch.setattr(services, "validate_rows", inspect_receipt)
    result = upload(db_runtime, preview_case, (product(),), orchestrated=True)
    assert observed == [["VALIDATING"]]
    assert result.status == "READY_FOR_CONFIRMATION"


@pytest.mark.parametrize("audit_remains_unavailable", [False, True])
def test_orchestrator_failure_keeps_no_partial_rows(
    preview_case, db_runtime, monkeypatch, audit_remains_unavailable
):
    from app.audit import service as audit_module
    from app.core.errors import ApiError
    from app.datahub.models import DataHubImport

    original = audit_module.append_event

    def fail_final_audit(db, event):
        if event.action == "datahub.import.validated" or (
            audit_remains_unavailable and event.action == "datahub.import.failed"
        ):
            raise RuntimeError("synthetic sensitive failure payload")
        return original(db, event)

    monkeypatch.setattr(audit_module, "append_event", fail_final_audit)
    with pytest.raises(ApiError) as error:
        upload(db_runtime, preview_case, (product(),), orchestrated=True)
    assert error.value.code == "DATAHUB_ANALYSIS_FAILED"
    assert "sensitive" not in error.value.message
    with Session(db_runtime) as db:
        row = db.scalar(select(DataHubImport))
        assert row.status == ("VALIDATING" if audit_remains_unavailable else "FAILED")
        assert db.scalar(select(func.count()).select_from(DataHubImportRow)) == 0
        assert db.scalar(select(func.count()).select_from(DataHubRecord)) == 0


def test_formula_issue_does_not_persist_raw_value(preview_case, db_runtime):
    from app.datahub.connectors.excel import ExcelConnector
    from tests.test_datahub_excel import edit

    selection = invoke(db_runtime, preview_case[1], "COMPRADOR_NACIONAL")
    excel = ExcelConnector(
        Path(__file__).resolve().parents[2] / "frontend/src/assets/hiatlas-light.png"
    )
    content = excel.generate(
        selection,
        WorkbookContext(
            "Empresa sintética",
            "SYN-001",
            "Perfil sintético",
            "DH-UNIT",
            datetime.now(UTC),
        ),
        (product(),),
    )
    content = edit(content, "Produtos", "B13", "=SYNTHETIC_SECRET()")
    result = upload(db_runtime, preview_case, content=content)
    assert result.status == "REJECTED"
    assert "FORMULA_NOT_ALLOWED" in codes(db_runtime, result.id)
    with Session(db_runtime) as db:
        row = db.scalar(
            select(DataHubImportRow).where(DataHubImportRow.import_id == result.id)
        )
        issues = list(
            db.scalars(
                select(DataHubImportIssue).where(
                    DataHubImportIssue.import_id == result.id
                )
            )
        )
        assert "SYNTHETIC_SECRET" not in str(row.normalized_payload)
        assert all("SYNTHETIC_SECRET" not in i.message for i in issues)


def test_missing_reference_is_neutral(preview_case, db_runtime):
    demand = NormalizedRow(
        "DEMANDS",
        1,
        "Demandas",
        13,
        DemandPayload(
            codigo="DEM-SYN",
            produto_codigo="FOREIGN-PRODUCT",
            unidade_codigo="DH-UNIT",
            quantidade="1",
            data_necessidade=date(2026, 10, 20),
            modalidade="NACIONAL",
            prioridade="NORMAL",
        ),
    )
    result = upload(db_runtime, preview_case, (demand,))
    assert result.status == "REJECTED"
    assert "REFERENCE_UNAVAILABLE" in codes(db_runtime, result.id)
    with Session(db_runtime) as db:
        messages = list(
            db.scalars(
                select(DataHubImportIssue.message).where(
                    DataHubImportIssue.import_id == result.id
                )
            )
        )
        assert all("FOREIGN-PRODUCT" not in m for m in messages)


def test_preview_expiring_during_validation_never_ready(
    preview_case, db_runtime, monkeypatch
):
    from datetime import timedelta

    from app.datahub import services

    original = services.validate_rows

    def crosses_expiry(db, selection, parsed):
        result = original(db, selection, parsed)
        clock = datetime.now(UTC) + timedelta(seconds=2)
        db.info["clock"] = lambda: clock
        return result

    monkeypatch.setattr(services, "validate_rows", crosses_expiry)
    result = upload(
        db_runtime,
        preview_case,
        (product(),),
        settings_overrides={"datahub_limits": {"preview_seconds": 1}},
    )
    assert result.status == "EXPIRED"
    assert result.result_code == "PREVIEW_EXPIRED"


def test_failed_analysis_audit_has_failure_outcome(
    preview_case, db_runtime, monkeypatch
):
    from app.audit.models import AuditEvent
    from app.core.errors import ApiError
    from app.datahub import services

    def fail_validation(*args):
        raise RuntimeError("synthetic validation failure")

    monkeypatch.setattr(services, "validate_rows", fail_validation)
    with pytest.raises(ApiError):
        upload(db_runtime, preview_case, (product(),), orchestrated=True)
    with Session(db_runtime) as db:
        event = db.scalar(
            select(AuditEvent).where(AuditEvent.action == "datahub.import.failed")
        )
        assert event.outcome == "FAILURE"


def test_foreign_valid_product_reference_is_neutral(admin, preview_case, db_runtime):
    from tests.test_datahub_schema import seed_record

    ids = preview_case[0]
    foreign_context = select_context(admin, ids["contract_a2"])
    with db_runtime.begin() as conn:
        seed_record(
            conn,
            foreign_context["X-HiAtlas-Context"],
            ids["tenant_a"],
            ids["contract_a2"],
            key="FOREIGN-PRODUCT",
        )
    demand = NormalizedRow(
        "DEMANDS",
        1,
        "Demandas",
        13,
        DemandPayload(
            codigo="DEM-SYN",
            produto_codigo="FOREIGN-PRODUCT",
            unidade_codigo="DH-UNIT",
            quantidade="1",
            data_necessidade=date(2026, 10, 20),
            modalidade="NACIONAL",
            prioridade="NORMAL",
        ),
    )
    result = upload(db_runtime, preview_case, (demand,))
    assert result.status == "REJECTED"
    assert codes(db_runtime, result.id) == {"REFERENCE_UNAVAILABLE"}


def test_unassigned_unit_text_never_binds_an_id(preview_case, db_runtime):
    from app.datahub.connectors.excel import ExcelConnector
    from tests.test_datahub_excel import edit

    selection = invoke(db_runtime, preview_case[1], "COMPRADOR_NACIONAL")
    excel = ExcelConnector(
        Path(__file__).resolve().parents[2] / "frontend/src/assets/hiatlas-light.png"
    )
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
    content = excel.generate(
        selection,
        WorkbookContext(
            "Empresa sintética",
            "SYN-001",
            "Perfil sintético",
            "DH-UNIT",
            datetime.now(UTC),
        ),
        (product(), demand),
    )
    content = edit(content, "Demandas", "C13", "FOREIGN-UNIT")
    result = upload(db_runtime, preview_case, content=content)
    assert result.status == "REJECTED"
    with Session(db_runtime) as db:
        row = db.scalar(
            select(DataHubImportRow).where(
                DataHubImportRow.import_id == result.id,
                DataHubImportRow.dataset_code == "DEMANDS",
            )
        )
        assert row.unit_id is None
        assert row.unit_version is None

from uuid import uuid4

import pytest
from sqlalchemy import text

from tests.fixtures.correction_domain import seed_fixture_run
from tests.helpers import CONTEXT_HEADER
from tests.test_grants import start


@pytest.fixture
def correction_case(app, admin, scope_ids, db_runtime):
    from tests.fixtures.correction_domain import register_fixture_action

    register_fixture_action(app)
    node = uuid4()
    with db_runtime.begin() as db:
        db.execute(
            text(
                "INSERT INTO organization_nodes(id,tenant_id,contract_id,kind,name,code) VALUES(:id,:tenant,:contract,'COMPANY','Original','PH10')"
            ),
            {
                "id": node,
                "tenant": scope_ids["tenant_a"],
                "contract": scope_ids["contract_a"],
            },
        )
    parent, response = start(
        admin,
        scope_ids,
        grant_type="MAINTENANCE",
        reference="SUP-TEST",
        scopes=[
            {
                "action_code": "FIXTURE_NODE_RENAME",
                "entity_type": "organization_node",
                "entity_id": str(node),
            }
        ],
    )
    assert response.status_code == 201
    child = {CONTEXT_HEADER: response.json()["context_id"]}
    return {
        "node": node,
        "parent": parent,
        "child": child,
        "grant": response.json(),
        "payload": {
            "action_code": "FIXTURE_NODE_RENAME",
            "entity_id": str(node),
            "expected_version": 1,
            "proposed_input": {"name": "Corrected"},
            "reason": "Controlled correction",
            "reference": "SUP-TEST",
        },
    }


@pytest.fixture
def processing_case(correction_case, db_runtime, scope_ids):
    case = correction_case
    case["run"] = seed_fixture_run(
        db_runtime,
        scope_ids,
        case["node"],
        {"context_id": case["parent"]["X-HiAtlas-Context"]},
    )
    case["retry"] = {
        "reason": "Repeat controlled run",
        "reference": "SUP-TEST",
        "idempotency_key": "retry-01",
        "expected_version": 1,
    }
    return case

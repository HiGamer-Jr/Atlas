"""Actual tenant contract, actor and unit records for purchase request persistence tests."""

from uuid import uuid4

import pytest
from sqlalchemy import text


@pytest.fixture
def purchase_case(db, scope_ids, auth_users):
    ids = dict(scope_ids)
    ids.update(
        user=auth_users["member_user"],
        node=uuid4(),
        foreign_node=uuid4(),
        request=uuid4(),
        other_request=uuid4(),
        item=uuid4(),
        other_item=uuid4(),
        audit=uuid4(),
    )
    for node, tenant, contract in [
        ("node", "tenant_a", "contract_a"),
        ("foreign_node", "tenant_b", "contract_b"),
    ]:
        db.execute(
            text(
                "INSERT INTO organization_nodes(id,tenant_id,contract_id,kind,name,code) VALUES (:id,:tenant,:contract,'UNIT','Actual unit',:code)"
            ),
            {
                "id": ids[node],
                "tenant": ids[tenant],
                "contract": ids[contract],
                "code": node.upper(),
            },
        )
    for key in ["request", "other_request"]:
        db.execute(
            text(
                "INSERT INTO purchase_requests(id,tenant_id,contract_id,requester_user_id,requester_membership_id,requesting_node_id,title) VALUES (:id,:tenant,:contract,:user,:member,:node,'Actual purchasing need')"
            ),
            {
                "id": ids[key],
                "tenant": ids["tenant_a"],
                "contract": ids["contract_a"],
                "user": ids["user"],
                "member": ids["member_a"],
                "node": ids["node"],
            },
        )
    for key, request in [("item", "request"), ("other_item", "other_request")]:
        db.execute(
            text(
                "INSERT INTO purchase_request_items(id,tenant_id,contract_id,request_id,position,description,requested_quantity,uom_code) VALUES (:id,:tenant,:contract,:request,1,'Actual item',1,'UN')"
            ),
            {
                "id": ids[key],
                "tenant": ids["tenant_a"],
                "contract": ids["contract_a"],
                "request": ids[request],
            },
        )
    db.execute(
        text(
            "INSERT INTO audit_events(id,tenant_id,contract_id,action,outcome,request_id) VALUES (:id,:tenant,:contract,'procurement.request.created','SUCCESS',:request)"
        ),
        {
            "id": ids["audit"],
            "tenant": ids["tenant_a"],
            "contract": ids["contract_a"],
            "request": uuid4(),
        },
    )
    return ids

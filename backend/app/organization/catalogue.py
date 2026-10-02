"""Closed physical kinds and server-owned containment matrix."""

from types import MappingProxyType

LABELS = MappingProxyType(
    {
        "COMPANY": "Empresa",
        "BRANCH": "Filial",
        "UNIT": "Unidade",
        "STORE": "Loja",
        "DISTRIBUTION_CENTER": "Centro de distribuição",
        "WAREHOUSE": "Depósito",
        "OFFICE": "Escritório",
        "WORKSITE": "Canteiro",
    }
)
CHILDREN = MappingProxyType(
    {
        "COMPANY": frozenset(set(LABELS) - {"COMPANY"}),
        "BRANCH": frozenset(
            {"UNIT", "STORE", "DISTRIBUTION_CENTER", "WAREHOUSE", "OFFICE", "WORKSITE"}
        ),
        "UNIT": frozenset(
            {"UNIT", "STORE", "DISTRIBUTION_CENTER", "WAREHOUSE", "OFFICE", "WORKSITE"}
        ),
        "STORE": frozenset({"WAREHOUSE", "OFFICE"}),
        "DISTRIBUTION_CENTER": frozenset({"WAREHOUSE", "OFFICE"}),
        "WAREHOUSE": frozenset({"OFFICE"}),
        "WORKSITE": frozenset({"OFFICE"}),
        "OFFICE": frozenset(),
    }
)


def allowed_parents(kind):
    return [parent for parent in LABELS if kind in CHILDREN[parent]]


def node_types():
    return {
        "items": [
            {
                "kind": kind,
                "label": label,
                "allowed_parent_kinds": allowed_parents(kind),
            }
            for kind, label in LABELS.items()
        ]
    }

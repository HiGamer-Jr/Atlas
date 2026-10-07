from importlib.util import find_spec

import pytest


def catalog():
    assert find_spec("app.datahub"), "Data Hub catalog not implemented"
    from app.datahub.catalog import dataset_definition, template_definition

    return dataset_definition, template_definition


def test_stock_key_has_no_artificial_code():
    dataset, _ = catalog()
    stock = dataset("STOCK_POSITIONS", 1)
    assert stock.business_key_fields == (
        "produto_codigo",
        "unidade_codigo",
        "data_referencia",
    )
    assert "codigo" not in stock.fields


def test_template_does_not_replace_dataset_or_grant_permissions():
    _, template = catalog()
    assert template("COMPRADOR_NACIONAL", 1).datasets == (
        "PRODUCTS",
        "PARTNERS",
        "DEMANDS",
    )
    with pytest.raises(ValueError):
        template("PLATFORM_ADMIN", 1)
    with pytest.raises(ValueError):
        template("COMPRADOR_NACIONAL", 99)


def test_normalization_keeps_textual_code_and_exact_decimal():
    dataset, _ = catalog()
    from app.datahub.normalization import normalize_row

    result = normalize_row(
        dataset("STOCK_POSITIONS", 1),
        {
            "produto_codigo": "000123",
            "unidade_codigo": "ws-001",
            "quantidade_disponivel": "12.3400",
            "data_referencia": "2026-10-06",
        },
    )
    assert result.model_dump(mode="json") == {
        "produto_codigo": "000123",
        "unidade_codigo": "WS-001",
        "quantidade_disponivel": "12.3400",
        "data_referencia": "2026-10-06",
    }


@pytest.mark.parametrize(
    "change",
    [
        {"produto_codigo": 123},
        {"quantidade_disponivel": "1.00001"},
        {"quantidade_disponivel": "NaN"},
        {"quantidade_disponivel": "-1"},
        {"sql": "UPDATE arbitrary"},
        {"data_referencia": "06/10/2026"},
    ],
)
def test_closed_stock_schema_rejects_lossy_or_arbitrary_input(change):
    dataset, _ = catalog()
    from app.datahub.normalization import normalize_row

    data = {
        "produto_codigo": "000123",
        "unidade_codigo": "WS-001",
        "quantidade_disponivel": "12.34",
        "data_referencia": "2026-10-06",
    }
    with pytest.raises(ValueError):
        normalize_row(dataset("STOCK_POSITIONS", 1), data | change)


@pytest.mark.parametrize("value", ["1E100000", "9" * 100, "Infinity"])
def test_extreme_decimal_is_validation_error(value):
    dataset, _ = catalog()
    from app.datahub.normalization import normalize_row

    with pytest.raises(ValueError):
        normalize_row(
            dataset("STOCK_POSITIONS", 1),
            {
                "produto_codigo": "P1",
                "unidade_codigo": "UNIT1",
                "quantidade_disponivel": value,
                "data_referencia": "2026-10-06",
            },
        )


@pytest.mark.parametrize(
    "dataset_code,data",
    [
        (
            "PRODUCTS",
            {
                "codigo": "p01",
                "descricao": "Produto sintético",
                "unidade_medida": "UN",
                "ativo": "SIM",
            },
        ),
        (
            "PARTNERS",
            {
                "codigo": "f01",
                "nome": "Parceiro sintético",
                "tipo": "FORNECEDOR",
                "pais_iso": "BR",
                "ativo": "NAO",
            },
        ),
        (
            "DEMANDS",
            {
                "codigo": "d01",
                "produto_codigo": "p01",
                "unidade_codigo": "unit1",
                "quantidade": "1.2",
                "data_necessidade": "2026-10-06",
                "modalidade": "NACIONAL",
                "prioridade": "NORMAL",
            },
        ),
        (
            "STOCK_POSITIONS",
            {
                "produto_codigo": "p01",
                "unidade_codigo": "unit1",
                "quantidade_disponivel": "0",
                "data_referencia": "2026-10-06",
            },
        ),
        (
            "COMEX_REFERENCES",
            {
                "codigo": "cx01",
                "parceiro_codigo": "f01",
                "moeda": "USD",
                "incoterm": "FOB",
                "data_prevista": "2026-10-06",
                "status": "PLANEJADO",
            },
        ),
        (
            "FINANCIAL_FORECASTS",
            {
                "codigo": "ff01",
                "unidade_codigo": "unit1",
                "moeda": "BRL",
                "valor": "5.30",
                "vencimento": "2026-10-06",
                "natureza": "SAIDA",
            },
        ),
    ],
)
def test_six_schemas_are_closed_and_normalize_synthetic_values(dataset_code, data):
    dataset, _ = catalog()
    from app.datahub.normalization import normalize_row

    normalized = normalize_row(dataset(dataset_code, 1), data).model_dump(mode="json")
    assert (
        normalized.get("codigo", normalized.get("produto_codigo"))
        == data.get("codigo", data.get("produto_codigo")).upper()
    )
    if "ativo" in data:
        assert normalized["ativo"] is (data["ativo"] == "SIM")
    with pytest.raises(ValueError):
        normalize_row(dataset(dataset_code, 1), data | {"actor": "forged"})


def test_signed_stock_zero_has_one_canonical_representation():
    dataset, _ = catalog()
    from app.datahub.normalization import normalize_row

    data = {
        "produto_codigo": "P1",
        "unidade_codigo": "UNIT1",
        "data_referencia": "2026-10-06",
    }
    a = normalize_row(
        dataset("STOCK_POSITIONS", 1), data | {"quantidade_disponivel": "-0"}
    ).model_dump(mode="json")
    b = normalize_row(
        dataset("STOCK_POSITIONS", 1), data | {"quantidade_disponivel": "0"}
    ).model_dump(mode="json")
    assert a == b
    assert a["quantidade_disponivel"] == "0.0000"

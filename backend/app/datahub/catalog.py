"""Versioned closed catalogue; template names never grant capabilities."""

from types import MappingProxyType

from app.datahub.schemas import (
    ComexPayload,
    DemandPayload,
    FinancialPayload,
    PartnerPayload,
    ProductPayload,
    StockPayload,
)
from app.datahub.types import DatasetCode as D
from app.datahub.types import DatasetDefinition, TemplateDefinition

DATASETS = MappingProxyType(
    {
        item.code: item
        for item in (
            DatasetDefinition(
                D.PRODUCTS, 1, "Produtos", "Produtos", ProductPayload, ("codigo",)
            ),
            DatasetDefinition(
                D.PARTNERS, 1, "Parceiros", "Parceiros", PartnerPayload, ("codigo",)
            ),
            DatasetDefinition(
                D.DEMANDS,
                1,
                "Demandas de compra",
                "Demandas",
                DemandPayload,
                ("codigo",),
                "PROCUREMENT",
            ),
            DatasetDefinition(
                D.STOCK_POSITIONS,
                1,
                "Posições de estoque",
                "Estoque",
                StockPayload,
                ("produto_codigo", "unidade_codigo", "data_referencia"),
                "INVENTORY",
            ),
            DatasetDefinition(
                D.COMEX_REFERENCES,
                1,
                "Referências COMEX",
                "COMEX",
                ComexPayload,
                ("codigo",),
                "COMEX",
            ),
            DatasetDefinition(
                D.FINANCIAL_FORECASTS,
                1,
                "Previsões financeiras",
                "Financeiro",
                FinancialPayload,
                ("codigo",),
                "FINANCE",
                True,
            ),
        )
    }
)
TEMPLATES = MappingProxyType(
    {
        item.code: item
        for item in (
            TemplateDefinition(
                "COORDENACAO",
                1,
                "Coordenação",
                (
                    D.PRODUCTS,
                    D.PARTNERS,
                    D.DEMANDS,
                    D.STOCK_POSITIONS,
                    D.COMEX_REFERENCES,
                ),
            ),
            TemplateDefinition(
                "SUPERVISAO",
                1,
                "Supervisão",
                (D.PRODUCTS, D.DEMANDS, D.STOCK_POSITIONS),
            ),
            TemplateDefinition(
                "COMPRADOR_NACIONAL",
                1,
                "Comprador Nacional",
                (D.PRODUCTS, D.PARTNERS, D.DEMANDS),
                modality="NACIONAL",
            ),
            TemplateDefinition(
                "COMPRADOR_INTERNACIONAL",
                1,
                "Comprador Internacional",
                (D.PRODUCTS, D.PARTNERS, D.DEMANDS, D.COMEX_REFERENCES),
                modality="INTERNACIONAL",
            ),
            TemplateDefinition("FINANCEIRO", 1, "Financeiro", (D.FINANCIAL_FORECASTS,)),
            TemplateDefinition(
                "DIRETORIA",
                1,
                "Diretoria",
                (
                    D.PRODUCTS,
                    D.PARTNERS,
                    D.DEMANDS,
                    D.STOCK_POSITIONS,
                    D.COMEX_REFERENCES,
                ),
                importable=False,
            ),
            TemplateDefinition(
                "LOJA", 1, "Loja", (D.PRODUCTS, D.DEMANDS, D.STOCK_POSITIONS)
            ),
            TemplateDefinition(
                "CENTRO_DISTRIBUICAO",
                1,
                "Centro de Distribuição",
                (D.PRODUCTS, D.STOCK_POSITIONS),
            ),
        )
    }
)


def dataset_definition(code: D, version: int) -> DatasetDefinition:
    try:
        definition = DATASETS[D(code)]
    except (ValueError, KeyError):
        raise ValueError("Dataset desconhecido") from None
    if version != definition.version:
        raise ValueError("Versão de dataset incompatível")
    return definition


def template_definition(template_id: str, version: int) -> TemplateDefinition:
    definition = TEMPLATES.get(template_id)
    if definition is None or version != definition.version:
        raise ValueError("Template ou versão incompatível")
    return definition

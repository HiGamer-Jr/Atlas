from uuid import UUID

"""Closed input schemas shared by connectors; validation never echoes rejected inputs."""

import re
import unicodedata
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

COUNTRIES = frozenset(
    [
        "AD",
        "AE",
        "AF",
        "AG",
        "AI",
        "AL",
        "AM",
        "AO",
        "AQ",
        "AR",
        "AS",
        "AT",
        "AU",
        "AW",
        "AX",
        "AZ",
        "BA",
        "BB",
        "BD",
        "BE",
        "BF",
        "BG",
        "BH",
        "BI",
        "BJ",
        "BL",
        "BM",
        "BN",
        "BO",
        "BQ",
        "BR",
        "BS",
        "BT",
        "BV",
        "BW",
        "BY",
        "BZ",
        "CA",
        "CC",
        "CD",
        "CF",
        "CG",
        "CH",
        "CI",
        "CK",
        "CL",
        "CM",
        "CN",
        "CO",
        "CR",
        "CU",
        "CV",
        "CW",
        "CX",
        "CY",
        "CZ",
        "DE",
        "DJ",
        "DK",
        "DM",
        "DO",
        "DZ",
        "EC",
        "EE",
        "EG",
        "EH",
        "ER",
        "ES",
        "ET",
        "FI",
        "FJ",
        "FK",
        "FM",
        "FO",
        "FR",
        "GA",
        "GB",
        "GD",
        "GE",
        "GF",
        "GG",
        "GH",
        "GI",
        "GL",
        "GM",
        "GN",
        "GP",
        "GQ",
        "GR",
        "GS",
        "GT",
        "GU",
        "GW",
        "GY",
        "HK",
        "HM",
        "HN",
        "HR",
        "HT",
        "HU",
        "ID",
        "IE",
        "IL",
        "IM",
        "IN",
        "IO",
        "IQ",
        "IR",
        "IS",
        "IT",
        "JE",
        "JM",
        "JO",
        "JP",
        "KE",
        "KG",
        "KH",
        "KI",
        "KM",
        "KN",
        "KP",
        "KR",
        "KW",
        "KY",
        "KZ",
        "LA",
        "LB",
        "LC",
        "LI",
        "LK",
        "LR",
        "LS",
        "LT",
        "LU",
        "LV",
        "LY",
        "MA",
        "MC",
        "MD",
        "ME",
        "MF",
        "MG",
        "MH",
        "MK",
        "ML",
        "MM",
        "MN",
        "MO",
        "MP",
        "MQ",
        "MR",
        "MS",
        "MT",
        "MU",
        "MV",
        "MW",
        "MX",
        "MY",
        "MZ",
        "NA",
        "NC",
        "NE",
        "NF",
        "NG",
        "NI",
        "NL",
        "NO",
        "NP",
        "NR",
        "NU",
        "NZ",
        "OM",
        "PA",
        "PE",
        "PF",
        "PG",
        "PH",
        "PK",
        "PL",
        "PM",
        "PN",
        "PR",
        "PS",
        "PT",
        "PW",
        "PY",
        "QA",
        "RE",
        "RO",
        "RS",
        "RU",
        "RW",
        "SA",
        "SB",
        "SC",
        "SD",
        "SE",
        "SG",
        "SH",
        "SI",
        "SJ",
        "SK",
        "SL",
        "SM",
        "SN",
        "SO",
        "SR",
        "SS",
        "ST",
        "SV",
        "SX",
        "SY",
        "SZ",
        "TC",
        "TD",
        "TF",
        "TG",
        "TH",
        "TJ",
        "TK",
        "TL",
        "TM",
        "TN",
        "TO",
        "TR",
        "TT",
        "TV",
        "TW",
        "TZ",
        "UA",
        "UG",
        "UM",
        "US",
        "UY",
        "UZ",
        "VA",
        "VC",
        "VE",
        "VG",
        "VI",
        "VN",
        "VU",
        "WF",
        "WS",
        "YE",
        "YT",
        "ZA",
        "ZM",
        "ZW",
    ]
)


def code(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Código deve ser textual")  # noqa: TRY004 -- Pydantic wraps ValueError, not TypeError
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9._-]{1,64}", value):
        raise ValueError("Código inválido")
    return value


def clean_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Texto inválido")  # noqa: TRY004 -- Pydantic wraps ValueError, not TypeError
    value = unicodedata.normalize("NFC", value).strip()
    if any(unicodedata.category(c).startswith("C") for c in value):
        raise ValueError("Texto contém caracteres não permitidos")
    return value


def decimal_value(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, Decimal, int, float)):
        raise ValueError("Número inválido")  # noqa: TRY004 -- Pydantic wraps ValueError, not TypeError
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("Número inválido") from None
    if not number.is_finite():
        raise ValueError("Número não finito")
    if number.copy_abs() >= Decimal(10000000000000000):
        raise ValueError("Precisão numérica excedida")
    try:
        normalized = number.quantize(Decimal("0.0001"))
    except InvalidOperation:
        raise ValueError("Precisão numérica excedida") from None
    if number != normalized:
        raise ValueError("Precisão numérica excedida")
    return Decimal("0.0000") if normalized.is_zero() else normalized


def iso_date(value: object) -> date:
    if isinstance(value, datetime):
        if value.time() != time():
            raise ValueError("Data não aceita horário")
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Data ISO obrigatória")
    return date.fromisoformat(value)


def boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().upper() in {"SIM", "NAO"}:
        return value.strip().upper() == "SIM"
    raise ValueError("Booleano deve ser SIM ou NAO")


def country(value: object) -> str:
    value = code(value)
    if value not in COUNTRIES:
        raise ValueError("País ISO inválido")
    return value


Code = Annotated[str, BeforeValidator(code)]
Name = Annotated[str, BeforeValidator(clean_text), Field(min_length=1, max_length=200)]
Date = Annotated[date, BeforeValidator(iso_date)]
Amount = Annotated[Decimal, BeforeValidator(decimal_value), Field(gt=0)]
StockAmount = Annotated[Decimal, BeforeValidator(decimal_value), Field(ge=0)]
Currency = Literal["BRL", "USD", "EUR", "GBP", "CNY"]


class ClosedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, frozen=True)


class ProductPayload(ClosedPayload):
    codigo: Code
    descricao: Name
    unidade_medida: Literal["UN", "KG", "TON", "L", "M", "M2", "M3", "CX", "PAL"]
    categoria: Annotated[str, BeforeValidator(clean_text), Field(max_length=120)] = ""
    ativo: Annotated[bool, BeforeValidator(boolean)]


class PartnerPayload(ClosedPayload):
    codigo: Code
    nome: Name
    tipo: Literal["FORNECEDOR", "CLIENTE", "TRANSPORTADOR"]
    pais_iso: Annotated[str, BeforeValidator(country)]
    ativo: Annotated[bool, BeforeValidator(boolean)]


class DemandPayload(ClosedPayload):
    codigo: Code
    produto_codigo: Code
    unidade_codigo: Code
    quantidade: Amount
    data_necessidade: Date
    modalidade: Literal["NACIONAL", "INTERNACIONAL"]
    prioridade: Literal["BAIXA", "NORMAL", "ALTA", "URGENTE"]


class StockPayload(ClosedPayload):
    produto_codigo: Code
    unidade_codigo: Code
    quantidade_disponivel: StockAmount
    data_referencia: Date


class ComexPayload(ClosedPayload):
    codigo: Code
    parceiro_codigo: Code
    moeda: Currency
    incoterm: Literal[
        "EXW", "FCA", "CPT", "CIP", "DAP", "DPU", "DDP", "FAS", "FOB", "CFR", "CIF"
    ]
    data_prevista: Date
    status: Literal["PLANEJADO", "EM_ANDAMENTO", "CONCLUIDO", "CANCELADO"]


class FinancialPayload(ClosedPayload):
    codigo: Code
    referencia_externa: Annotated[
        str, BeforeValidator(clean_text), Field(max_length=128)
    ] = ""
    unidade_codigo: Code
    moeda: Currency
    valor: Amount
    vencimento: Date
    natureza: Literal["ENTRADA", "SAIDA"]


NormalizedPayload = (
    ProductPayload
    | PartnerPayload
    | DemandPayload
    | StockPayload
    | ComexPayload
    | FinancialPayload
)


class ImportSummary(ClosedPayload):
    id: UUID
    status: Literal[
        "RECEIVED",
        "VALIDATING",
        "READY_FOR_CONFIRMATION",
        "REJECTED",
        "EXPIRED",
        "COMMITTED",
        "FAILED",
    ]
    version: int = Field(ge=1)
    template_id: str
    template_version: int
    row_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    inserted_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    preview_expires_at: datetime
    result_code: str


class ConfirmationInput(ClosedPayload):
    expected_version: int = Field(ge=1, strict=True)
    idempotency_key: UUID


class ConfirmationResult(ImportSummary):
    status: Literal["COMMITTED"]

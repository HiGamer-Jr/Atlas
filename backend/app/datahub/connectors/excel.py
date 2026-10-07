"""Official XLSX formatting and bounded parsing; no formula evaluation."""

import json
import stat
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Literal
from zipfile import BadZipFile, ZipFile
from zlib import error as ZlibError

from defusedxml import ElementTree as SafeXML
from defusedxml.common import DefusedXmlException
from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils.cell import (
    column_index_from_string,
    coordinate_from_string,
    get_column_letter,
)
from openpyxl.utils.exceptions import CellCoordinatesException, InvalidFileException
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.datahub.catalog import DATASETS, template_definition
from app.datahub.connectors.base import WorkbookRejected
from app.datahub.schemas import COUNTRIES
from app.datahub.types import (
    AuthorizedSelection,
    DatasetCode,
    NormalizedRow,
    ParsedRow,
    ParsedWorkbook,
    WorkbookContext,
    WorkbookIssue,
    WorkbookLimits,
)

HEADER_ROW = 12
DATA_ROW = 13
META_SHEET = "_HIATLAS_META"
README_SHEET = "LEIA-ME"
MARKER = "HIATLAS_DATAHUB_XLSX_V1"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NAVY = "173B5E"
BLUE = "237EB4"
EXCEL_MAX_TEXT = 32767
EXCEL_MAX_ROW = 1048576
EXCEL_MAX_COLUMN = 16384


class ManifestDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    code: DatasetCode
    sheet: str = Field(min_length=1, max_length=31)
    schema_version: int = Field(strict=True, ge=1, le=1)
    columns: tuple[str, ...] = Field(min_length=1, max_length=20)


class WorkbookInformation(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    company: str = Field(min_length=1, max_length=200)
    contract: str = Field(min_length=1, max_length=64)
    profile: str = Field(min_length=1, max_length=200)
    unit_scope: str = Field(max_length=4096)
    generated_at: AwareDatetime


class WorkbookManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    connector: Literal["XLSX"]
    template: str = Field(max_length=32)
    version: int = Field(strict=True, ge=1, le=1)
    datasets: tuple[ManifestDataset, ...] = Field(min_length=1, max_length=6)
    information: WorkbookInformation


def manifest(template_id, codes):
    definition = template_definition(template_id, 1)
    return {
        "connector": "XLSX",
        "template": definition.code,
        "version": definition.version,
        "datasets": [
            {
                "code": code.value,
                "sheet": DATASETS[code].sheet,
                "schema_version": DATASETS[code].version,
                "columns": list(DATASETS[code].fields),
            }
            for code in codes
        ],
    }


def enum_values(dataset, field):
    prop = dataset.schema.model_json_schema()["properties"][field]
    if field == "ativo":
        return ("SIM", "NAO")
    if field == "pais_iso":
        return tuple(sorted(COUNTRIES))
    return tuple(prop.get("enum", ()))


def is_code(field):
    return field == "codigo" or field.endswith("_codigo") or field == "pais_iso"


def numeric_values(xml):
    return {
        c.attrib["r"]: c.find("s:v", NS).text
        for c in xml.findall(".//s:sheetData/s:row/s:c", NS)
        if c.attrib.get("t", "n") == "n"
        and c.find("s:v", NS) is not None
        and c.find("s:v", NS).text is not None
    }


class ExcelConnector:
    code = "XLSX"

    def __init__(self, logo_path: Path, *, limits: WorkbookLimits | None = None):
        self.logo_path = logo_path
        self.limits = limits if limits is not None else WorkbookLimits()

    @staticmethod
    def write_cell(cell, value):
        if isinstance(value, str):
            if len(value) > EXCEL_MAX_TEXT:
                raise WorkbookRejected("TEXT_TOO_LONG")
            cell.value = value
            cell.data_type = (
                "s"  # Explicit inline string even for whitespace + formula prefixes.
            )
            cell.number_format = "@"
            cell.hyperlink = None
        elif isinstance(value, Decimal):
            if not value.is_finite():
                raise WorkbookRejected("INVALID_NUMBER")
            if len(value.normalize().as_tuple().digits) > 15:
                cell.value = format(value, "f")
                cell.data_type = "s"
                cell.number_format = "@"
            else:
                cell.value = value
                cell.number_format = "#,##0.0000"
        elif isinstance(value, (date, datetime)):
            cell.value = value
            cell.number_format = "yyyy-mm-dd"
        elif isinstance(value, bool):
            cell.value = "SIM" if value else "NAO"
            cell.data_type = "s"
        else:
            cell.value = value
        cell.font = Font(name="Arial", size=10, color=NAVY)
        cell.alignment = Alignment(
            vertical="center",
            horizontal="right"
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
            else "left",
        )

    def brand(self, sheet, context, label, version):
        sheet.sheet_view.showGridLines = False
        image = Image(self.logo_path)
        ratio = image.height / image.width
        image.width, image.height = 165, 165 * ratio
        sheet.add_image(image, "A1")
        for row in (2, 3, 4):
            sheet.merge_cells(start_row=row, start_column=3, end_row=row, end_column=7)
        for cell, value in (
            ("C2", "HiAtlas — Supply Chain Intelligence"),
            ("C3", "Um novo horizonte para o seu negócio"),
            ("C4", label),
        ):
            self.write_cell(sheet[cell], value)
        sheet["C2"].font = Font(name="Arial", size=14, bold=True, color=NAVY)
        for row, value in (
            (5, context.company),
            (6, context.contract),
            (7, context.role),
            (8, context.unit_scope),
            (9, context.generated_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")),
            (10, str(version)),
        ):
            self.write_cell(
                sheet.cell(row, 1),
                {
                    5: "Empresa",
                    6: "Contrato",
                    7: "Perfil",
                    8: "Unidade/escopo",
                    9: "Gerado em",
                    10: "Versão do template",
                }[row],
            )
            sheet.merge_cells(start_row=row, start_column=2, end_row=row, end_column=7)
            self.write_cell(sheet.cell(row, 2), value)
        for row in range(1, 12):
            sheet.row_dimensions[row].height = 21
        sheet.row_dimensions[1].height = 12
        for col in range(1, 8):
            sheet.column_dimensions[get_column_letter(col)].width = 24

    def generate(
        self,
        selection: AuthorizedSelection,
        context: WorkbookContext,
        rows: Sequence[NormalizedRow],
    ) -> bytes:
        if context.generated_at.tzinfo is None:
            raise WorkbookRejected("UTC_CONTEXT_REQUIRED")
        if len(rows) > self.limits.max_export_rows:
            raise WorkbookRejected("EXPORT_LIMIT")
        template = template_definition(
            selection.template_id, selection.template_version
        )
        codes = tuple(DatasetCode(c) for c in selection.datasets)
        if (
            not codes
            or len(set(codes)) != len(codes)
            or not set(codes) <= set(template.datasets)
        ):
            raise WorkbookRejected("DATASET_INCOMPATIBLE")
        if any(row.dataset not in codes for row in rows):
            raise WorkbookRejected("DATASET_INCOMPATIBLE")
        allowed_units = {unit.code for unit in selection.units}
        for row in rows:
            if (
                hasattr(row.payload, "unidade_codigo")
                and row.payload.unidade_codigo not in allowed_units
            ):
                raise WorkbookRejected("UNIT_SCOPE_DENIED")
        workbook = Workbook()
        workbook.remove(workbook.active)
        workbook.properties.creator = "HiAtlas"
        workbook.properties.title = "HiAtlas — Supply Chain Intelligence"
        meta = workbook.create_sheet(META_SHEET)
        meta.sheet_state = "hidden"
        self.write_cell(meta["A1"], MARKER)
        self.write_cell(
            meta["A2"],
            json.dumps(
                manifest(template.code, codes)
                | {
                    "information": WorkbookInformation(
                        company=context.company,
                        contract=context.contract,
                        profile=context.role,
                        unit_scope=context.unit_scope,
                        generated_at=context.generated_at.astimezone(UTC),
                    ).model_dump(mode="json")
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        )
        validation_col = 3
        for code in codes:
            dataset = DATASETS[code]
            sheet = workbook.create_sheet(dataset.sheet)
            self.brand(
                sheet, context, template.label + " / " + dataset.label, template.version
            )
            payloads = [
                dataset.schema.model_validate(r.payload.model_dump())
                for r in rows
                if r.dataset == code
            ]
            for col, field in enumerate(dataset.fields, 1):
                cell = sheet.cell(HEADER_ROW, col, field)
                cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor=NAVY)
                cell.alignment = Alignment(
                    horizontal="center", vertical="center", wrap_text=True
                )
                sheet.column_dimensions[get_column_letter(col)].width = max(
                    20, len(field) + 3
                )
                prop = dataset.schema.model_fields[field]
                values = enum_values(dataset, field)
                if field == "modalidade" and template.modality:
                    values = (template.modality,)
                if field == "unidade_codigo":
                    values = tuple(u.code for u in selection.units)
                if values:
                    for pos, value in enumerate(values, 1):
                        self.write_cell(meta.cell(pos, validation_col), value)
                    letter = get_column_letter(validation_col)
                    validation = DataValidation(
                        type="list",
                        formula1=f"'{META_SHEET}'!${letter}$1:${letter}${len(values)}",
                        allow_blank=not prop.is_required(),
                    )
                    validation_col += 1
                    validation.errorTitle = "Valor inválido"
                    validation.error = "Selecione um valor da lista."
                    validation.showErrorMessage = True
                    validation.errorStyle = "stop"
                    sheet.add_data_validation(validation)
                    validation.add(
                        f"{get_column_letter(col)}{DATA_ROW}:{get_column_letter(col)}{DATA_ROW + self.limits.max_rows - 1}"
                    )
                for pos, payload in enumerate(payloads, DATA_ROW):
                    self.write_cell(sheet.cell(pos, col), getattr(payload, field))
                blank = sheet.cell(DATA_ROW, col)
                if not payloads:
                    blank.fill = PatternFill(
                        "solid", fgColor="FFF4D6" if prop.is_required() else "E5F1F8"
                    )
                    blank.number_format = (
                        "@"
                        if is_code(field)
                        else "yyyy-mm-dd"
                        if prop.annotation is date
                        else "#,##0.0000"
                        if prop.annotation is Decimal
                        else "General"
                    )
            last = max(DATA_ROW, DATA_ROW + len(payloads) - 1)
            table = Table(
                displayName="HT_" + code.value,
                ref=f"A{HEADER_ROW}:{get_column_letter(len(dataset.fields))}{last}",
            )
            table.tableStyleInfo = TableStyleInfo(
                name="TableStyleMedium2", showRowStripes=True
            )
            sheet.add_table(table)
            sheet.freeze_panes = "A13"
            sheet.row_dimensions[HEADER_ROW].height = 32
            sheet.print_title_rows = "1:12"
            sheet.sheet_properties.pageSetUpPr.fitToPage = True
            sheet.page_setup.orientation = "landscape"
            sheet.page_setup.fitToWidth = 1
            sheet.page_setup.fitToHeight = 0
        readme = workbook.create_sheet(README_SHEET, 0)
        self.brand(readme, context, "Como usar esta planilha", template.version)
        instructions = [
            "Finalidade: registros informacionais do Data Hub; não executa processos operacionais.",
            "A planilha não concede autorização. O HiAtlas revalida permissões, módulos e escopo ao importar.",
            "Campos obrigatórios: amarelo-claro. Campos opcionais: azul-claro. Cabeçalho azul-escuro.",
            "Não renomear abas ou colunas. Não alterar _HIATLAS_META. Template versão "
            + str(template.version)
            + ".",
            "Dados começam na linha 13. Preserve o cabeçalho da linha 12. Não use fórmulas ou macros.",
            "Códigos devem ser texto; preserve zeros à esquerda. Datas: YYYY-MM-DD ou célula de data sem horário.",
            "Números: até quatro casas decimais. Acima de 15 dígitos significativos, use texto com ponto decimal.",
            "Booleanos: SIM ou NAO. Use os valores das listas para campos enumerados.",
            "Importar novamente: Data Hub > Excel > Upload > Validar > Revisar preview > Confirmar.",
            "Duplicatas idênticas são ignoradas; chaves com conteúdo diferente são rejeitadas, sem sobrescrever.",
        ]
        for dataset_code in codes:
            dataset = DATASETS[dataset_code]
            required = ", ".join(
                field
                for field, item in dataset.schema.model_fields.items()
                if item.is_required()
            )
            instructions.append(dataset.label + " — campos obrigatórios: " + required)
        for pos, text in enumerate(instructions, 12):
            readme.merge_cells(start_row=pos, start_column=1, end_row=pos, end_column=7)
            self.write_cell(readme.cell(pos, 1), text)
            readme.cell(pos, 1).alignment = Alignment(wrap_text=True, vertical="center")
            readme.row_dimensions[pos].height = 36
        workbook.active = 0
        output = BytesIO()
        workbook.save(output)
        workbook.close()
        return output.getvalue()

    def package(self, content, limits):
        if len(content) > limits.max_upload_bytes:
            raise WorkbookRejected("FILE_TOO_LARGE")
        try:
            with ZipFile(BytesIO(content)) as archive:
                infos = archive.infolist()
                if (
                    len(infos) > limits.max_entries
                    or sum(i.file_size for i in infos) > limits.max_uncompressed_bytes
                ):
                    raise WorkbookRejected("PACKAGE_LIMIT")
                names = [i.filename for i in infos]
                if len(set(names)) != len(names):
                    raise WorkbookRejected("PACKAGE_INVALID")
                xml = {}
                cells = 0
                for info in infos:
                    path = PurePosixPath(info.filename)
                    lower = info.filename.lower()
                    if (
                        path.is_absolute()
                        or ".." in path.parts
                        or "\\" in lower
                        or ":" in lower
                        or info.flag_bits & 1
                        or stat.S_ISLNK(info.external_attr >> 16)
                        or any(
                            term in lower
                            for term in (
                                "vbaproject",
                                "activex",
                                "externallinks",
                                "embeddings",
                            )
                        )
                        or (
                            not info.is_dir()
                            and path.name != ".rels"
                            and path.suffix.lower()
                            not in {".xml", ".rels", ".png", ".jpg", ".jpeg", ".gif"}
                        )
                    ):
                        raise WorkbookRejected("PACKAGE_UNSAFE")
                    if path.suffix.lower() in {".xml", ".rels"} or path.name == ".rels":
                        data = archive.read(info.filename)
                        root = SafeXML.fromstring(
                            data,
                            forbid_dtd=True,
                            forbid_entities=True,
                            forbid_external=True,
                        )
                        xml[info.filename] = root
                        if any(
                            e.attrib.get("TargetMode") == "External"
                            for e in root.iter()
                        ):
                            raise WorkbookRejected("EXTERNAL_LINK_NOT_ALLOWED")
                        if any(
                            "macro" in v.lower() or "vba" in v.lower()
                            for e in root.iter()
                            for v in e.attrib.values()
                        ):
                            raise WorkbookRejected("MACRO_NOT_ALLOWED")
                        if lower.startswith("xl/worksheets/"):
                            cs = root.findall(".//s:sheetData/s:row/s:c", NS)
                            cells += len(cs)
                            positions = set()
                            for cell in cs:
                                coordinate = cell.attrib.get("r", "")
                                column, row = coordinate_from_string(coordinate)
                                if (
                                    row > EXCEL_MAX_ROW
                                    or column_index_from_string(column)
                                    > EXCEL_MAX_COLUMN
                                ):
                                    raise WorkbookRejected("PACKAGE_INVALID")
                                if coordinate in positions:
                                    raise WorkbookRejected("PACKAGE_INVALID")
                                positions.add(coordinate)
                if cells > limits.max_cells:
                    raise WorkbookRejected("CELL_LIMIT")
                return xml, len(infos)
        except WorkbookRejected:
            raise
        except (
            BadZipFile,
            CellCoordinatesException,
            ZlibError,
            DefusedXmlException,
            SafeXML.ParseError,
            ValueError,
            KeyError,
            RuntimeError,
            OSError,
        ):
            raise WorkbookRejected("PACKAGE_INVALID") from None

    def parse(self, content: bytes, limits: WorkbookLimits) -> ParsedWorkbook:
        xml, entries = self.package(content, limits)
        try:
            workbook = load_workbook(
                BytesIO(content), read_only=True, data_only=False, keep_links=False
            )
            if len(workbook.sheetnames) > limits.max_sheets:
                raise WorkbookRejected("SHEET_LIMIT")
            if META_SHEET not in workbook or README_SHEET not in workbook:
                raise WorkbookRejected("TEMPLATE_INCOMPATIBLE")
            meta = workbook[META_SHEET]
            if meta["A1"].value != MARKER or meta.sheet_state != "hidden":
                raise WorkbookRejected("TEMPLATE_INCOMPATIBLE")
            metadata = WorkbookManifest.model_validate_json(meta["A2"].value)
            template = template_definition(metadata.template, metadata.version)
            codes = tuple(row.code for row in metadata.datasets)
            if (
                not codes
                or len(set(codes)) != len(codes)
                or not set(codes) <= set(template.datasets)
            ):
                raise WorkbookRejected("TEMPLATE_INCOMPATIBLE")
            # Context labels and profile are informative; permission is revalidated independently.
            if metadata.model_dump(mode="json", exclude={"information"}) != manifest(
                template.code, codes
            ):
                raise WorkbookRejected("TEMPLATE_INCOMPATIBLE")
            sheets = {DATASETS[c].sheet: c for c in codes}
            if set(workbook.sheetnames) != set(sheets) | {META_SHEET, README_SHEET}:
                raise WorkbookRejected("SHEET_INCOMPATIBLE")
            # Resolve real OOXML part names, not user-visible sheet order or numbering.
            wbxml = xml["xl/workbook.xml"]
            rels = {
                r.attrib["Id"]: r.attrib["Target"]
                for r in xml["xl/_rels/workbook.xml.rels"]
            }
            parts = {}
            for sheet in wbxml.findall("s:sheets/s:sheet", NS):
                target = rels[sheet.attrib[f"{{{REL_NS}}}id"]]
                parts[sheet.attrib["name"]] = (
                    target.lstrip("/") if target.startswith("/") else "xl/" + target
                )
            rows = []
            issues = []
            for name, code in sheets.items():
                dataset = DATASETS[code]
                sheet = workbook[name]
                # Do not trust worksheet dimensions: malicious dimensions must not drive iteration.
                sheet.reset_dimensions()
                header = next(
                    sheet.iter_rows(
                        min_row=HEADER_ROW,
                        max_row=HEADER_ROW,
                        max_col=len(dataset.fields) + 1,
                    )
                )
                if (
                    tuple(c.value for c in header[: len(dataset.fields)])
                    != dataset.fields
                    or header[-1].value is not None
                ):
                    raise WorkbookRejected("COLUMN_INCOMPATIBLE")
                sheet_xml = xml[parts[name]]
                for cell in sheet_xml.findall(".//s:sheetData/s:row/s:c", NS):
                    column, row_number = coordinate_from_string(cell.attrib["r"])
                    meaningful = any(item.text is not None for item in cell.iter())
                    if row_number >= HEADER_ROW and meaningful:
                        if row_number > HEADER_ROW + limits.max_rows:
                            raise WorkbookRejected("ROW_LIMIT")
                        if column_index_from_string(column) > len(dataset.fields):
                            raise WorkbookRejected("COLUMN_INCOMPATIBLE")
                numeric = numeric_values(sheet_xml)
                for source, row in enumerate(
                    sheet.iter_rows(
                        min_row=DATA_ROW,
                        max_row=limits.max_rows + HEADER_ROW,
                        max_col=len(dataset.fields) + 1,
                    ),
                    DATA_ROW,
                ):
                    if not any(c.value is not None for c in row):
                        continue
                    if len(rows) >= limits.max_rows:
                        raise WorkbookRejected("ROW_LIMIT")
                    if row[-1].value is not None:
                        raise WorkbookRejected("COLUMN_INCOMPATIBLE")
                    values = {}
                    for field, cell in zip(dataset.fields, row, strict=False):
                        value = cell.value
                        if cell.data_type == "f":
                            issues.append(
                                WorkbookIssue(
                                    "FORMULA_NOT_ALLOWED",
                                    "Fórmulas não são permitidas.",
                                    name,
                                    source,
                                    field,
                                )
                            )
                            value = None
                        elif cell.data_type == "e":
                            issues.append(
                                WorkbookIssue(
                                    "CELL_ERROR",
                                    "Célula contém erro.",
                                    name,
                                    source,
                                    field,
                                )
                            )
                            value = None
                        elif (
                            is_code(field)
                            and value is not None
                            and not isinstance(value, str)
                        ):
                            issues.append(
                                WorkbookIssue(
                                    "TEXT_CODE_REQUIRED",
                                    "Código deve ser preenchido como texto.",
                                    name,
                                    source,
                                    field,
                                )
                            )
                            value = None
                        elif (
                            dataset.schema.model_fields[field].annotation is Decimal
                            and cell.data_type == "n"
                            and cell.coordinate in numeric
                        ):
                            value = Decimal(numeric[cell.coordinate])
                        values[field] = value
                    rows.append(
                        ParsedRow(
                            code,
                            dataset.version,
                            name,
                            source,
                            MappingProxyType(values),
                        )
                    )
            return ParsedWorkbook(
                template.code,
                template.version,
                codes,
                tuple(rows),
                tuple(issues),
                len(workbook.sheetnames),
                entries,
            )
        except WorkbookRejected:
            raise
        except (
            ValueError,
            TypeError,
            KeyError,
            InvalidFileException,
            IndexError,
            AttributeError,
            OverflowError,
        ):
            raise WorkbookRejected("TEMPLATE_INCOMPATIBLE") from None
        finally:
            if "workbook" in locals():
                workbook.close()

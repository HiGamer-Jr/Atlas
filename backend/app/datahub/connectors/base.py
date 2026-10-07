"""Connectors translate formats; they never grant authority or write domain data."""

from collections.abc import Sequence
from typing import Protocol

from app.datahub.types import (
    AuthorizedSelection,
    NormalizedRow,
    ParsedWorkbook,
    WorkbookContext,
    WorkbookLimits,
)


class WorkbookRejected(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class Connector(Protocol):
    def parse(self, content: bytes, limits: WorkbookLimits) -> ParsedWorkbook: ...
    def generate(
        self,
        selection: AuthorizedSelection,
        context: WorkbookContext,
        rows: Sequence[NormalizedRow],
    ) -> bytes: ...

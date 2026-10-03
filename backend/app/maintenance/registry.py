"""Typed domain boundary; future domains register explicit closed Python contracts."""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel


def closed_schema(schema):
    root = schema.model_json_schema()

    def check(item):
        if not isinstance(item, dict):
            raise TypeError("Handler schemas must be typed and closed")
        if "$ref" in item:
            reference = item["$ref"]
            if not reference.startswith("#/$defs/") or reference.split("/")[
                -1
            ] not in root.get("$defs", {}):
                raise ValueError("Handler schemas must be typed and closed")
            return
        choices = [item[key] for key in ("anyOf", "oneOf", "allOf") if key in item]
        if choices:
            for values in choices:
                for value in values:
                    check(value)
            return
        kind = item.get("type")
        if kind not in {
            "object",
            "array",
            "string",
            "integer",
            "number",
            "boolean",
            "null",
        }:
            raise ValueError("Handler schemas must be typed and closed")
        if kind == "object":
            if item.get("additionalProperties") is not False:
                raise ValueError("Handler schemas must be typed and closed")
            for value in item.get("properties", {}).values():
                check(value)
        if kind == "array":
            check(item.get("items"))

    check(root)
    for item in root.get("$defs", {}).values():
        check(item)


@dataclass(frozen=True)
class MaintenanceHandler:
    input_type: type[BaseModel]
    snapshot_type: type[BaseModel]
    load_scoped: Callable
    preview: Callable
    apply: Callable
    description: str
    effects: tuple[str, ...]
    reprocess: Callable | None = None
    retry_eligible: Callable | None = None
    foundation_action: bool = False
    diagnostics_safe: bool = False

    def validate_contract(self):
        for schema in (self.input_type, self.snapshot_type):
            if not isinstance(schema, type) or not issubclass(schema, BaseModel):
                raise TypeError("Handler schemas must be typed")
            closed_schema(schema)
        if not all(callable(fn) for fn in (self.load_scoped, self.preview, self.apply)):
            raise ValueError("Handler operations must be typed callables")

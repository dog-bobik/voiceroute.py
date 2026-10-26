#!/usr/bin/env python3
"""Generate deterministic internal TypedDict wire models from OpenAPI/AsyncAPI JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import keyword
import re
from pathlib import Path
from typing import Any

HEADER = '''# ruff: noqa: E501, I001
# fmt: off
"""Generated VoiceRoute wire DTOs; do not edit."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypeAlias, TypedDict

'''


def identifier(value: str) -> str:
    result = re.sub(r"(?<!^)(?=[A-Z])", "_", value).replace("-", "_").lower()
    result = re.sub(r"\W", "_", result)
    if not result or result[0].isdigit() or keyword.iskeyword(result):
        result = f"field_{result}"
    return result


def type_name(value: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+", value)
    result = "".join(part[:1].upper() + part[1:] for part in parts if part)
    return result if result and not result[0].isdigit() else f"Model{result}"


def annotation(schema: dict[str, Any]) -> str:
    ref = schema.get("$ref")
    if isinstance(ref, str):
        return type_name(ref.rsplit("/", 1)[-1])
    variants = schema.get("oneOf") or schema.get("anyOf")
    if isinstance(variants, list) and variants:
        return " | ".join(dict.fromkeys(annotation(item) for item in variants))
    enum = schema.get("enum")
    if isinstance(enum, list) and enum and all(isinstance(item, str) for item in enum):
        return "Literal[" + ", ".join(repr(item) for item in enum) + "] | str"
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        concrete = [item for item in schema_type if item != "null"]
        nested = dict(schema)
        nested["type"] = concrete[0] if len(concrete) == 1 else None
        value = annotation(nested)
        return value if "null" not in schema_type else f"{value} | None"
    if schema_type == "array":
        items = schema.get("items")
        return f"list[{annotation(items if isinstance(items, dict) else {})}]"
    if schema_type == "object":
        return "dict[str, Any]"
    base = {
        "boolean": "bool",
        "integer": "int",
        "number": "float",
        "string": "str",
    }.get(schema_type, "Any")
    return f"{base} | None" if schema.get("nullable") else base


def schemas(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    components = document.get("components")
    if isinstance(components, dict) and isinstance(components.get("schemas"), dict):
        return components["schemas"]
    return {}


def render(documents: list[dict[str, Any]], *, source_hashes: list[str] | None = None) -> str:
    merged: dict[str, dict[str, Any]] = {}
    for document in documents:
        merged.update(schemas(document))
    blocks: list[str] = [HEADER.rstrip()]
    if source_hashes:
        hashes = "\n".join(f"    {value!r}," for value in source_hashes)
        blocks.append(f"SOURCE_HASHES = (\n{hashes}\n)")
    for raw_name in sorted(merged):
        schema = merged[raw_name]
        name = type_name(raw_name)
        properties = schema.get("properties")
        if isinstance(properties, dict):
            required = set(schema.get("required", ()))
            lines = [f"class {name}(TypedDict):"]
            if not properties:
                lines.append("    pass")
            for wire_name in sorted(properties):
                field_schema = properties[wire_name]
                value_type = annotation(field_schema if isinstance(field_schema, dict) else {})
                if wire_name not in required:
                    value_type = f"NotRequired[{value_type}]"
                lines.append(f"    {identifier(wire_name)}: {value_type}")
            blocks.append("\n".join(lines))
        else:
            blocks.append(f"{name}: TypeAlias = {annotation(schema)}")
    return "\n\n\n".join(blocks) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source_bytes = [path.read_bytes() for path in args.inputs]
    documents = [json.loads(value) for value in source_bytes]
    hashes = [hashlib.sha256(value).hexdigest() for value in source_bytes]
    generated = render(documents, source_hashes=hashes)
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != generated:
            raise SystemExit(f"generated models are stale: {args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")


if __name__ == "__main__":
    main()

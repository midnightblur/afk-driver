"""Check a value against a JSON Schema, with the keywords the page schemas use and no others.

A problem is `(path, why)`; `path` is a tuple of object keys and list indexes.
A schema with any other keyword raises `SchemaError`, so a keyword is never ignored in silence.
"""

from __future__ import annotations

import re

ANNOTATIONS = {"$schema", "$id", "title", "description", "$defs"}
KEYWORDS = {"$ref", "type", "const", "enum", "required", "properties", "additionalProperties",
            "items", "pattern", "minimum", "minItems", "minLength", "anyOf"}
TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


class SchemaError(ValueError):
    """A schema uses a keyword or a type this reader does not know."""


def check_schema(schema: dict) -> None:
    unknown = set(schema) - KEYWORDS - ANNOTATIONS
    if unknown:
        raise SchemaError(f"unknown schema keyword: {sorted(unknown)}")
    declared = schema.get("type", [])
    for name in [declared] if isinstance(declared, str) else declared:
        if name not in TYPES:
            raise SchemaError(f"unknown schema type: {name}")
    subs = list(schema.get("properties", {}).values()) + list(schema.get("$defs", {}).values())
    subs += schema.get("anyOf", [])
    if "items" in schema:
        subs.append(schema["items"])
    for sub in subs:
        check_schema(sub)


def problems(value, schema: dict, path: tuple = (), root: dict | None = None) -> list[tuple]:
    root = root if root is not None else schema
    if "$ref" in schema:
        return problems(value, _resolve(schema["$ref"], root), path, root)
    found = _scalar_problems(value, schema, path, root)
    if found:
        return found
    if isinstance(value, dict):
        found += _object_problems(value, schema, path, root)
    elif isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            found.append((path, f"needs at least {schema['minItems']} entries"))
        if "items" in schema:
            for index, entry in enumerate(value):
                found += problems(entry, schema["items"], (*path, index), root)
    return found


def _resolve(ref: str, root: dict) -> dict:
    prefix = "#/$defs/"
    if not ref.startswith(prefix) or ref[len(prefix):] not in root.get("$defs", {}):
        raise SchemaError(f"unknown schema reference: {ref}")
    return root["$defs"][ref[len(prefix):]]


def _scalar_problems(value, schema: dict, path: tuple, root: dict) -> list[tuple]:
    if "const" in schema and value != schema["const"]:
        return [(path, f"must be {schema['const']!r}, found {value!r}")]
    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(str(v) for v in schema["enum"])
        return [(path, f"{value!r} is not one of {allowed}")]
    if "type" in schema:
        names = [schema["type"]] if isinstance(schema["type"], str) else schema["type"]
        if not any(TYPES[name](value) for name in names):
            return [(path, f"must be {' or '.join(names)}, found {type(value).__name__}")]
    if "anyOf" in schema and not any(not problems(value, sub, path, root) for sub in schema["anyOf"]):
        return [(path, "matches none of the allowed shapes")]
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            return [(path, "must not be empty")]
        if "pattern" in schema and not re.search(schema["pattern"], value):
            return [(path, f"{value!r} does not match {schema['pattern']}")]
    if "minimum" in schema and TYPES["number"](value) and value < schema["minimum"]:
        return [(path, f"must be at least {schema['minimum']}, found {value}")]
    return []


def _object_problems(value: dict, schema: dict, path: tuple, root: dict) -> list[tuple]:
    found = [((*path, key), "is required") for key in schema.get("required", []) if key not in value]
    known = schema.get("properties", {})
    for key, entry in value.items():
        if key in known:
            found += problems(entry, known[key], (*path, key), root)
        elif schema.get("additionalProperties") is False:
            found.append(((*path, key), "is not a field of this object"))
    return found

"""Component registry: a type name maps to a schema and a renderer (SDD §9).

A new component is one module in `components/` that calls `register_component`. The renderer
has no list of types. `render(props, children)` takes the rendered children and returns HTML.
"""

from __future__ import annotations

import html
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from schema.validate import check_schema, problems

COMPONENTS = Path(__file__).resolve().parent / "components"
PAGE_SCHEMA = json.loads((COMPONENTS.parent / "schema" / "page-v0.schema.json").read_text(encoding="utf-8"))
COMPONENT_SHAPE = {"$ref": "#/$defs/component"}

_types: dict[str, "ComponentType"] = {}
_loaded = False


@dataclass(frozen=True)
class ComponentType:
    name: str
    schema: dict
    render: Callable[[dict, list[str]], str]
    nested: Callable[[dict], Iterable[tuple]] | None = None
    check: Callable[[dict], Iterable[tuple]] | None = None
    inline: bool = False
    takes_html: bool = False


def register_component(name: str, schema: dict, render: Callable, *, nested: Callable | None = None,
                       check: Callable | None = None, inline: bool = False, takes_html: bool = False) -> None:
    """Add one type. `nested(props)` yields `(path below props, component)` for components held in
    props; `check(props)` yields `(path below props, why)` for rules the schema cannot state."""
    if name in _types:
        raise ValueError(f"component type {name!r} is registered already")
    check_schema(schema)
    _types[name] = ComponentType(name, schema, render, nested, check, inline, takes_html)


def load_components(folder: Path = COMPONENTS) -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    for path in sorted(folder.glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"page_component_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


def lookup(type_name: str) -> ComponentType | None:
    load_components()
    return _types.get(type_name)


def known_types() -> list[str]:
    load_components()
    return sorted(_types)


def _children(component: dict) -> list[dict]:
    return component.get("children") or []


def _held(component: dict, kind: ComponentType | None) -> list[tuple]:
    """`(path below the component, component)` for each component this one holds."""
    props = component.get("props") or {}
    held = [(("children", i), child) for i, child in enumerate(_children(component))]
    if kind and kind.nested:
        held += [(("props", *path), sub) for path, sub in kind.nested(props)]
    return held


def validate(component: dict, path: tuple = ()) -> list[tuple]:
    """Problems of a component and of every component it holds, as `(path, why)`."""
    shape = problems(component, COMPONENT_SHAPE, path, PAGE_SCHEMA)
    if shape:
        return shape
    kind = lookup(component["type"])
    if kind is None:
        return [((*path, "type"), f"unknown type {component['type']!r}; known types: {', '.join(known_types())}")]
    props = component.get("props") or {}
    found = problems(props, kind.schema, (*path, "props"))
    if "html" in component and not kind.takes_html:
        found.append(((*path, "html"), "is for freestyle only"))
    if found:
        return found
    if kind.takes_html and not component.get("html"):
        found.append(((*path, "html"), "is required"))
    if kind.check:
        found += [((*path, "props", *sub), why) for sub, why in kind.check(props)]
    if found:
        return found
    for sub, child in _held(component, kind):
        found += validate(child, (*path, *sub))
    return found


def walk(component: dict, path: tuple = ()) -> Iterable[tuple]:
    """Yield `(path, component)` for a valid component and every component it holds."""
    yield path, component
    for sub, child in _held(component, lookup(component["type"])):
        yield from walk(child, (*path, *sub))


def render_component(component: dict) -> str:
    """The HTML of one valid component, in the wrapper that carries its id and style."""
    kind = lookup(component["type"])
    props = component.get("props") or {}
    if kind.takes_html:
        props = {**props, "html": component["html"], "id": component.get("id")}
    inner = kind.render(props, [render_component(child) for child in _children(component)])
    element, style = component.get("id"), component.get("style")
    if not element and not style:
        return inner
    tag = "span" if kind.inline else "div"
    attrs = ""
    if element:
        attrs += f' data-afkv2-element="{html.escape(element)}"'
    if style:
        attrs += f' style="{html.escape(style)}"'
    return f"<{tag}{attrs}>{inner}</{tag}>"

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
PAGE_SCHEMA = json.loads((COMPONENTS.parent / "schema" / "page-v1.schema.json").read_text(encoding="utf-8"))
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
    targets: Callable[[dict], dict] | None = None
    takes_id: bool = False


def register_component(name: str, schema: dict, render: Callable, *, nested: Callable | None = None,
                       check: Callable | None = None, inline: bool = False, takes_html: bool = False,
                       targets: Callable | None = None, takes_id: bool = False) -> None:
    """Add one type. `nested(props)` yields `(path below props, component)` for components held in
    props; `check(props)` yields `(path below props, why)` for rules the schema cannot state;
    `targets(props)` maps each HTML id the renderer draws that is no element id to the element id that an
    annotation on it stands for. With `takes_id`, `render` and `targets` find the element id in `props["id"]`."""
    if name in _types:
        raise ValueError(f"component type {name!r} is registered already")
    check_schema(schema)
    _types[name] = ComponentType(name, schema, render, nested, check, inline, takes_html, targets, takes_id)


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


def validate(component: dict, path: tuple = (), page_schema: dict | None = None) -> list[tuple]:
    """Problems of a component and of every component it holds, as `(path, why)`. The component shape is
    the one of `page_schema`, the schema of the document's format; by default the newest format."""
    page_schema = page_schema or PAGE_SCHEMA
    shape = problems(component, COMPONENT_SHAPE, path, page_schema)
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
        found += validate(child, (*path, *sub), page_schema)
    return found


def walk(component: dict, path: tuple = ()) -> Iterable[tuple]:
    """Yield `(path, component)` for a valid component and every component it holds."""
    yield path, component
    for sub, child in _held(component, lookup(component["type"])):
        yield from walk(child, (*path, *sub))


def _render_props(component: dict, kind: ComponentType) -> dict:
    """The props that `render` and `targets` take: freestyle also gets its html, and both get the id."""
    props = component.get("props") or {}
    if kind.takes_html:
        return {**props, "html": component["html"], "id": component.get("id")}
    if kind.takes_id:
        return {**props, "id": component.get("id")}
    return props


def aliases(component: dict) -> dict:
    """Each HTML id that a valid component tree draws and that is no element id, with the element id that
    an annotation on it stands for."""
    found = {}
    for _, part in walk(component):
        kind = lookup(part["type"])
        if kind.targets:
            found.update(kind.targets(_render_props(part, kind)))
    return found


def render_component(component: dict) -> str:
    """The HTML of one valid component, in the wrapper that carries its id, style and tip. A `fold` label
    puts the component in a closed `<details>` inside that wrapper. A fold of a component with an id
    has the key `fold-<id>`, so the page keeps it open through a reload; a fold with no id has no key.

    The id is also the HTML id: a lavish annotation names the nearest ancestor id in its selector. The tip is
    the hover text of the tooltip layer (`shell/tips.js`)."""
    kind = lookup(component["type"])
    inner = kind.render(_render_props(component, kind), [render_component(child) for child in _children(component)])
    element, style, tip = component.get("id"), component.get("style"), component.get("tip")
    if component.get("fold"):
        key = f' data-afkv2-fold="fold-{html.escape(element)}"' if element else ""
        inner = (f'<details class="afkv2-fold"{key}><summary>{html.escape(component["fold"])}</summary>'
                 f'<div class="afkv2-fold-body">{inner}</div></details>')
    if not element and not style and not tip:
        return inner
    tag = "span" if kind.inline else "div"
    attrs = ""
    if element:
        attrs += f' id="{html.escape(element)}" data-afkv2-element="{html.escape(element)}"'
    if style:
        attrs += f' style="{html.escape(style)}"'
    if tip:
        attrs += f' data-afkv2-tip="{html.escape(tip)}"'
    return f"<{tag}{attrs}>{inner}</{tag}>"

"""Table (CMP-6): rows and cells; a cell is text or any component.

A table with an id gives each body row an HTML id. lavish names an annotation by the nearest ancestor id
within 5 elements, and a cell's table id is further away than that; `row_targets` maps a row to its table.
"""

from html import escape

from registry import register_component, render_component

ROW_ID = "afkv2-tr-{}-{}"


def nested_cells(props):
    return [(("rows", r, c), cell)
            for r, row in enumerate(props["rows"])
            for c, cell in enumerate(row) if isinstance(cell, dict)]


def check_rows(props):
    width = len(props["columns"])
    return [(("rows", r), f"has {len(row)} cells; the table has {width} columns")
            for r, row in enumerate(props["rows"]) if len(row) != width]


def _cell(cell):
    return escape(cell) if isinstance(cell, str) else render_component(cell)


def _row_ids(props):
    return [ROW_ID.format(props["id"], n) for n in range(1, len(props["rows"]) + 1)] if props.get("id") else []


def render_table(props, children):
    head = "".join(f'<th scope="col">{escape(name)}</th>' for name in props["columns"])
    ids = _row_ids(props) or [None] * len(props["rows"])
    rows = "".join((f'<tr id="{escape(row_id)}">' if row_id else "<tr>")
                   + "".join(f"<td>{_cell(cell)}</td>" for cell in row) + "</tr>"
                   for row_id, row in zip(ids, props["rows"]))
    return (f'<div class="afkv2-grid-wrap"><table class="afkv2-grid"><thead><tr>{head}</tr></thead>'
            f"<tbody>{rows}</tbody></table></div>" + "".join(children))


def row_targets(props):
    """An annotation on a body row, or on a cell in it, stands for the table."""
    return {row_id: props["id"] for row_id in _row_ids(props)}


register_component("table", {
    "type": "object", "additionalProperties": False, "required": ["columns", "rows"],
    "properties": {
        "columns": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "rows": {"type": "array", "minItems": 1, "items": {
            "type": "array",
            "items": {"anyOf": [{"type": "string"}, {"type": "object", "required": ["type"]}]},
        }},
    },
}, render_table, nested=nested_cells, check=check_rows, targets=row_targets, takes_id=True)

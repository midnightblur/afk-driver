"""Table (CMP-6): rows and cells; a cell is text or any component."""

from html import escape

from registry import register_component, render_component


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


def render_table(props, children):
    head = "".join(f'<th scope="col">{escape(name)}</th>' for name in props["columns"])
    rows = "".join("<tr>" + "".join(f"<td>{_cell(cell)}</td>" for cell in row) + "</tr>"
                   for row in props["rows"])
    return (f'<div class="afkv2-grid-wrap"><table class="afkv2-grid"><thead><tr>{head}</tr></thead>'
            f"<tbody>{rows}</tbody></table></div>" + "".join(children))


register_component("table", {
    "type": "object", "additionalProperties": False, "required": ["columns", "rows"],
    "properties": {
        "columns": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "rows": {"type": "array", "minItems": 1, "items": {
            "type": "array",
            "items": {"anyOf": [{"type": "string"}, {"type": "object", "required": ["type"]}]},
        }},
    },
}, render_table, nested=nested_cells, check=check_rows)

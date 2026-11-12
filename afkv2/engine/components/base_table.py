"""Table (CMP-6): rows and cells; a cell is text or any component.

A table with an id gives each body row an HTML id. lavish names an annotation by the nearest ancestor id
within 5 elements, and a cell's table id is further away than that; `row_targets` maps a row to its table, and
`row_labels` names the row, so a note on it keeps its row.
"""

from html import escape

from registry import register_component, render_component

ROW_ID = "afkv2-tr-{}-{}"
LABEL_LIMIT = 60


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


def _words(cell) -> str:
    text = cell if isinstance(cell, str) else next(
        (value for key in ("text", "label", "title") for value in [(cell.get("props") or {}).get(key)]
         if isinstance(value, str)), "")
    words = " ".join(text.split())
    return words if len(words) <= LABEL_LIMIT else words[:LABEL_LIMIT - 1] + "…"


def row_labels(props):
    """Each body row as `row <n> (<words>)`, the words of its first cell that holds a letter: a cell of a number
    only repeats the row number. `row <n>` when no cell holds a letter."""
    found = {}
    for n, (row_id, row) in enumerate(zip(_row_ids(props), props["rows"]), start=1):
        first = next((words for words in map(_words, row) if any(c.isalpha() for c in words)), "")
        found[row_id] = f"row {n} ({first})" if first else f"row {n}"
    return found


register_component("table", {
    "type": "object", "additionalProperties": False, "required": ["columns", "rows"],
    "properties": {
        "columns": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "rows": {"type": "array", "minItems": 1, "items": {
            "type": "array",
            "items": {"anyOf": [{"type": "string"}, {"type": "object", "required": ["type"]}]},
        }},
    },
}, render_table, nested=nested_cells, check=check_rows, targets=row_targets, takes_id=True, labels=row_labels)

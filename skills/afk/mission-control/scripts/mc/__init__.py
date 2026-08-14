"""mission-control renderer internals (M5) — Python stdlib only (ADR-0006).

Sub-packages:
- `vm` — the PanelVM / Absent value types (ADR-0007).
- `mdtable` — shared markdown section/table parsing helpers.
- `panels/` — the five per-panel parsers behind the registry.
- `template` — composes parsed panels into one self-contained HTML page.
- `server` — mtime-watch + serve (127.0.0.1), and the `--once` render path.
"""

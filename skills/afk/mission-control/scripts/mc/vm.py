"""Panel view-model contract (ADR-0007): parse(spec_dir) -> PanelVM | Absent.

A missing or unparseable source is a *value*, never an exception, so one
drifted artifact format degrades exactly one panel while the other four
still render.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanelVM:
    """A successfully parsed panel, ready for the template to compose.

    `html` is a pre-escaped, self-contained HTML fragment for the panel's
    card body (no external references — see the self-containment NFR).
    """

    panel_id: str
    title: str
    html: str


@dataclass(frozen=True)
class Absent:
    """A panel whose source artifact is missing or unparseable.

    Never raised as an exception — always returned as a value so the
    template can render an explicit empty-state card (AC-010).
    """

    panel_id: str
    reason: str

"""MC Understanding — derived from the post-ship understanding artifact at
`understanding/index.html` under the spec dir. Reads ONLY the artifact's
machine-readable `afk-understanding` meta header (generated date + diff SHA
range) — the sole parse target (SDD §4 row "Machine-readable header"; SDD §8
row "mission-control understanding panel"; SDD §14 row "Mission-control panel
registry").

Lockstep pair: the `afk-understanding` meta grammar owned by
`skills/afk/understand/UNDERSTANDING-FORMAT.md#afk-understanding` — a change to
the element name or its content fields is a same-commit change here.

Renders the artifact's repo-relative path as plain text plus chips for the two
fields — **no hyperlink** anywhere: the ship-snapshot copy relocates the
rendered dashboard file, breaking any relative link (SDD §14 panel row). Never
raises: a missing or malformed header returns `Absent(reason)` (SDD §14; format
contract "Well-formedness").
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from ..vm import Absent, PanelVM

PANEL_ID = "understanding"
PANEL_TITLE = "Understanding"

_ARTIFACT_RELPATH = ("understanding", "index.html")

# The single `<meta name="afk-understanding" …>` element (attribute order and
# line breaks tolerant). Fields are carried on data-* attributes, with the
# `content=` string as a fallback — both forms stamped by the shell asset.
_META_RE = re.compile(
    r"<meta\b[^>]*\bname\s*=\s*[\"']afk-understanding[\"'][^>]*>",
    re.IGNORECASE | re.DOTALL,
)
_GENERATED_ATTR_RE = re.compile(r"\bdata-generated\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
_DIFF_ATTR_RE = re.compile(r"\bdata-diff-range\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
_CONTENT_RE = re.compile(r"\bcontent\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
_CONTENT_GENERATED_RE = re.compile(r"generated\s*=\s*([^;]+)")
_CONTENT_DIFF_RE = re.compile(r"diff-range\s*=\s*([^;]+)")


def parse(spec_dir: Path):
    artifact = spec_dir.joinpath(*_ARTIFACT_RELPATH)
    if not artifact.is_file():
        return Absent(PANEL_ID, "understanding/index.html not found under the spec dir")

    text = artifact.read_text(encoding="utf-8", errors="replace")
    meta_match = _META_RE.search(text)
    if meta_match is None:
        return Absent(PANEL_ID, "no afk-understanding meta header in understanding/index.html")

    meta = meta_match.group(0)
    generated, diff_range = _extract_fields(meta)
    if not generated or not diff_range:
        return Absent(
            PANEL_ID,
            "afk-understanding meta header missing generated date or diff SHA range",
        )

    rel_path = _repo_relative(spec_dir, artifact)
    return PanelVM(PANEL_ID, PANEL_TITLE, _render(rel_path, generated, diff_range))


def _extract_fields(meta: str):
    generated_match = _GENERATED_ATTR_RE.search(meta)
    diff_match = _DIFF_ATTR_RE.search(meta)
    generated = generated_match.group(1).strip() if generated_match else ""
    diff_range = diff_match.group(1).strip() if diff_match else ""
    if generated and diff_range:
        return generated, diff_range

    # Fallback: the `content="generated=…; diff-range=…"` string.
    content_match = _CONTENT_RE.search(meta)
    if content_match:
        content = content_match.group(1)
        if not generated:
            cg = _CONTENT_GENERATED_RE.search(content)
            generated = cg.group(1).strip() if cg else generated
        if not diff_range:
            cd = _CONTENT_DIFF_RE.search(content)
            diff_range = cd.group(1).strip() if cd else diff_range
    return generated, diff_range


def _repo_relative(spec_dir: Path, artifact: Path) -> str:
    """Artifact path relative to the enclosing git checkout root; falls back to
    the path relative to the spec dir when no root is found."""
    current = spec_dir
    for _ in range(64):
        if (current / ".git").exists():  # a file in worktrees, a dir in the main checkout
            try:
                return artifact.relative_to(current).as_posix()
            except ValueError:
                break
        if current.parent == current:
            break
        current = current.parent
    return Path(*_ARTIFACT_RELPATH).as_posix()


def _render(rel_path: str, generated: str, diff_range: str) -> str:
    # Plain text path — NO anchor: the ship-snapshot copy relocates this file,
    # so any relative link would break (SDD §14 panel row).
    chip = "border:1px solid #22262f;border-radius:12px;padding:0.1rem 0.6rem;font-size:0.8rem;color:#aab"
    return "\n".join(
        [
            f'<div class="mc-understanding-path"><code>{html.escape(rel_path)}</code></div>',
            '<div class="mc-understanding-chips" style="display:flex;flex-wrap:wrap;gap:0.4rem;margin-top:0.5rem">',
            f'<span class="mc-chip" style="{chip}">generated {html.escape(generated)}</span>',
            f'<span class="mc-chip" style="{chip}">diff {html.escape(diff_range)}</span>',
            "</div>",
        ]
    )

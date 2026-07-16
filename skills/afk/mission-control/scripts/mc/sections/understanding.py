"""Understanding artifact card (surfaced inside Overview) — parses ONLY the
`afk-understanding` meta header of `understanding/index.html`.

Lockstep pair: grammar owned by
`skills/afk/understand/UNDERSTANDING-FORMAT.md#afk-understanding` — a change
to the element name or its content fields is a same-commit change here.

Returns a plain dict (or None + reason) rather than a SectionVM — Overview
embeds it as a card. No hyperlink is ever emitted for the path: the
ship-snapshot copy relocates the rendered dashboard file, breaking any
relative link (SDD §14 panel row).
"""
from __future__ import annotations

import re
from pathlib import Path

_ARTIFACT_RELPATH = ("understanding", "index.html")

_META_RE = re.compile(
    r"<meta\b[^>]*\bname\s*=\s*[\"']afk-understanding[\"'][^>]*>",
    re.IGNORECASE | re.DOTALL,
)
_GENERATED_ATTR_RE = re.compile(r"\bdata-generated\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
_DIFF_ATTR_RE = re.compile(r"\bdata-diff-range\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
_CONTENT_RE = re.compile(r"\bcontent\s*=\s*[\"']([^\"']*)[\"']", re.IGNORECASE)
_CONTENT_GENERATED_RE = re.compile(r"generated\s*=\s*([^;]+)")
_CONTENT_DIFF_RE = re.compile(r"diff-range\s*=\s*([^;]+)")


def parse(spec_dir: Path) -> tuple:
    """(card_dict | None, reason). card_dict = {path, generated, diff_range}."""
    artifact = spec_dir.joinpath(*_ARTIFACT_RELPATH)
    if not artifact.is_file():
        return None, "understanding/index.html not found under the spec dir"

    try:
        text = artifact.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return None, f"understanding/index.html could not be read: {exc.strerror or exc}"

    meta_match = _META_RE.search(text)
    if meta_match is None:
        return None, "no afk-understanding meta header in understanding/index.html"

    generated, diff_range = _extract_fields(meta_match.group(0))
    if not generated or not diff_range:
        return None, "afk-understanding meta header missing generated date or diff SHA range"

    return (
        {
            "path": _repo_relative(spec_dir, artifact),
            "generated": generated,
            "diff_range": diff_range,
        },
        "",
    )


def _extract_fields(meta: str):
    generated_match = _GENERATED_ATTR_RE.search(meta)
    diff_match = _DIFF_ATTR_RE.search(meta)
    generated = generated_match.group(1).strip() if generated_match else ""
    diff_range = diff_match.group(1).strip() if diff_match else ""
    if generated and diff_range:
        return generated, diff_range

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

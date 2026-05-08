"""Shared types for section-splice operations across format-specific impls.

A section splice preserves foreign prose around a driver-owned block within
a description (Jira parent description, GitLab MR description). Each format
has its own splicer (ADF tree walk vs plain-text marker pair); they share
this exception type and marker-identifier convention.

See ``CONTEXT.md`` for the section-splice / marker-pair / strict-mode terms.
"""

from __future__ import annotations


class SectionMarkerMissing(Exception):
    """Raised when a splicer is asked to operate on content whose marker pair
    is absent or malformed, and ``create_if_missing=False``.

    Malformed = one marker present without its mate, or end before start.
    Missing = neither marker present (callers can opt into auto-create via
    ``create_if_missing=True``).
    """


def marker_id_text(name: str) -> tuple[str, str]:
    """Return ``(start_text, end_text)`` for a marker pair named ``name``.

    The strings are the *bare identifier* — format-agnostic. Plaintext callers
    wrap them in HTML-comment delimiters (``<!-- ... -->``); ADF callers wrap
    them in paragraph nodes with an ``inline-code`` mark.
    """
    return f"afk:{name}:start", f"afk:{name}:end"

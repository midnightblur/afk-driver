#!/usr/bin/env afk-python
"""Validate, render, or audit the managed behavior registry.

Commands:
  behavior_registry.py validate [registry] [--plugin-root DIR] [--base-registry FILE] [--verbose]
  behavior_registry.py render [registry] [--plugin-root DIR] [--output FILE]
  behavior_registry.py audit [registry] [--plugin-root DIR] --target FILE [...]
      [--target-root FILE ROOT ENABLEMENT ...] [--ignore-unmanaged]

``validate`` checks the registry contract and the rendered byte ceiling; it is
silent on success unless ``--verbose``.
``render`` writes one ``afk:behaviors`` block. It never truncates the block.
``audit`` checks installed blocks without changing their target files.
``--target`` audits a file against the shared ``--plugin-root`` (its provider
is assumed enabled); ``--target-root FILE ROOT ENABLEMENT`` audits one file
against its own root (a target installed for one harness renders
``${AFK_PLUGIN_ROOT}`` as that harness's own root, not the root of whichever
harness is running the audit) and its own provider enablement state
(``enabled``, ``disabled``, or ``absent`` — anything but ``enabled`` rejects a
leftover marker there regardless of whether the root resolves).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import re
import subprocess
import sys
from typing import NamedTuple, Sequence


START = "<!-- afk:behaviors:start -->"
END = "<!-- afk:behaviors:end -->"
FIELD_RE = re.compile(
    r"^state: (active|retired) \| scope: (all-repos|configured-repos) "
    r"\| revision: ([0-9]+) \| doctrine: (.+)$"
)
# The plugin-source runner names a git outside the judged tree.
GIT = os.environ.get("AFK_JUDGE_GIT") or "git"
ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SECTION_RE = re.compile(r"(?m)^## ([^\r\n]+)\r?\n")
DOCTRINE_PATH_RE = re.compile(r"(?:^|[ `])([A-Za-z0-9_.\-/]+\.md)(?=$|[ `§])")
PROVIDER_TEXT_RE = re.compile(
    r"(?i)(?:\b(?:claude|codex|chatgpt|gemini|cursor)\b|~/\.(?:claude|codex)|CLAUDE_[A-Z_]+)"
)
# The binding unit is UTF-8 bytes of the rendered block, not a token count
# (AGREEMENT-2 §5, amended DEBATE-2 round 7): no tokenizer is named, so bytes
# are what the gate can prove. ~1,500 tokens is a rough estimate for this
# prose at ~4 bytes/token — an estimate only, never a guarantee, and never
# printed as a token count.
BODY_BYTE_LIMIT = 6000
DISPOSITIONS = {
    "registry",
    "fold",
    "retired",
    "tool-fact",
    "stack-fact",
    "existing-doctrine",
}
LEGACY_SENTINELS = ("plain-language", "lavish-sessions", "investigation")
REQUIRED_INSTALL_TESTS = (
    "test_install_migration_covers_h7_h8_h10_and_removes_duplicate_unified_blocks",
    "test_install_reuses_legacy_marker_as_consent",
    "test_teardown_removes_every_named_block_and_preserves_outside_bytes",
)
LEGACY_HEADINGS = (
    "## Reply standard: Simplified Technical English",
    "## Grilling sessions: render through lavish",
    "## Code questions: investigate to closure",
)
# Lockstep copy of the inventory IDs owned by hooks/behavior-dispositions.tsv.
# The fixed parser set makes a deleted disposition fail closed.
EXPECTED_INVENTORY_IDS = frozenset(
    {
        "adr-final-design-only",
        "always-open-a-pr",
        "automation-fully-autonomous-self-provision",
        "bug-fix-with-future-co-scaffold",
        "build-scope-matches-change",
        "check-prd-before-contract-fix",
        "ci-parity-before-push",
        "clear-stale-git-index-lock",
        "delegate-exploration",
        "diff-the-merge-first",
        "dogfood-verify-after-fix",
        "inference-marking",
        "instructions-only-what-reader-needs",
        "investigation-closure",
        "jira-get-fields",
        "l9-implementation-seam-grill",
        "lavish-grilling-render",
        "local-branch-no-pr-split",
        "mcp-tools-self-contained",
        "name-the-reader",
        "never-alter-db-directly",
        "no-autonomous-commits-on-protected-branches",
        "phase-review-gates",
        "prefer-instruction-over-hook",
        "prove-reachability-before-fixing",
        "reply-ste100",
        "run-readonly-commands-yourself",
        "spring-bean-constructor-context-test",
        "verify-commit-content-landed",
        "verify-external-state",
        "verify-gaps-before-planning",
        "verify-hardest-where-you-wrote-it",
        "verify-hibernate-behavior",
        "verify-jdk-spec-claims",
        "verify-version-spec-claims",
        "verify-without-asking",
        "vue3-bidirectional-watch-guard",
        "wiring-done-is-consumed",
        "rebuild-round-page",
        "never-reload-answering-page",
        "poll-lavish-tracked-job",
        "rationale-on-change",
        "render-lavish-repo-renderer",
        "worktree-per-session",
    }
)


class RegistryError(ValueError):
    """The registry does not satisfy its file contract."""


class Behavior(NamedTuple):
    id: str
    state: str
    scope: str
    revision: int
    doctrine: str
    self_contained: bool
    reason: str | None
    body: tuple[str, ...]


class Registry(NamedTuple):
    rows: tuple[Behavior, ...]

    @property
    def revision(self) -> int:
        return max(row.revision for row in self.rows)


def _split_sections(text: str) -> list[tuple[str, list[str]]]:
    matches = list(SECTION_RE.finditer(text))
    sections: list[tuple[str, list[str]]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[match.end() : end].replace("\r\n", "\n").split("\n")
        while content and not content[0]:
            content.pop(0)
        while content and not content[-1]:
            content.pop()
        sections.append((match.group(1).strip(), content))
    return sections


def _parse_registry_text(text: str, source: str) -> Registry:
    rows: list[Behavior] = []
    seen: set[str] = set()
    for behavior_id, content in _split_sections(text):
        if not ID_RE.fullmatch(behavior_id):
            raise RegistryError(f"invalid behavior id: {behavior_id}")
        if behavior_id in seen:
            raise RegistryError(f"duplicate behavior id: {behavior_id}")
        seen.add(behavior_id)
        if not content:
            raise RegistryError(f"{behavior_id}: missing field line")
        match = FIELD_RE.fullmatch(content[0])
        if not match:
            raise RegistryError(f"{behavior_id}: invalid field line")
        state, scope, revision_text, doctrine = match.groups()
        revision = int(revision_text)
        if revision < 1:
            raise RegistryError(f"{behavior_id}: revision must be positive")

        remaining = content[1:]
        self_contained = False
        if remaining and remaining[0] == "self-contained: yes":
            self_contained = True
            remaining.pop(0)
        reason = None
        if remaining and remaining[0].startswith("reason:"):
            reason = remaining.pop(0).removeprefix("reason:").strip()
        if any(not line for line in remaining):
            raise RegistryError(f"{behavior_id}: body contains a blank line")
        body = tuple(remaining)
        if state == "retired" and (body or reason or self_contained):
            raise RegistryError(f"{behavior_id}: retired behavior must have no body or reason")
        if state == "active" and not body:
            raise RegistryError(f"{behavior_id}: active behavior has no body")
        if len(body) > 4:
            raise RegistryError(f"{behavior_id}: body exceeds 4 lines")
        if len(body) > 2 and not reason:
            raise RegistryError(f"{behavior_id}: a 3-4 line body requires reason")
        if reason == "":
            raise RegistryError(f"{behavior_id}: reason must not be empty")
        rows.append(
            Behavior(behavior_id, state, scope, revision, doctrine, self_contained, reason, body)
        )
    if not rows:
        raise RegistryError(f"{source}: registry contains no behavior sections")
    return Registry(tuple(rows))


def parse_registry(path: pathlib.Path | str) -> Registry:
    registry_path = pathlib.Path(path)
    try:
        text = registry_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RegistryError(f"cannot read {registry_path}: {exc}") from exc
    return _parse_registry_text(text, str(registry_path))


def _render_body(registry: Registry, plugin_root: pathlib.Path) -> str:
    parts: list[str] = ["## All repositories"]
    for scope in ("all-repos", "configured-repos"):
        if scope == "configured-repos":
            parts.extend(
                [
                    "",
                    "## Configured repositories",
                    "Apply this section only when the repository contains `.afk/config.yaml`.",
                ]
            )
        emitted = False
        for row in registry.rows:
            if row.state != "active" or row.scope != scope:
                continue
            if emitted:
                parts.append("")
            parts.extend(row.body)
            emitted = True
    root_text = plugin_root.resolve().as_posix()
    return "\n".join(parts).replace("${AFK_PLUGIN_ROOT}", root_text) + "\n"


def render_registry(registry_path: pathlib.Path | str, plugin_root: pathlib.Path | str) -> str:
    registry = parse_registry(registry_path)
    body = _render_body(registry, pathlib.Path(plugin_root))
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return (
        f"{START}\nregistry-revision: {registry.revision}\nbody-sha256: {digest}\n"
        f"{body}{END}\n"
    )


def rendered_byte_count(text: str) -> int:
    """Return the UTF-8 byte length of a rendered block — the binding budget unit."""
    return len(text.encode("utf-8"))


def _normalized_heading(value: str) -> str:
    value = re.sub(r"[`*_]", "", value).strip().casefold()
    return re.sub(r"\s+", " ", value)


def _section_refs(section: str) -> list[str]:
    range_match = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", section)
    if not range_match:
        return [section]
    start, end = (int(value) for value in range_match.groups())
    if end < start:
        raise RegistryError(f"invalid doctrine section range: {section}")
    return [str(number) for number in range(start, end + 1)]


def _heading_matches(reference: str, heading: str) -> bool:
    reference = _normalized_heading(reference)
    heading = _normalized_heading(heading)
    if reference.isdigit():
        return re.match(rf"^{re.escape(reference)}(?:[.)]|\s|$)", heading) is not None
    if heading == reference:
        return True
    without_number = re.sub(r"^\d+(?:\.\d+)*[.)]?\s+", "", heading)
    return without_number == reference


def _validate_doctrine_section(row: Behavior, target: pathlib.Path, path_match: re.Match[str]) -> None:
    remainder = row.doctrine[path_match.end() :].strip()
    if not remainder:
        raise RegistryError(f"{row.id}: doctrine must include §section")
    if not remainder.startswith("§") or not remainder[1:].strip():
        raise RegistryError(f"{row.id}: invalid doctrine section reference: {remainder}")
    section = remainder[1:].strip()
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RegistryError(f"{row.id}: cannot read doctrine target: {target}: {exc}") from exc
    headings = re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", text)
    for reference in _section_refs(section):
        if not any(_heading_matches(reference, heading) for heading in headings):
            raise RegistryError(
                f"{row.id}: doctrine section does not exist in {target.name}: {reference}"
            )


def _validate_revisions(registry: Registry, base: Registry) -> None:
    base_by_id = {row.id: row for row in base.rows}
    current_by_id = {row.id: row for row in registry.rows}
    for behavior_id, base_row in base_by_id.items():
        if behavior_id not in current_by_id and base_row.state == "active":
            raise RegistryError(f"{behavior_id}: must be retired before deletion")
    for row in registry.rows:
        base_row = base_by_id.get(row.id)
        if base_row is None:
            continue
        if row.revision < base_row.revision:
            raise RegistryError(
                f"{row.id}: revision decreased from {base_row.revision} to {row.revision}"
            )
        if row != base_row and row.revision == base_row.revision:
            raise RegistryError(f"{row.id}: changed without a revision increase")
    if registry.revision < base.revision:
        raise RegistryError(
            f"registry revision decreased from {base.revision} to {registry.revision}"
        )


def _discover_base_registry(root: pathlib.Path) -> Registry | None:
    candidates: list[str] = []
    try:
        remote_head = subprocess.run(
            [GIT, "-C", str(root), "symbolic-ref", "refs/remotes/origin/HEAD", "--short"],
            check=False,
            capture_output=True,
            text=True,
        )
        if remote_head.returncode == 0 and remote_head.stdout.strip():
            candidates.append(remote_head.stdout.strip())
    except OSError:
        return None
    candidates.extend(("origin/main", "origin/master", "main", "master"))
    for candidate in dict.fromkeys(candidates):
        merge_base = subprocess.run(
            [GIT, "-C", str(root), "merge-base", "HEAD", candidate],
            check=False,
            capture_output=True,
            text=True,
        )
        if merge_base.returncode != 0 or not merge_base.stdout.strip():
            continue
        content = subprocess.run(
            [GIT, "-C", str(root), "show", f"{merge_base.stdout.strip()}:BEHAVIORS.md"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if content.returncode == 0:
            return _parse_registry_text(content.stdout, f"{candidate}:BEHAVIORS.md")
    return None


def validate_registry(
    registry_path: pathlib.Path | str,
    plugin_root: pathlib.Path | str,
    *,
    byte_limit: int = BODY_BYTE_LIMIT,
    dispositions: pathlib.Path | str | None = None,
    parity_root: pathlib.Path | str | None = None,
    base_registry: pathlib.Path | str | None = None,
) -> Registry:
    root = pathlib.Path(plugin_root).resolve()
    registry = parse_registry(registry_path)
    for row in registry.rows:
        if row.state != "active":
            continue
        matches = list(DOCTRINE_PATH_RE.finditer(row.doctrine))
        if len(matches) != 1:
            raise RegistryError(
                f"{row.id}: doctrine must name exactly one Markdown file; found {len(matches)}"
            )
        doctrine_path = matches[0].group(1)
        target = (root / doctrine_path).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise RegistryError(f"{row.id}: doctrine target leaves the plugin root") from exc
        if not target.is_file():
            raise RegistryError(f"{row.id}: doctrine target does not exist: {doctrine_path}")
        _validate_doctrine_section(row, target, matches[0])
        for line in row.body:
            provider_match = PROVIDER_TEXT_RE.search(line)
            if provider_match:
                raise RegistryError(
                    f"{row.id}: body contains provider-specific text: {provider_match.group(0)}"
                )
        if not row.self_contained:
            pointer = f"${{AFK_PLUGIN_ROOT}}/{doctrine_path}"
            if not any(pointer in line for line in row.body):
                raise RegistryError(
                    f"{row.id}: body is not independently actionable; "
                    "add a doctrine pointer or self-contained: yes"
                )
    rendered = render_registry(registry_path, root)
    count = rendered_byte_count(rendered)
    if count > byte_limit:
        raise RegistryError(f"rendered block is {count} bytes; limit is {byte_limit} bytes")
    if dispositions is not None:
        validate_dispositions(dispositions, registry)
    if parity_root is not None:
        validate_parity(parity_root)
    if base_registry is not None:
        _validate_revisions(registry, parse_registry(base_registry))
    elif parity_root is not None:
        base = _discover_base_registry(pathlib.Path(parity_root).resolve())
        if base is not None:
            _validate_revisions(registry, base)
    return registry


def validate_dispositions(path: pathlib.Path | str, registry: Registry) -> None:
    disposition_path = pathlib.Path(path)
    try:
        lines = disposition_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RegistryError(f"cannot read {disposition_path}: {exc}") from exc
    header = ["inventory_id", "class", "disposition", "behavior_id"]
    if not lines or lines[0].split("\t") != header:
        raise RegistryError("dispositions must start with inventory_id, class, disposition, behavior_id")
    active = {row.id for row in registry.rows if row.state == "active"}
    referenced: set[str] = set()
    inventory_ids: set[str] = set()
    for number, line in enumerate(lines[1:], 2):
        if not line:
            continue
        columns = line.split("\t")
        if len(columns) != 4:
            raise RegistryError(f"dispositions line {number}: expected 4 tab-separated columns")
        inventory_id, behavior_class, disposition, behavior_id = columns
        if not inventory_id:
            raise RegistryError(f"dispositions line {number}: empty inventory_id")
        if inventory_id in inventory_ids:
            raise RegistryError(f"duplicate inventory id: {inventory_id}")
        inventory_ids.add(inventory_id)
        if behavior_class != "team":
            raise RegistryError(f"{inventory_id}: class must be team")
        if disposition not in DISPOSITIONS:
            raise RegistryError(f"{inventory_id}: invalid disposition: {disposition}")
        if disposition == "registry":
            if behavior_id not in active:
                raise RegistryError(
                    f"{inventory_id}: registry behavior {behavior_id} does not resolve to an active row"
                )
            referenced.add(behavior_id)
        elif behavior_id != "-":
            raise RegistryError(f"{inventory_id}: non-registry disposition must use behavior_id '-'")
    if inventory_ids != EXPECTED_INVENTORY_IDS:
        missing_ids = sorted(EXPECTED_INVENTORY_IDS - inventory_ids)
        extra_ids = sorted(inventory_ids - EXPECTED_INVENTORY_IDS)
        raise RegistryError(
            "inventory set mismatch; "
            f"missing={','.join(missing_ids) or '-'}; extra={','.join(extra_ids) or '-'}"
        )
    missing = sorted(active - referenced)
    if missing:
        raise RegistryError(f"active behavior has no registry disposition: {', '.join(missing)}")


def _table_lookup(text: str, row_label: str) -> tuple[list[str] | None, list[str] | None]:
    """Return (header cells, row cells) for the Markdown table row whose first
    cell equals ``row_label``, scoped to the nearest header+separator above it."""
    lines = text.splitlines()

    def cells_of(line: str) -> list[str] | None:
        stripped = line.strip()
        if not stripped.startswith("|"):
            return None
        return [cell.strip() for cell in stripped.strip("|").split("|")]

    header: list[str] | None = None
    for index, line in enumerate(lines):
        cells = cells_of(line)
        if cells is None:
            continue
        following = cells_of(lines[index + 1]) if index + 1 < len(lines) else None
        if following is not None and all(re.fullmatch(r":?-+:?", c) for c in following if c):
            header = cells
            continue
        if header is not None and cells and cells[0] == row_label:
            return header, cells
    return None, None


def validate_parity(path: pathlib.Path | str) -> None:
    root = pathlib.Path(path).resolve()

    def read(relative: str) -> str:
        target = root / relative
        try:
            return target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RegistryError(f"parity file cannot be read: {relative}: {exc}") from exc

    manifest = read("skills/afk/setup/MANIFEST.md")
    for marker in ("afk:behaviors", *LEGACY_SENTINELS):
        if marker not in manifest:
            raise RegistryError(f"MANIFEST.md does not mention {marker}")

    harness_columns = ("Claude Code", "Codex CLI")

    def cell_value(cells: list[str], header: list[str], column: str) -> str:
        return cells[header.index(column)]

    def require_row(file_name: str, text: str, row_label: str, noun: str, predicate) -> None:
        header, row = _table_lookup(text, row_label)
        if header is None or any(column not in header for column in harness_columns):
            raise RegistryError(f"{file_name} does not declare {noun} for {', '.join(harness_columns)}")
        for column in harness_columns:
            if not predicate(cell_value(row, header, column)):
                raise RegistryError(f"{file_name} does not declare {noun} for {', '.join(harness_columns)}")

    providers = read("PROVIDERS.md")
    require_row(
        "PROVIDERS.md",
        providers,
        "Managed behavior",
        "managed behavior",
        lambda cell: "afk:behaviors" in cell,
    )

    capabilities = read("CAPABILITIES.md")
    require_row(
        "CAPABILITIES.md",
        capabilities,
        "`managed_behavior`",
        "managed_behavior",
        lambda cell: "afk:behaviors" in cell and "SessionStart drift notice" in cell,
    )

    install_tests = read("scripts/tests/test_install_block.py")
    for test_name in REQUIRED_INSTALL_TESTS:
        if not re.search(rf"(?m)^def {re.escape(test_name)}\(", install_tests):
            raise RegistryError(f"install and migration tests are missing executable install test: {test_name}")

    providers_root = root / "providers"
    copies = list(providers_root.rglob("BEHAVIORS.md")) if providers_root.exists() else []
    if copies:
        relative = ", ".join(str(item.relative_to(root)) for item in copies)
        raise RegistryError(f"provider registry copy is not allowed: {relative}")


def _sentinel_pattern(name: str) -> re.Pattern[str]:
    return re.compile(
        rf"<!-- afk:{re.escape(name)}:start -->.*?<!-- afk:{re.escape(name)}:end -->",
        re.DOTALL,
    )


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


_TEXT_MARKER_RE = re.compile(r"<!-- afk:([a-z0-9-]+):(start|end) -->")


def _marker_issues(text: str, names: Sequence[str]) -> list[str]:
    accepted = set(names)
    issues: list[str] = []
    opened: str | None = None
    for match in _TEXT_MARKER_RE.finditer(text):
        name, kind = match.group(1), match.group(2)
        if name not in accepted:
            continue
        if kind == "start":
            if opened is not None:
                issues.append(f"unmatched managed marker: nested start {name} inside {opened}")
                continue
            opened = name
            continue
        if opened is None:
            issues.append(f"unmatched managed marker: end {name} without a start")
            continue
        if opened != name:
            issues.append(f"unmatched managed marker: crossed end {name} while {opened} is open")
            continue
        opened = None
    if opened is not None:
        issues.append(f"unmatched managed marker: start {opened} without an end")
    return issues


class AuditResult(NamedTuple):
    state: str  # "opt-in-available" | "installed" | "drifted"
    findings: tuple[str, ...]
    installed_targets: int


def _body_signatures_for(registry: Registry, root: pathlib.Path) -> dict[str, set[str]]:
    body_signatures: dict[str, set[str]] = {}
    for row in registry.rows:
        if row.state != "active":
            continue
        rendered_lines = [
            line.replace("${AFK_PLUGIN_ROOT}", root.as_posix())
            for line in row.body
            if not re.match(r"^#{1,6}\s+", line)
        ]
        signatures = {_normalized_text(line) for line in rendered_lines if line.strip()}
        if len(rendered_lines) > 1:
            signatures.add(_normalized_text(" ".join(rendered_lines)))
        body_signatures[row.id] = signatures
    return body_signatures


def audit_targets(
    registry_path: pathlib.Path | str,
    plugin_root: pathlib.Path | str,
    targets: Sequence[
        pathlib.Path
        | str
        | tuple[pathlib.Path | str, pathlib.Path | str | None]
        | tuple[pathlib.Path | str, pathlib.Path | str | None, str | None]
    ],
    *,
    ignore_unmanaged: bool = False,
) -> AuditResult:
    """Audit every target. A plain path is checked against ``plugin_root``; a
    ``(target, root)`` pair is checked against its own root — a target
    installed for one harness renders ``${AFK_PLUGIN_ROOT}`` as that harness's
    own root, never whichever root a different harness happens to pass. A
    ``(target, None)`` pair (root ``None`` or empty) names a target whose
    installed root could not be independently verified: its content is still
    inspected for a leftover managed or legacy marker — the one check that
    needs no root — but is never compared against a rendered expected block,
    since there is no root to render one against.

    A ``(target, root, enablement)`` triple additionally names the target's
    provider enablement state. Omitted or ``"enabled"`` behaves exactly like
    the two-element form. Any other value (``"disabled"``, ``"absent"``, or
    any non-empty string that is not ``"enabled"``) names a target whose
    provider must not carry the block at all: its content is inspected for a
    leftover marker the same way, but reported as a disabled provider rather
    than an unresolved root — and this check takes precedence over root
    resolution, so a marker is rejected even when the root independently
    verifies."""
    validation_root = pathlib.Path(plugin_root).resolve()
    registry = validate_registry(registry_path, validation_root)
    behavior_pattern = _sentinel_pattern("behaviors")
    headings = {
        line.strip()
        for row in registry.rows
        if row.state == "active"
        for line in row.body
        if re.match(r"^#{1,6} ", line)
    }
    headings.update(LEGACY_HEADINGS)
    for row in registry.rows:
        if row.state == "active":
            headings.update((f"## {row.id}", f"### {row.id}"))
    path_suffixes = {
        line.split("${AFK_PLUGIN_ROOT}", 1)[1]
        for row in registry.rows
        if row.state == "active"
        for line in row.body
        if "${AFK_PLUGIN_ROOT}" in line
    }

    resolved_pairs: list[tuple[pathlib.Path, pathlib.Path]] = []
    unresolved_targets: list[pathlib.Path] = []
    disabled_targets: list[pathlib.Path] = []
    for item in targets:
        if isinstance(item, tuple):
            target_value = item[0]
            root_value = item[1] if len(item) > 1 else None
            enablement_value = item[2] if len(item) > 2 else None
            if enablement_value and enablement_value != "enabled":
                disabled_targets.append(pathlib.Path(target_value))
                continue
            if not root_value:
                unresolved_targets.append(pathlib.Path(target_value))
                continue
        else:
            target_value, root_value = item, plugin_root
        resolved_pairs.append((pathlib.Path(target_value), pathlib.Path(root_value).resolve()))

    expected_by_root: dict[pathlib.Path, str] = {}
    signatures_by_root: dict[pathlib.Path, dict[str, set[str]]] = {}

    def expected_for(root: pathlib.Path) -> str:
        if root not in expected_by_root:
            expected_by_root[root] = render_registry(registry_path, root).replace("\r\n", "\n").rstrip("\n")
        return expected_by_root[root]

    def signatures_for(root: pathlib.Path) -> dict[str, set[str]]:
        if root not in signatures_by_root:
            signatures_by_root[root] = _body_signatures_for(registry, root)
        return signatures_by_root[root]

    findings: list[str] = []
    target_texts: list[tuple[pathlib.Path, pathlib.Path, str]] = []
    missing_targets: list[pathlib.Path] = []
    for target, root in resolved_pairs:
        try:
            text = target.read_text(encoding="utf-8").replace("\r\n", "\n")
        except FileNotFoundError:
            missing_targets.append(target)
            continue
        except (OSError, UnicodeError) as exc:
            findings.append(f"{target}: cannot read target: {exc}")
            continue
        target_texts.append((target, root, text))

    unresolved_texts: list[tuple[pathlib.Path, str]] = []
    for target in unresolved_targets:
        try:
            text = target.read_text(encoding="utf-8").replace("\r\n", "\n")
        except FileNotFoundError:
            continue
        except (OSError, UnicodeError) as exc:
            findings.append(f"{target}: cannot read target: {exc}")
            continue
        unresolved_texts.append((target, text))

    disabled_texts: list[tuple[pathlib.Path, str]] = []
    for target in disabled_targets:
        try:
            text = target.read_text(encoding="utf-8").replace("\r\n", "\n")
        except FileNotFoundError:
            continue
        except (OSError, UnicodeError) as exc:
            findings.append(f"{target}: cannot read target: {exc}")
            continue
        disabled_texts.append((target, text))

    marker_names = ("behaviors", *LEGACY_SENTINELS)

    def _has_any_marker(text: str) -> bool:
        return any(
            f"<!-- afk:{name}:start -->" in text or f"<!-- afk:{name}:end -->" in text
            for name in marker_names
        )

    has_opt_in = (
        any(_has_any_marker(text) for _target, _root, text in target_texts)
        or any(_has_any_marker(text) for _target, text in unresolved_texts)
        or any(_has_any_marker(text) for _target, text in disabled_texts)
    )
    if not has_opt_in:
        return AuditResult("opt-in-available", (), 0)

    findings.extend(f"{target}: missing target file after behavior opt-in" for target in missing_targets)
    for target, text in unresolved_texts:
        if _has_any_marker(text):
            findings.append(
                f"{target}: managed behavior block present but its installed root could not be "
                "verified — check the provider's install"
            )
    for target, text in disabled_texts:
        if _has_any_marker(text):
            findings.append(
                f"{target}: managed behavior block present but its provider is not enabled — "
                "remove it or run /afk:setup teardown"
            )

    installed_targets = 0
    for target, root, text in target_texts:
        marker_issues = _marker_issues(text, marker_names)
        if marker_issues:
            findings.extend(f"{target}: {issue}" for issue in marker_issues)
            continue
        target_ok = True
        expected = expected_for(root)
        blocks = behavior_pattern.findall(text)
        if not blocks:
            findings.append(f"{target}: missing behaviors block")
            target_ok = False
        if len(blocks) > 1:
            findings.append(f"{target}: duplicate behaviors blocks ({len(blocks)})")
            target_ok = False
        for block in blocks:
            if block != expected:
                findings.append(f"{target}: stale behaviors block")
                target_ok = False
            for suffix in path_suffixes:
                if suffix in block and f"{root.as_posix()}{suffix}" not in block:
                    findings.append(f"{target}: installed plugin path is outside the active plugin root")
                    target_ok = False
                    break
        unmanaged = behavior_pattern.sub("", text)
        for name in LEGACY_SENTINELS:
            legacy_pattern = _sentinel_pattern(name)
            if legacy_pattern.search(unmanaged):
                findings.append(f"{target}: legacy sentinel {name} remains")
                target_ok = False
            unmanaged = legacy_pattern.sub("", unmanaged)
        if not ignore_unmanaged:
            for heading in sorted(headings):
                if re.search(rf"(?m)^{re.escape(heading)}\s*$", unmanaged):
                    findings.append(
                        f"{target}: likely duplicate behavior heading outside sentinels: {heading}"
                    )
                    target_ok = False
            normalized_unmanaged = _normalized_text(unmanaged)
            for behavior_id, signatures in signatures_for(root).items():
                if any(signature and signature in normalized_unmanaged for signature in signatures):
                    findings.append(
                        f"{target}: likely duplicate behavior text outside sentinels: {behavior_id}"
                    )
                    target_ok = False
        if target_ok:
            installed_targets += 1
    state = "drifted" if findings else "installed"
    return AuditResult(state, tuple(findings), installed_targets)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("registry_positional", nargs="?", type=pathlib.Path, metavar="registry")
    parser.add_argument("--registry", dest="registry_option", type=pathlib.Path)
    parser.add_argument("--plugin-root", type=pathlib.Path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    _add_common(validate_parser)
    validate_parser.add_argument("--dispositions", type=pathlib.Path)
    validate_parser.add_argument("--parity-root", type=pathlib.Path)
    validate_parser.add_argument("--base-registry", type=pathlib.Path)
    validate_parser.add_argument("--byte-limit", type=int, default=BODY_BYTE_LIMIT)
    validate_parser.add_argument("--verbose", action="store_true", help="print the row count and byte size on success")

    render_parser = subparsers.add_parser("render")
    _add_common(render_parser)
    render_parser.add_argument("--output", type=pathlib.Path)
    render_parser.add_argument("--byte-limit", type=int, default=BODY_BYTE_LIMIT)

    audit_parser = subparsers.add_parser("audit")
    _add_common(audit_parser)
    audit_parser.add_argument("--target", action="append", type=pathlib.Path, default=[])
    audit_parser.add_argument(
        "--target-root",
        action="append",
        nargs=3,
        metavar=("TARGET", "ROOT", "ENABLEMENT"),
        default=[],
    )
    audit_parser.add_argument("--ignore-unmanaged", action="store_true")

    args = parser.parse_args(argv)
    if args.registry_positional is not None and args.registry_option is not None:
        parser.error("registry must be supplied either positionally or with --registry, not both")
    default_root = pathlib.Path(__file__).resolve().parents[1]
    root = (args.plugin_root or default_root).resolve()
    registry_path = args.registry_option or args.registry_positional or root / "BEHAVIORS.md"
    try:
        if args.command == "validate":
            registry = validate_registry(
                registry_path,
                root,
                byte_limit=args.byte_limit,
                dispositions=args.dispositions,
                parity_root=args.parity_root,
                base_registry=args.base_registry,
            )
            if args.verbose:
                count = rendered_byte_count(render_registry(registry_path, root))
                print(f"valid: {len(registry.rows)} rows; revision={registry.revision}; bytes={count}")
            return 0
        if args.command == "render":
            validate_registry(registry_path, root, byte_limit=args.byte_limit)
            block = render_registry(registry_path, root)
            if args.output:
                args.output.write_text(block, encoding="utf-8", newline="\n")
            else:
                sys.stdout.write(block)
            return 0
        if not args.target and not args.target_root:
            parser.error("audit requires --target or --target-root")
        try:
            targets = [*args.target, *((t, r, e) for t, r, e in args.target_root)]
            result = audit_targets(
                registry_path,
                root,
                targets,
                ignore_unmanaged=args.ignore_unmanaged,
            )
        except (RegistryError, OSError) as exc:
            # A broken registry or unreadable input is a tool/config problem,
            # never real drift: exit 2 so a caller (behavior-drift.sh) never
            # tells the user their installed block is stale when it cannot
            # even check.
            print(f"behavior_registry: {exc}", file=sys.stderr)
            return 2
        if result.state == "opt-in-available":
            print("opt-in available; no managed block installed")
            return 0
        if result.state == "drifted":
            for finding in result.findings:
                print(finding, file=sys.stderr)
            return 1
        print(f"valid: {result.installed_targets} installed target(s)")
        return 0
    except RegistryError as exc:
        print(f"behavior_registry: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"behavior_registry: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

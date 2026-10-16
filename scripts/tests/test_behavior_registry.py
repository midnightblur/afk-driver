import hashlib
import importlib.util
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "behavior_registry.py"


def load_module():
    spec = importlib.util.spec_from_file_location("behavior_registry", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def registry_text():
    return """# Behaviors

## concise-replies
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
### Concise replies
Use short sentences.

## configured-checks
state: active | scope: configured-repos | revision: 1 | doctrine: VERIFY.md §Checks
Run `${AFK_PLUGIN_ROOT}/scripts/check.py` when the repository has `.afk/config.yaml`.

## old-rule
state: retired | scope: all-repos | revision: 2 | doctrine: LANGUAGE.md
"""


def write_registry(tmp_path, text, *, add_self_contained=True):
    (tmp_path / "LANGUAGE.md").write_text(
        "# Language\n\n## 1. Sentences\n\n## 2. Terms\n", encoding="utf-8"
    )
    (tmp_path / "VERIFY.md").write_text("# Verify\n\n## Checks\n", encoding="utf-8")
    if add_self_contained:
        text = re.sub(
            r"(^state: active \|[^\n]+\n)(?!self-contained: yes\n)",
            r"\1self-contained: yes\n",
            text,
            flags=re.MULTILINE,
        )
    path = tmp_path / "BEHAVIORS.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_and_render_exact_scopes_hash_and_root_substitution(tmp_path, registry_text):
    behavior_registry = load_module()
    registry_path = write_registry(tmp_path, registry_text)

    block = behavior_registry.render_registry(registry_path, tmp_path)

    assert block.startswith("<!-- afk:behaviors:start -->\nregistry-revision: 2\n")
    assert "## All repositories\n### Concise replies\nUse short sentences." in block
    assert "## Configured repositories\n" in block
    assert "Apply this section only when the repository contains `.afk/config.yaml`." in block
    assert f"{tmp_path.as_posix()}/scripts/check.py" in block
    assert "${AFK_PLUGIN_ROOT}" not in block
    assert "old-rule" not in block

    lines = block.splitlines()
    claimed_hash = lines[2].removeprefix("body-sha256: ")
    body = "\n".join(lines[3:-1]) + "\n"
    assert claimed_hash == hashlib.sha256(body.encode("utf-8")).hexdigest()


def test_validate_rejects_a_missing_doctrine_target(tmp_path):
    behavior_registry = load_module()
    registry_path = tmp_path / "BEHAVIORS.md"
    registry_path.write_text(
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: MISSING.md §Missing
Apply the rule.
""",
        encoding="utf-8",
    )

    with pytest.raises(behavior_registry.RegistryError, match="doctrine target does not exist"):
        behavior_registry.validate_registry(registry_path, tmp_path)


def test_validate_requires_exactly_one_doctrine_path(tmp_path):
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md and VERIFY.md
Apply the rule.
""",
    )

    with pytest.raises(behavior_registry.RegistryError, match="exactly one Markdown file"):
        behavior_registry.validate_registry(registry_path, tmp_path)


def test_validate_doctrine_section_ranges_and_numbered_headings(tmp_path):
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1–2
Apply the rule.
""",
    )
    behavior_registry.validate_registry(registry_path, tmp_path)

    registry_path.write_text(
        registry_path.read_text(encoding="utf-8").replace("§1–2", "§Missing section"),
        encoding="utf-8",
    )
    with pytest.raises(behavior_registry.RegistryError, match="doctrine section does not exist"):
        behavior_registry.validate_registry(registry_path, tmp_path)


def test_validate_rejects_doctrine_without_section(tmp_path):
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md
Apply the rule.
""",
    )

    with pytest.raises(behavior_registry.RegistryError, match="must include §section"):
        behavior_registry.validate_registry(registry_path, tmp_path)


def test_validate_requires_actionable_body_or_self_contained_metadata(tmp_path):
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Apply the rule.
""",
        add_self_contained=False,
    )

    with pytest.raises(behavior_registry.RegistryError, match="not independently actionable"):
        behavior_registry.validate_registry(registry_path, tmp_path)

    registry_path.write_text(
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Read `${AFK_PLUGIN_ROOT}/LANGUAGE.md` §1 before applying the rule.
""",
        encoding="utf-8",
    )
    behavior_registry.validate_registry(registry_path, tmp_path)


def test_production_reply_behavior_loads_language_sections_one_and_two():
    behavior_registry = load_module()
    registry = behavior_registry.parse_registry(ROOT / "BEHAVIORS.md")
    reply = next(row for row in registry.rows if row.id == "reply-ste100")

    assert "${AFK_PLUGIN_ROOT}/LANGUAGE.md" in "\n".join(reply.body)
    assert "§1–2" in "\n".join(reply.body)


def test_production_ci_parity_behavior_reaches_every_repository():
    behavior_registry = load_module()
    registry = behavior_registry.parse_registry(ROOT / "BEHAVIORS.md")
    row = next(row for row in registry.rows if row.id == "ci-parity-before-push")

    assert (row.state, row.scope, row.self_contained) == ("active", "all-repos", True)
    assert row.doctrine == "VERIFICATION.md §Before a push"
    assert "## Before a push" in (ROOT / "VERIFICATION.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("field", "body", "message"),
    [
        (
            "state: active | scope: wrong | revision: 1 | doctrine: LANGUAGE.md",
            "Apply it.",
            "invalid field line",
        ),
        (
            "state: active | scope: all-repos | revision: 0 | doctrine: LANGUAGE.md",
            "Apply it.",
            "revision must be positive",
        ),
        (
            "state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md",
            "One.\nTwo.\nThree.",
            "requires reason",
        ),
        (
            "state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md",
            "One.\nTwo.\nThree.\nFour.\nFive.",
            "exceeds 4 lines",
        ),
    ],
)
def test_parse_rejects_invalid_core_rows(tmp_path, field, body, message):
    behavior_registry = load_module()
    registry_path = write_registry(tmp_path, f"## rule\n{field}\n{body}\n")

    with pytest.raises(behavior_registry.RegistryError, match=message):
        behavior_registry.parse_registry(registry_path)


def test_validate_rejects_provider_text_and_budget_overflow(tmp_path):
    behavior_registry = load_module()
    provider_registry = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Write this only for Claude.
""",
    )
    with pytest.raises(behavior_registry.RegistryError, match="provider-specific"):
        behavior_registry.validate_registry(provider_registry, tmp_path)

    large_registry = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
reason: This body needs four lines.
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB
CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD
""",
    )
    with pytest.raises(behavior_registry.RegistryError, match="limit is 10 bytes"):
        behavior_registry.validate_registry(large_registry, tmp_path, byte_limit=10)


def test_byte_count_is_utf8_byte_length():
    behavior_registry = load_module()

    assert behavior_registry.rendered_byte_count("a" * 1499) == 1499
    assert behavior_registry.rendered_byte_count("a" * 1501) == 1501
    assert behavior_registry.rendered_byte_count("😀") == 4


def test_validate_enforces_the_6000_byte_cap_at_its_exact_boundary(tmp_path):
    behavior_registry = load_module()
    # ${AFK_PLUGIN_ROOT} is a fixed placeholder text, not the final substituted
    # root, so the rendered byte count this test targets is the body text plus
    # the fixed frame (heading, sentinel lines) — pad with an exact-width body
    # line and assert the boundary against the real render, never a hardcoded
    # frame-size guess.
    def registry_with_body_bytes(body: str) -> Path:
        return write_registry(
            tmp_path,
            f"""## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
self-contained: yes
{body}
""",
        )

    def rendered_bytes(body: str) -> int:
        path = registry_with_body_bytes(body)
        return behavior_registry.rendered_byte_count(
            behavior_registry.render_registry(path, tmp_path)
        )

    body = "A"
    baseline = rendered_bytes(body)
    # Grow the body by exactly the bytes needed to land on, then past, the cap.
    at_cap = "A" * (len(body) + (behavior_registry.BODY_BYTE_LIMIT - baseline))
    over_cap = at_cap + "A"

    behavior_registry.validate_registry(registry_with_body_bytes(at_cap), tmp_path)
    with pytest.raises(behavior_registry.RegistryError, match=r"is 6001 bytes; limit is 6000 bytes"):
        behavior_registry.validate_registry(registry_with_body_bytes(over_cap), tmp_path)


def test_validate_dispositions_cover_inventory_and_active_rows(tmp_path):
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Apply it.
""",
    )
    dispositions = tmp_path / "dispositions.tsv"
    rows = []
    for inventory_id in sorted(behavior_registry.EXPECTED_INVENTORY_IDS):
        if inventory_id == "reply-ste100":
            rows.append(f"{inventory_id}\tteam\tregistry\trule")
        else:
            rows.append(f"{inventory_id}\tteam\tfold\t-")
    dispositions.write_text(
        "inventory_id\tclass\tdisposition\tbehavior_id\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )

    behavior_registry.validate_registry(registry_path, tmp_path, dispositions=dispositions)

    dispositions.write_text(
        dispositions.read_text(encoding="utf-8").replace(
            "reply-ste100\tteam\tregistry\trule",
            "reply-ste100\tteam\tregistry\tmissing",
        ),
        encoding="utf-8",
    )
    with pytest.raises(behavior_registry.RegistryError, match="does not resolve to an active"):
        behavior_registry.validate_registry(registry_path, tmp_path, dispositions=dispositions)

    dispositions.write_text(
        "inventory_id\tclass\tdisposition\tbehavior_id\n" + "\n".join(rows[1:]) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(behavior_registry.RegistryError, match="inventory set mismatch"):
        behavior_registry.validate_registry(registry_path, tmp_path, dispositions=dispositions)

    dispositions.write_text(
        "inventory_id\tclass\tdisposition\tbehavior_id\n"
        + "\n".join(rows).replace("\tteam\t", "\tpersonal\t", 1)
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(behavior_registry.RegistryError, match="class must be team"):
        behavior_registry.validate_registry(registry_path, tmp_path, dispositions=dispositions)


def test_revision_check_compares_ids_to_an_explicit_base(tmp_path):
    behavior_registry = load_module()
    base = write_registry(
        tmp_path,
        """## early
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Early.

## late
state: active | scope: all-repos | revision: 4 | doctrine: LANGUAGE.md §1
Late.
""",
    )
    base = tmp_path / "BASE.md"
    base.write_text((tmp_path / "BEHAVIORS.md").read_text(encoding="utf-8"), encoding="utf-8")
    current = write_registry(
        tmp_path,
        """## early
state: active | scope: all-repos | revision: 5 | doctrine: LANGUAGE.md §1
Early.

## late
state: active | scope: all-repos | revision: 4 | doctrine: LANGUAGE.md §1
Late.

## new
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
New.
""",
    )
    behavior_registry.validate_registry(current, tmp_path, base_registry=base)

    current.write_text(
        current.read_text(encoding="utf-8").replace(
            "## late\nstate: active | scope: all-repos | revision: 4",
            "## late\nstate: active | scope: all-repos | revision: 3",
        ),
        encoding="utf-8",
    )
    with pytest.raises(behavior_registry.RegistryError, match="late: revision decreased"):
        behavior_registry.validate_registry(current, tmp_path, base_registry=base)


@pytest.mark.parametrize(
    ("current_field", "current_body"),
    [
        (
            "state: active | scope: all-repos | revision: 4 | doctrine: LANGUAGE.md §1",
            "Changed.",
        ),
        (
            "state: active | scope: configured-repos | revision: 4 | doctrine: LANGUAGE.md §1",
            "Original.",
        ),
        (
            "state: active | scope: all-repos | revision: 4 | doctrine: LANGUAGE.md §2",
            "Original.",
        ),
        (
            "state: retired | scope: all-repos | revision: 4 | doctrine: LANGUAGE.md §1",
            "",
        ),
    ],
)
def test_revision_must_increase_for_any_row_change(tmp_path, current_field, current_body):
    behavior_registry = load_module()
    base = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 4 | doctrine: LANGUAGE.md §1
Original.
""",
    )
    base = tmp_path / "BASE.md"
    base.write_text((tmp_path / "BEHAVIORS.md").read_text(encoding="utf-8"), encoding="utf-8")
    current = write_registry(
        tmp_path,
        f"## rule\n{current_field}\n{current_body}\n",
    )

    with pytest.raises(behavior_registry.RegistryError, match="changed without a revision increase"):
        behavior_registry.validate_registry(current, tmp_path, base_registry=base)


def test_active_row_must_be_retired_before_deletion_and_global_revision_cannot_drop(tmp_path):
    behavior_registry = load_module()
    base = write_registry(
        tmp_path,
        """## keep
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Keep.

## remove
state: active | scope: all-repos | revision: 8 | doctrine: LANGUAGE.md §1
Remove.
""",
    )
    base = tmp_path / "BASE.md"
    base.write_text((tmp_path / "BEHAVIORS.md").read_text(encoding="utf-8"), encoding="utf-8")
    current = write_registry(
        tmp_path,
        """## keep
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Keep.
""",
    )
    with pytest.raises(behavior_registry.RegistryError, match="must be retired before deletion"):
        behavior_registry.validate_registry(current, tmp_path, base_registry=base)

    base.write_text(
        base.read_text(encoding="utf-8")
        .replace("state: active | scope: all-repos | revision: 8", "state: retired | scope: all-repos | revision: 8")
        .replace("self-contained: yes\nRemove.\n", ""),
        encoding="utf-8",
    )
    with pytest.raises(behavior_registry.RegistryError, match="registry revision decreased"):
        behavior_registry.validate_registry(current, tmp_path, base_registry=base)


def test_audit_reports_missing_stale_duplicate_legacy_and_unmanaged_heading(tmp_path, registry_text):
    behavior_registry = load_module()
    registry_path = write_registry(tmp_path, registry_text)
    expected = behavior_registry.render_registry(registry_path, tmp_path)

    clean = tmp_path / "clean.md"
    clean.write_text(f"human before\n{expected}human after\n", encoding="utf-8")
    assert behavior_registry.audit_targets(registry_path, tmp_path, [clean]).state == "installed"

    bad = tmp_path / "bad.md"
    stale = expected.replace(tmp_path.as_posix(), "/old/plugin")
    bad.write_text(
        "### Concise replies\nHuman copy.\n"
        + stale
        + expected
        + "<!-- afk:plain-language:start -->\nold\n<!-- afk:plain-language:end -->\n",
        encoding="utf-8",
    )
    findings = behavior_registry.audit_targets(registry_path, tmp_path, [bad]).findings
    assert any("duplicate behaviors blocks" in item for item in findings)
    assert any("legacy sentinel plain-language" in item for item in findings)
    assert any("installed plugin path is outside" in item for item in findings)
    assert any("likely duplicate behavior heading" in item for item in findings)

    duplicate_text = tmp_path / "duplicate-text.md"
    duplicate_text.write_text(
        expected + "\n  USE   SHORT sentences.  \n", encoding="utf-8"
    )
    assert any(
        "likely duplicate behavior text" in item
        for item in behavior_registry.audit_targets(registry_path, tmp_path, [duplicate_text]).findings
    )
    assert behavior_registry.audit_targets(
        registry_path, tmp_path, [duplicate_text], ignore_unmanaged=True
    ).findings == ()

    opted_out = tmp_path / "opted-out.md"
    opted_out.write_text("human\n", encoding="utf-8")
    assert behavior_registry.audit_targets(registry_path, tmp_path, [opted_out]).state == "opt-in-available"

    assert "missing behaviors block" in behavior_registry.audit_targets(
        registry_path, tmp_path, [clean, opted_out]
    ).findings[0]

    missing = tmp_path / "does-not-exist.md"
    assert behavior_registry.audit_targets(registry_path, tmp_path, [missing]).state == "opt-in-available"
    assert any(
        "missing target file" in item
        for item in behavior_registry.audit_targets(registry_path, tmp_path, [clean, missing]).findings
    )

    second_clean = tmp_path / "second-clean.md"
    second_clean.write_text(expected, encoding="utf-8")
    result = behavior_registry.audit_targets(registry_path, tmp_path, [clean, second_clean])
    assert result.state == "installed"
    assert result.installed_targets == 2

    malformed = tmp_path / "malformed.md"
    malformed.write_text(
        "<!-- afk:behaviors:start -->\n"
        "<!-- afk:plain-language:end -->\n",
        encoding="utf-8",
    )
    result = behavior_registry.audit_targets(registry_path, tmp_path, [malformed])
    assert result.state == "drifted"
    assert sum("unmatched managed marker" in item for item in result.findings) == 2


def test_audit_targets_compares_each_target_against_its_own_root(tmp_path, registry_text):
    """A2-004: a target installed for one harness renders ${AFK_PLUGIN_ROOT} as
    that harness's own root; comparing it against a different shared root
    falsely reports it stale."""
    behavior_registry = load_module()
    registry_path = write_registry(tmp_path, registry_text)
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    root_a.mkdir()
    root_b.mkdir()

    target_a = tmp_path / "a.md"
    target_a.write_text(behavior_registry.render_registry(registry_path, root_a), encoding="utf-8")
    target_b = tmp_path / "b.md"
    target_b.write_text(behavior_registry.render_registry(registry_path, root_b), encoding="utf-8")

    shared = behavior_registry.audit_targets(registry_path, tmp_path, [target_a, target_b])
    assert shared.state == "drifted"
    assert any("stale behaviors block" in item for item in shared.findings)

    per_target = behavior_registry.audit_targets(
        registry_path, tmp_path, [(target_a, root_a), (target_b, root_b)]
    )
    assert per_target.state == "installed"
    assert per_target.installed_targets == 2

    # A mix of plain paths (shared root) and (target, root) pairs is legal —
    # the CLI's --target and --target-root map onto exactly this shape.
    target_a.write_text(behavior_registry.render_registry(registry_path, tmp_path), encoding="utf-8")
    mixed = behavior_registry.audit_targets(
        registry_path, tmp_path, [target_a, (target_b, root_b)]
    )
    assert mixed.state == "installed"
    assert mixed.installed_targets == 2


def test_audit_targets_validates_structure_against_plugin_root_not_target_root(tmp_path, registry_text):
    """The registry's own doctrine files live at plugin_root regardless of
    which installed root a target's rendered block substitutes."""
    behavior_registry = load_module()
    registry_path = write_registry(tmp_path, registry_text)
    other_root = tmp_path / "other-root"
    other_root.mkdir()
    target = tmp_path / "a.md"
    target.write_text(behavior_registry.render_registry(registry_path, other_root), encoding="utf-8")

    result = behavior_registry.audit_targets(registry_path, tmp_path, [(target, other_root)])
    assert result.state == "installed"


def test_audit_flags_a_leftover_marker_when_its_root_is_unresolved(tmp_path, registry_text):
    """A3-003: a provider whose root cannot resolve (e.g. left disabled after
    a prior opt-in) must not go unaudited — a leftover managed block there is
    exactly the drift Agreement §4.3 requires catching, and omitting the
    target instead of flagging it would hide it."""
    behavior_registry = load_module()
    registry_path = write_registry(tmp_path, registry_text)
    root = tmp_path / "root"
    root.mkdir()
    resolved_target = tmp_path / "a.md"
    resolved_target.write_text(behavior_registry.render_registry(registry_path, root), encoding="utf-8")

    orphaned = tmp_path / "orphaned.md"
    orphaned.write_text(
        "<!-- afk:behaviors:start -->\nstale content\n<!-- afk:behaviors:end -->\n",
        encoding="utf-8",
    )

    result = behavior_registry.audit_targets(
        registry_path, tmp_path, [(resolved_target, root), (orphaned, None)]
    )
    assert result.state == "drifted"
    assert any(
        "managed behavior block present but its installed root could not be verified" in item
        for item in result.findings
    )
    # The empty-string CLI spelling (argparse `--target-root TARGET ""`) means
    # the same thing as `None`.
    result_empty_string = behavior_registry.audit_targets(
        registry_path, tmp_path, [(resolved_target, root), (orphaned, "")]
    )
    assert result_empty_string.state == "drifted"


def test_audit_rejects_a_disabled_providers_marker_even_when_its_root_resolves(tmp_path, registry_text):
    """A4-001: enablement is a separate axis from root resolution — a provider
    that is installed (root resolves) but turned off must still reject a
    leftover block, the same as an uninstalled one. 1 enabled provider with a
    clean install must not hide the finding for the other, disabled provider;
    both roots resolve in this test."""
    behavior_registry = load_module()
    registry_path = write_registry(tmp_path, registry_text)
    root_enabled = tmp_path / "root-enabled"
    root_disabled = tmp_path / "root-disabled"
    root_enabled.mkdir()
    root_disabled.mkdir()
    target_enabled = tmp_path / "enabled.md"
    target_enabled.write_text(
        behavior_registry.render_registry(registry_path, root_enabled), encoding="utf-8"
    )
    target_disabled = tmp_path / "disabled.md"
    target_disabled.write_text(
        behavior_registry.render_registry(registry_path, root_disabled), encoding="utf-8"
    )

    result = behavior_registry.audit_targets(
        registry_path,
        tmp_path,
        [
            (target_enabled, root_enabled, "enabled"),
            (target_disabled, root_disabled, "disabled"),
        ],
    )
    assert result.state == "drifted"
    disabled_findings = [item for item in result.findings if str(target_disabled) in item]
    enabled_findings = [item for item in result.findings if str(target_enabled) in item]
    assert any("its provider is not enabled" in item for item in disabled_findings)
    assert enabled_findings == []


def test_audit_leaves_an_unresolved_root_target_out_of_opt_in_available_when_it_has_no_marker(
    tmp_path, registry_text
):
    """A target whose root cannot resolve and carries no marker is simply not
    opted in — the same as any other never-installed target, not a finding."""
    behavior_registry = load_module()
    registry_path = write_registry(tmp_path, registry_text)
    untouched = tmp_path / "untouched.md"
    untouched.write_text("# just a normal file\n", encoding="utf-8")

    result = behavior_registry.audit_targets(registry_path, tmp_path, [(untouched, None)])
    assert result.state == "opt-in-available"
    assert result.findings == ()


def test_parity_check_covers_setup_providers_capability_tests_and_no_copy(tmp_path):
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Apply it.
""",
    )
    (tmp_path / "skills" / "afk" / "setup").mkdir(parents=True)
    (tmp_path / "skills" / "afk" / "setup" / "MANIFEST.md").write_text(
        "afk:behaviors plain-language lavish-sessions investigation",
        encoding="utf-8",
    )
    (tmp_path / "PROVIDERS.md").write_text(
        "| Concern | Claude Code | Codex CLI |\n"
        "|---|---|---|\n"
        "| Managed behavior | `afk:behaviors` sentinel in user steering | `afk:behaviors` sentinel in user steering |\n",
        encoding="utf-8",
    )
    (tmp_path / "CAPABILITIES.md").write_text(
        "| Capability | Claude Code | Codex CLI | Required degradation |\n"
        "|---|---|---|---|\n"
        "| `managed_behavior` | Setup-managed `afk:behaviors` block in `~/.claude/CLAUDE.md`; SessionStart drift notice | Setup-managed `afk:behaviors` block in `~/.codex/AGENTS.md`; SessionStart drift notice | Unavailable until opt-in |\n",
        encoding="utf-8",
    )
    tests = tmp_path / "scripts" / "tests"
    tests.mkdir(parents=True)
    (tests / "test_install_block.py").write_text(
        "def test_install_migration_covers_h7_h8_h10_and_removes_duplicate_unified_blocks(): pass\n"
        "def test_install_reuses_legacy_marker_as_consent(): pass\n"
        "def test_teardown_removes_every_named_block_and_preserves_outside_bytes(): pass\n",
        encoding="utf-8",
    )
    (tmp_path / "providers").mkdir()

    behavior_registry.validate_registry(registry_path, tmp_path, parity_root=tmp_path)

    (tmp_path / "providers" / "BEHAVIORS.md").write_text("copy", encoding="utf-8")
    with pytest.raises(behavior_registry.RegistryError, match="provider registry copy"):
        behavior_registry.validate_registry(registry_path, tmp_path, parity_root=tmp_path)

    (tmp_path / "providers" / "BEHAVIORS.md").unlink()
    providers = tmp_path / "PROVIDERS.md"
    providers.write_text(
        providers.read_text(encoding="utf-8").replace(
            "`afk:behaviors` sentinel in user steering |\n",
            "wrong |\n",
            1,
        ),
        encoding="utf-8",
    )
    with pytest.raises(behavior_registry.RegistryError, match="PROVIDERS.md.*Claude Code"):
        behavior_registry.validate_registry(registry_path, tmp_path, parity_root=tmp_path)


def test_parity_rejects_wrong_capability_value_and_missing_named_test(tmp_path):
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Apply it.
""",
    )
    (tmp_path / "skills" / "afk" / "setup").mkdir(parents=True)
    (tmp_path / "skills" / "afk" / "setup" / "MANIFEST.md").write_text(
        "afk:behaviors plain-language lavish-sessions investigation",
        encoding="utf-8",
    )
    (tmp_path / "PROVIDERS.md").write_text(
        "| Concern | Claude Code | Codex CLI |\n|---|---|---|\n"
        "| Managed behavior | `afk:behaviors` sentinel in user steering | `afk:behaviors` sentinel in user steering |\n",
        encoding="utf-8",
    )
    (tmp_path / "CAPABILITIES.md").write_text(
        "| Capability | Claude Code | Codex CLI | Required degradation |\n|---|---|---|---|\n"
        "| `managed_behavior` | wrong | Setup-managed `afk:behaviors` block in `~/.codex/AGENTS.md`; SessionStart drift notice | Unavailable |\n",
        encoding="utf-8",
    )
    tests = tmp_path / "scripts" / "tests"
    tests.mkdir(parents=True)
    (tests / "test_install_block.py").write_text("def test_something_else(): pass\n", encoding="utf-8")

    with pytest.raises(behavior_registry.RegistryError, match="CAPABILITIES.md.*Claude Code"):
        behavior_registry.validate_registry(registry_path, tmp_path, parity_root=tmp_path)

    (tmp_path / "CAPABILITIES.md").write_text(
        "| Capability | Claude Code | Codex CLI | Required degradation |\n|---|---|---|---|\n"
        "| `managed_behavior` | Setup-managed `afk:behaviors` block in `~/.claude/CLAUDE.md`; SessionStart drift notice | Setup-managed `afk:behaviors` block in `~/.codex/AGENTS.md`; SessionStart drift notice | Unavailable |\n",
        encoding="utf-8",
    )
    with pytest.raises(behavior_registry.RegistryError, match="missing executable install test"):
        behavior_registry.validate_registry(registry_path, tmp_path, parity_root=tmp_path)


def test_cli_accepts_registry_option_and_rejects_positional_conflict(tmp_path, capsys):
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Apply it.
""",
    )

    assert behavior_registry.main(
        ["validate", "--registry", str(registry_path), "--plugin-root", str(tmp_path)]
    ) == 0
    assert capsys.readouterr().out == ""
    assert behavior_registry.main(
        ["validate", "--registry", str(registry_path), "--plugin-root", str(tmp_path), "--verbose"]
    ) == 0
    assert "valid: 1 rows" in capsys.readouterr().out

    with pytest.raises(SystemExit) as error:
        behavior_registry.main(
            [
                "validate",
                str(registry_path),
                "--registry",
                str(registry_path),
                "--plugin-root",
                str(tmp_path),
            ]
        )
    assert error.value.code == 2


def test_cli_audit_ignore_unmanaged_keeps_transport_checks(tmp_path, capsys):
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Apply the rule.
""",
    )
    target = tmp_path / "instructions.md"
    target.write_text(
        behavior_registry.render_registry(registry_path, tmp_path) + "\nApply the rule.\n",
        encoding="utf-8",
    )

    assert behavior_registry.main(
        [
            "audit",
            "--registry",
            str(registry_path),
            "--plugin-root",
            str(tmp_path),
            "--target",
            str(target),
            "--ignore-unmanaged",
        ]
    ) == 0
    assert "valid: 1 installed target" in capsys.readouterr().out

    target.write_text("human only\n", encoding="utf-8")
    assert behavior_registry.main(
        [
            "audit",
            "--registry",
            str(registry_path),
            "--plugin-root",
            str(tmp_path),
            "--target",
            str(target),
        ]
    ) == 0
    assert "opt-in available; no managed block installed" in capsys.readouterr().out


def test_cli_audit_target_root_checks_each_target_against_its_own_root(tmp_path, capsys):
    """A2-004/A2-002: --target-root TARGET ROOT ENABLEMENT takes three
    separate arguments — never a colon-joined string, which breaks on a
    Windows drive-letter path."""
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Apply the rule.
""",
    )
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    root_a.mkdir()
    root_b.mkdir()
    target_a = tmp_path / "a.md"
    target_a.write_text(behavior_registry.render_registry(registry_path, root_a), encoding="utf-8")
    target_b = tmp_path / "b.md"
    target_b.write_text(behavior_registry.render_registry(registry_path, root_b), encoding="utf-8")

    assert behavior_registry.main(
        [
            "audit",
            "--registry",
            str(registry_path),
            "--plugin-root",
            str(tmp_path),
            "--target-root",
            str(target_a),
            str(root_a),
            "enabled",
            "--target-root",
            str(target_b),
            str(root_b),
            "enabled",
        ]
    ) == 0
    assert "valid: 2 installed target" in capsys.readouterr().out

    with pytest.raises(SystemExit) as error:
        behavior_registry.main(["audit", "--registry", str(registry_path), "--plugin-root", str(tmp_path)])
    assert error.value.code == 2


def test_cli_audit_target_root_accepts_an_empty_root_for_an_unresolved_target(tmp_path, capsys):
    """A3-003: --target-root TARGET "" ENABLEMENT (empty root) is the CLI
    spelling of an unresolved root — the target is still audited for a
    leftover marker, never silently skipped."""
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Apply the rule.
""",
    )
    orphaned = tmp_path / "orphaned.md"
    orphaned.write_text(
        "<!-- afk:behaviors:start -->\nstale content\n<!-- afk:behaviors:end -->\n",
        encoding="utf-8",
    )

    exit_code = behavior_registry.main(
        [
            "audit",
            "--registry",
            str(registry_path),
            "--plugin-root",
            str(tmp_path),
            "--target-root",
            str(orphaned),
            "",
            "enabled",
        ]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "could not be verified" in err


def test_cli_audit_target_root_survives_a_space_in_either_path(tmp_path, capsys):
    """A2-002: target/root/enablement are argv elements, never joined into one
    string, so a space in either path must never be mis-split."""
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Apply the rule.
""",
    )
    root_with_space = tmp_path / "plugin root"
    root_with_space.mkdir()
    target_with_space = tmp_path / "user config" / "CLAUDE.md"
    target_with_space.parent.mkdir()
    target_with_space.write_text(
        behavior_registry.render_registry(registry_path, root_with_space), encoding="utf-8"
    )

    assert behavior_registry.main(
        [
            "audit",
            "--registry",
            str(registry_path),
            "--plugin-root",
            str(tmp_path),
            "--target-root",
            str(target_with_space),
            str(root_with_space),
            "enabled",
        ]
    ) == 0
    assert "valid: 1 installed target" in capsys.readouterr().out


def test_cli_audit_target_root_rejects_a_marker_for_a_disabled_provider_even_when_root_resolves(
    tmp_path, capsys
):
    """A4-001: --target-root TARGET ROOT disabled must reject a leftover
    marker even though the root independently resolves — 1 enabled provider
    with a clean install must not hide the finding for the other, disabled
    one. Both providers get a valid root in this test."""
    behavior_registry = load_module()
    registry_path = write_registry(
        tmp_path,
        """## rule
state: active | scope: all-repos | revision: 1 | doctrine: LANGUAGE.md §1
Apply the rule.
""",
    )
    root_enabled = tmp_path / "root-enabled"
    root_disabled = tmp_path / "root-disabled"
    root_enabled.mkdir()
    root_disabled.mkdir()
    target_enabled = tmp_path / "enabled.md"
    target_enabled.write_text(
        behavior_registry.render_registry(registry_path, root_enabled), encoding="utf-8"
    )
    target_disabled = tmp_path / "disabled.md"
    target_disabled.write_text(
        behavior_registry.render_registry(registry_path, root_disabled), encoding="utf-8"
    )

    exit_code = behavior_registry.main(
        [
            "audit",
            "--registry",
            str(registry_path),
            "--plugin-root",
            str(tmp_path),
            "--target-root",
            str(target_enabled),
            str(root_enabled),
            "enabled",
            "--target-root",
            str(target_disabled),
            str(root_disabled),
            "disabled",
        ]
    )
    assert exit_code == 1
    err = capsys.readouterr().err
    assert "its provider is not enabled" in err
    assert str(target_disabled) in err
    assert str(target_enabled) not in err

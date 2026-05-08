import re

from afk_driver.scope_enforcer import (
    Violation,
    enforce,
    extract_changed_paths,
    module_of,
)


MARKER = re.compile(r"P2P-\d+")

FORBIDDEN = (
    "**/UpgradeGroup*.java",
    "**/PreDbMigration*",
    "**/db/changelog/**",
    "**/changeset*.xml",
)

SCOPE_DRIVER = ("tools/payable/afk/**",)
SCOPE_PAYABLE = ("11700-payable/**",)
SCOPE_PAYABLE_AND_COMMON = ("11700-payable/**", "11999-common/**")


def _diff(path: str, added_lines: list[str]) -> str:
    body = "\n".join(f"+{ln}" for ln in added_lines)
    return (
        f"diff --git a/{path} b/{path}\n"
        f"index 1234567..abcdef0 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(added_lines)} @@\n"
        f"{body}\n"
    )


def test_in_scope_clean():
    diff = _diff("tools/payable/afk/src/afk_driver/foo.py", ["x = 1"])
    assert enforce(diff, SCOPE_DRIVER, FORBIDDEN, home_module=None, marker_pattern=MARKER) == []


def test_out_of_scope_violation():
    diff = _diff("other/thing.py", ["x = 1"])
    vs = enforce(diff, SCOPE_DRIVER, FORBIDDEN, home_module=None, marker_pattern=MARKER)
    assert len(vs) == 1
    assert vs[0].reason == "out-of-scope"
    assert vs[0].path == "other/thing.py"


def test_forbidden_upgrade_group():
    diff = _diff(
        "11700-payable/payable/src/main/java/com/foo/upgrades/UpgradeGroup_42_1.java",
        ["// hand-written migration"],
    )
    vs = enforce(diff, SCOPE_PAYABLE, FORBIDDEN, home_module="11700-payable", marker_pattern=MARKER)
    assert len(vs) == 1
    assert vs[0].reason == "forbidden-pattern"
    assert "UpgradeGroup" in vs[0].detail


def test_forbidden_pre_db_migration():
    diff = _diff(
        "11700-payable/payable/src/main/java/com/foo/migrations/PreDbMigrationFoo.java",
        ["// pre-DB migration"],
    )
    vs = enforce(diff, SCOPE_PAYABLE, FORBIDDEN, home_module="11700-payable", marker_pattern=MARKER)
    assert len(vs) == 1
    assert vs[0].reason == "forbidden-pattern"


def test_forbidden_liquibase_changelog():
    diff = _diff(
        "11700-payable/payable/src/main/resources/db/changelog/db.changelog-master.xml",
        ["  <changeSet/>"],
    )
    vs = enforce(diff, SCOPE_PAYABLE, FORBIDDEN, home_module="11700-payable", marker_pattern=MARKER)
    assert len(vs) == 1
    assert vs[0].reason == "forbidden-pattern"


def test_jpa_entity_in_scope_allowed():
    diff = _diff(
        "11700-payable/payable/src/main/java/com/foo/entities/Invoice.java",
        ["@Entity", "private String newField;"],
    )
    vs = enforce(diff, SCOPE_PAYABLE, FORBIDDEN, home_module="11700-payable", marker_pattern=MARKER)
    assert vs == []


def test_cross_module_with_marker_clean():
    diff = _diff(
        "11999-common/common-lib/src/main/java/com/foo/Util.java",
        ["// P2P-1221: shared helper bump", "private static final int X = 2;"],
    )
    vs = enforce(
        diff,
        SCOPE_PAYABLE_AND_COMMON,
        FORBIDDEN,
        home_module="11700-payable",
        marker_pattern=MARKER,
    )
    assert vs == []


def test_cross_module_no_marker_violation():
    diff = _diff(
        "11999-common/common-lib/src/main/java/com/foo/Util.java",
        ["private static final int X = 2;"],
    )
    vs = enforce(
        diff,
        SCOPE_PAYABLE_AND_COMMON,
        FORBIDDEN,
        home_module="11700-payable",
        marker_pattern=MARKER,
    )
    assert len(vs) == 1
    assert vs[0].reason == "cross-module-no-marker"
    assert vs[0].path.startswith("11999-common/")


def test_extract_changed_paths_dedup_and_order():
    diff = _diff("a.py", ["x"]) + _diff("b.py", ["y"]) + _diff("a.py", ["z"])
    assert extract_changed_paths(diff) == ["a.py", "b.py"]


def test_module_of_recognizes_5digit_prefix():
    assert module_of("11700-payable/foo.java") == "11700-payable"
    assert module_of("tasks/foo.py") is None
    assert module_of("99999-x-y-z/foo") == "99999-x-y-z"
    assert module_of("123-too-short/foo") is None

import ast
import re

import setup


def _install(places, version="2.0.0"):
    root = places.codex_dir / "plugins" / "cache" / "market" / "afkv2" / version
    for relative in ("engine/engine.py", "skills/use-lavish/scripts/page_round.py", "skills/grill/SKILL.md"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
    other = places.codex_dir / "plugins" / "cache" / "market" / "other" / "1.0.0" / "skills" / "x" / "scripts"
    other.mkdir(parents=True)
    (other / "other.py").write_bytes(b"")
    return root


def _patterns(places):
    found = []
    for line in places.codex_rules.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        match = re.fullmatch(r'prefix_rule\(pattern=(\[.*\]), decision="allow"\)', line)
        assert match, line
        found.append(ast.literal_eval(match.group(1)))
    return found


def test_rules_allow_only_the_plugin_scripts_for_each_launcher(places):
    root = _install(places)
    answer = setup.write_codex_rules(places)
    assert answer["ok"] and answer["action"] == "written" and answer["scripts"] == 2
    engine, page = str(root / "engine" / "engine.py"), str(root / "skills" / "use-lavish" / "scripts" / "page_round.py")
    assert _patterns(places) == [["python", engine], ["py", "-3", engine], ["python", page], ["py", "-3", page]]


def test_no_codex_install_writes_nothing(places):
    assert setup.write_codex_rules(places) == {"ok": True, "action": "not-installed"}
    assert not places.codex_rules.exists()


def test_a_second_run_changes_nothing(places):
    _install(places)
    setup.write_codex_rules(places)
    assert setup.write_codex_rules(places)["action"] == "unchanged"


def test_a_new_plugin_version_is_covered_on_the_next_run(places):
    _install(places, "2.0.0")
    setup.write_codex_rules(places)
    engine_folder = places.codex_dir / "plugins" / "cache" / "market" / "afkv2" / "2.0.1" / "engine"
    engine_folder.mkdir(parents=True)
    (engine_folder / "engine.py").write_bytes(b"")
    assert setup.write_codex_rules(places)["action"] == "written"
    assert any("2.0.1" in pattern[-1] for pattern in _patterns(places))


def test_remove_deletes_only_our_file(places):
    _install(places)
    setup.write_codex_rules(places)
    other = places.codex_rules.with_name("default.rules")
    other.write_text("kept\n", encoding="utf-8")
    assert setup.remove_codex_rules(places) == "removed"
    assert not places.codex_rules.exists() and other.exists()
    assert setup.remove_codex_rules(places) == "absent"

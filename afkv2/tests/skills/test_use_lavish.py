"""The use-lavish skill: the one home of the round commands, the round builder and the shared page helpers."""

import ast
import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
HOME = SKILLS / "use-lavish"
MOVED = ("page_round.py", "round_document.py", "grill_common.py", "page_links.py")
ROUND_COMMANDS = {"page_round.py": ("present", "wait", "reply", "ingest", "end"),
                  "round_document.py": ("build", "apply-readings")}
PAGE_SKILLS = ("grill", "propose-solution", "to-subtasks")


def _imports(path):
    names = set()
    for node in ast.walk(ast.parse(path.read_text("utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_the_moved_scripts_live_only_in_the_use_lavish_home():
    for name in MOVED:
        assert (HOME / "scripts" / name).is_file(), name
        assert not (SKILLS / "grill" / "scripts" / name).exists(), name


def test_the_new_home_holds_the_produced_symbols():
    assert "def present(doc" in (HOME / "scripts" / "page_round.py").read_text("utf-8")
    builder = (HOME / "scripts" / "round_document.py").read_text("utf-8")
    assert "def build_round_document(" in builder
    assert "def apply_readings(doc_path" in builder


def test_the_skill_file_has_frontmatter_and_names_its_commands():
    text = (HOME / "SKILL.md").read_text("utf-8")
    head = re.match(r"---\n(.*?)\n---\n", text, re.S).group(1)
    assert re.search(r"^name: use-lavish$", head, re.M)
    assert re.search(r"^description: .+", head, re.M)
    for script, verbs in ROUND_COMMANDS.items():
        for verb in verbs:
            assert f"scripts/{script} {verb}" in text, (script, verb)


def test_every_importer_finds_the_helpers_in_the_use_lavish_home():
    modules = {Path(name).stem for name in MOVED}
    importers = [path for path in SKILLS.glob("*/scripts/*.py") if _imports(path) & modules]
    assert importers
    for path in importers:
        if path.parent != HOME / "scripts":
            assert '"use-lavish"' in path.read_text("utf-8"), path


def test_the_page_skills_run_every_round_command_from_the_use_lavish_home():
    for skill in PAGE_SKILLS:
        for name in ("SKILL.md", "CODEX-LIVE-CHECK.md"):
            text = (SKILLS / skill / name).read_text("utf-8")
            for script in ROUND_COMMANDS:
                for line in [line for line in text.splitlines() if script in line]:
                    assert f"use-lavish/scripts/{script}" in line, (skill, name, line)
                    assert "grill/scripts" not in line, (skill, name, line)

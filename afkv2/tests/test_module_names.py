"""Every afkv2 script module name is unique (SDD section 7): flat modules with one name shadow each other in one process."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
FIXED_NAMES = {"__init__.py", "conftest.py"}  # Python and pytest fix these names
SKIPPED_FOLDERS = {"__pycache__", ".pytest_cache"}


def duplicate_names(root):
    places = defaultdict(list)
    for path in root.rglob("*.py"):
        relative = path.relative_to(root)
        if path.name not in FIXED_NAMES and not SKIPPED_FOLDERS.intersection(relative.parts):
            places[path.name].append(relative.as_posix())
    return {name: sorted(found) for name, found in places.items() if len(found) > 1}


def test_no_two_modules_of_the_plugin_tree_share_a_name():
    assert duplicate_names(PLUGIN) == {}


def test_the_2_prototype_skill_folders_register_their_3_modules_once_each():
    """VR-028 (SDD §14 row "plugin registration"): each folder holds a SKILL.md named as the folder, and each named
    module lives once in the plugin tree, in its own skill folder."""
    for folder in ("prototype", "design-system"):
        head = (PLUGIN / "skills" / folder / "SKILL.md").read_text("utf-8").split("\n")[:3]
        assert head[0] == "---" and head[1] == f"name: {folder}"
    found = {name: sorted(path.relative_to(PLUGIN).as_posix() for path in PLUGIN.rglob(f"{name}.py")
                          if "__pycache__" not in path.parts)
             for name in ("prototype_files", "mockup_show", "catalog_files")}
    assert found == {"prototype_files": ["skills/prototype/scripts/prototype_files.py"],
                     "mockup_show": ["skills/prototype/scripts/mockup_show.py"],
                     "catalog_files": ["skills/design-system/scripts/catalog_files.py"]}


def test_the_check_finds_a_duplicate_and_exempts_the_fixed_names(tmp_path):
    for relative in ("a/one.py", "b/one.py", "a/two.py", "a/__init__.py", "b/__init__.py", "a/conftest.py", "b/conftest.py",
                     "a/__pycache__/three.py", "b/__pycache__/three.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    assert duplicate_names(tmp_path) == {"one.py": ["a/one.py", "b/one.py"]}

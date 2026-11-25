"""The disk side of design-system, from the repository root (SDD §3, §8 row "skills/design-system").

`catalog_files.py start [--frontend NAME]`: the frontend of the config, its catalog folder, the cards of its README
  and the live block. Refuses `no-frontend`, `pick-frontend`.
`catalog_files.py add-frontend --name N --source S --catalog C`: the only writer of the config `frontends` list
  (ADR-0002 design). Refuses `bad-value` for a duplicate name or catalog, a path outside the repository or a missing
  source folder; the config stays as it is on each refusal.
`catalog_files.py check [--frontend NAME]`: checks the catalog folder against CATALOG-FORMAT.md, then counts the
  checked and unchecked cards.

Each answer is one JSON object; exit 0 ok, 1 refused, 2 unreadable input.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path, PurePath, PurePosixPath

SKILL = Path(__file__).resolve().parents[1]
PLUGIN = SKILL.parents[1]
sys.path.insert(0, str(SKILL.parent / "prototype" / "scripts"))
sys.path.insert(0, str(SKILL.parent / "use-lavish" / "scripts"))
sys.path.insert(0, str(PLUGIN / "scripts"))

import afkv2_config  # noqa: E402
import prototype_files  # noqa: E402
from grill_common import Parser, Refusal, serve  # noqa: E402

README = prototype_files.CATALOG_MARK
# Lockstep with CATALOG-FORMAT.md, which owns the format (decision D-8).
COLUMNS = ("File", "Kind", "State", "Screenshot")
SECTIONS = ("Scope", "Cards", "Refresh")
KINDS = ("token", "component", "shell", "page")
STATES = ("checked", "unchecked")
NO_SCREENSHOT = ("", "-", "—", "none")
TOKENS = "tokens.css"


def _relative(value):
    """A config path as POSIX text: `./a/b/` is `a/b`. An absolute path stays as given, so the config check refuses
    it."""
    if PurePath(value).anchor:
        return value
    return PurePosixPath(PurePath(value).as_posix()).as_posix()


def _inside(root, value, field):
    """Refuse `bad-value` for a path that is empty or resolves outside the repository root."""
    if value in ("", "."):
        raise Refusal("bad-value", f"--{field}: a folder inside the repository is required, not the repository root")
    resolved = (root / value).resolve()
    if resolved != root and root not in resolved.parents:
        raise Refusal("bad-value", f"--{field}: {value!r} must stay inside the repository root")


def _write(config_file, frontends):
    """Replace the `frontends` list and keep every other key; the file changes in one rename."""
    temporary = config_file.with_suffix(".tmp")
    try:
        raw = json.loads(config_file.read_text(encoding="utf-8"))
        raw["frontends"] = frontends
        temporary.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        os.replace(temporary, config_file)
    except (OSError, ValueError) as error:
        temporary.unlink(missing_ok=True)
        raise Refusal("config-write-failed", f"{config_file}: {error}") from None


def cmd_add_frontend(argv):
    parser = Parser(add_help=False)
    parser.add_argument("--name", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args(argv)
    config = prototype_files._config()
    root = Path(config["repo_root"]).resolve()
    entry = {"name": args.name, "source": _relative(args.source), "catalog": _relative(args.catalog)}
    frontends = [*config["frontends"], entry]
    try:
        afkv2_config._check_frontends(frontends)
    except afkv2_config.Refusal as refusal:
        raise Refusal(refusal.code, refusal.reason) from None
    for field in ("source", "catalog"):
        _inside(root, entry[field], field)
    if not (root / entry["source"]).is_dir():
        raise Refusal("bad-value", f"--source: no folder {entry['source']!r} in the repository")
    _write(Path(config["config_file"]), frontends)
    return {"ok": True, "entry": entry, "config_file": Path(config["config_file"]).as_posix()}


def _cell(row, column):
    return row.get(column, "").strip("` ")


def cards_of(readme):
    """The rows of the README Cards table as {file, kind, state, screenshot}, in order."""
    body = dict(prototype_files._sections(readme.replace("\r\n", "\n"))).get("Cards", "")
    return [{column.lower(): _cell(row, column) for column in COLUMNS} for row in prototype_files._table(body)]


def _catalog(argv):
    """(config, frontend entry, catalog folder) of the run."""
    parser = Parser(add_help=False)
    parser.add_argument("--frontend")
    args = parser.parse_args(argv)
    config = prototype_files._config()
    frontend = prototype_files._frontend(config["frontends"], args.frontend)
    return config, frontend, (Path(config["repo_root"]) / frontend["catalog"]).resolve()


def cmd_start(argv):
    config, frontend, catalog_dir = _catalog(argv)
    readme = catalog_dir / README
    exists = readme.is_file()
    return {"ok": True, "frontend": frontend, "catalog_dir": catalog_dir.as_posix(), "catalog_exists": exists,
            "cards": cards_of(prototype_files._read(readme)) if exists else [], "live": config.get("live")}


def _card_problems(card, catalog_dir):
    name, problems = card["file"], []
    parts = PurePosixPath(name).parts
    if not parts or PurePath(name).anchor or ".." in parts or name == README:
        problems.append(f"card {name or '(empty)'}: not a file in the catalog folder")
    elif not (catalog_dir / name).is_file():
        problems.append(f"card {name}: no such file in the catalog folder")
    if card["kind"] not in KINDS:
        problems.append(f"card {name}: kind `{card['kind']}` is not one of {', '.join(KINDS)}")
    if card["state"] not in STATES:
        problems.append(f"card {name}: state `{card['state']}` is not one of {', '.join(STATES)}")
    if card["state"] == "checked" and card["screenshot"].lower() in NO_SCREENSHOT:
        problems.append(f"card {name}: checked, but it names no screenshot it was checked against")
    return problems


def catalog_problems(catalog_dir):
    """Each way the catalog folder breaks CATALOG-FORMAT.md; empty when it holds."""
    problems = [] if (catalog_dir / TOKENS).is_file() else [f"no {TOKENS} in the catalog folder"]
    readme = catalog_dir / README
    if not readme.is_file():
        return [f"no {README} in the catalog folder", *problems]
    sections = dict(prototype_files._sections(prototype_files._read(readme).replace("\r\n", "\n")))
    problems += [f"no section `## {section}` in {README}" for section in SECTIONS if section not in sections]
    cards = cards_of(prototype_files._read(readme))
    if "Cards" in sections and not cards:
        problems.append("the Cards table has no row")
    seen = set()
    for card in cards:
        if card["file"] in seen:
            problems.append(f"card {card['file']}: 2 rows in the Cards table")
        seen.add(card["file"])
        problems += _card_problems(card, catalog_dir)
    return problems


def cmd_check(argv):
    _, _, catalog_dir = _catalog(argv)
    problems = catalog_problems(catalog_dir)
    if problems:
        raise Refusal("bad-catalog", "; ".join(problems), problems=problems)
    cards = cards_of(prototype_files._read(catalog_dir / README))
    checked = sum(card["state"] == "checked" for card in cards)
    return {"ok": True, "cards": len(cards), "checked": checked, "unchecked": len(cards) - checked}


VERBS = {"start": cmd_start, "add-frontend": cmd_add_frontend, "check": cmd_check}


def main(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", 2)
    return VERBS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(serve(main))

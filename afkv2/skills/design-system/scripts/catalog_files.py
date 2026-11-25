"""The disk side of design-system, from the repository root (SDD §3, §8 row "skills/design-system").

`catalog_files.py add-frontend --name N --source S --catalog C`: the only writer of the config `frontends` list
  (ADR-0002 design). Refuses `bad-value` for a duplicate name or catalog, a path outside the repository or a missing
  source folder; the config stays as it is on each refusal.

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


VERBS = {"add-frontend": cmd_add_frontend}


def main(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", 2)
    return VERBS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(serve(main))

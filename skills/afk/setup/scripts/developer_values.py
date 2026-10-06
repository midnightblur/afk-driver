#!/usr/bin/env python3
"""Report and record a developer's `developer:` values. None is a secret, so an agent
asks the human in session and records the answers here.

    python developer_values.py checkouts [FOLDER ...]   # configured main checkouts, below
    python developer_values.py status [--repo PATH]     # JSON report, below
    python developer_values.py set KEY=VALUE ... [--machine] [--repo PATH]

`checkouts` lists the main checkouts holding `.afk/config.yaml` up to three levels
below each FOLDER (default: the folder holding this repository's main checkout),
with each one's `missing` and `inherited` keys; this repository's entry has `current`. `--repo` points `status` and `set`
at one of them instead of the current checkout.

`status` names, per key: `need` (required | optional | n/a for this repository's
adapters), the resolved `value`, its `source` layer, and a `suggestion` to offer.
`missing` lists the required keys nothing resolves; `inherited` the keys naming a
person or a location that only the machine file supplies. A `worktreeBasePath` set in a file also shows its `derived` value.

`set` writes the repository file `<git common dir>/afk/config.yaml`, which the main
checkout and every worktree read; `--machine` writes `~/.afk/config.yaml`, the
default for every repository. It changes only the keys named; `KEY=` removes one.
`worktreeBasePath` is one repository's location, so `--machine` only removes it.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[4]


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ac = _module("afk_config_for_developer_values", PLUGIN_ROOT / "scripts" / "afk-config.py")
ORDER = ("trackerAssignee", "mrReviewer", "mrAssignee", "worktreeBasePath", "ideBinary")


def machine_file() -> Path:
    return Path.home() / ".afk" / "config.yaml"


def read_block(p: Path) -> dict:
    """The `developer:` mapping of one file, read by the one parser; {} when absent."""
    if not p.is_file():
        return {}
    block = ac.parse(p.read_text(encoding="utf-8"), str(p)).get("developer") or {}
    return {k: str(v) for k, v in block.items() if v is not None and str(v).strip()}


def write_block(p: Path, values: dict) -> None:
    """Replace the `developer:` block, leaving every other line of the file untouched."""
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = p.read_text(encoding="utf-8").splitlines() if p.is_file() else []
    kept, skipping = [], False
    for line in lines:
        if not line[:1].isspace() and line.strip():
            skipping = line.strip() == "developer:"
            if skipping:
                continue
        elif skipping:
            continue
        kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()

    block = ["developer:"] if values else []
    for key in sorted(values, key=lambda k: ORDER.index(k) if k in ORDER else len(ORDER)):
        text = str(values[key])
        # Quote anything the reader would not return as this exact string.
        plain = not (any(c in text for c in ":#\"'") or text.strip() != text
                     or text.lower() in ("true", "false", "null", "~")
                     or re.fullmatch(r"[+-]?\d*\.?\d+", text))
        quoted = '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')
        block.append("  %s: %s" % (key, text if plain else quoted))

    body = "\n".join(kept + ([""] if kept and block else []) + block)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(body + "\n" if body else "", encoding="utf-8")
    tmp.replace(p)


def forge_user(kind: str) -> str | None:
    """The username the forge CLI is logged in as, or None when it cannot say."""
    cli, args = {"gitlab": ("glab", ["api", "user"]),
                 "github": ("gh", ["api", "user", "--jq", ".login"])}.get(kind, (None, None))
    if not cli or not shutil.which(cli):
        return None
    try:
        out = subprocess.run([cli, *args], capture_output=True, text=True, timeout=30,
                             stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    text = out.stdout.strip()
    if kind == "gitlab":
        try:
            text = str(json.loads(text).get("username") or "")
        except (ValueError, AttributeError):
            return None
    return text or None


def jira_email() -> str | None:
    """The account email the Jira credential chain holds; an assignee may be an email."""
    try:
        api = _module("afk_jira_api_for_developer_values",
                      PLUGIN_ROOT / "adapters" / "tracker" / "jira" / "api.py")
        return api.resolve_creds_env().get("JIRA_EMAIL") or None
    except Exception:
        return None


def ide_guess() -> str | None:
    if os.name != "nt":
        return None
    for pf in filter(None, (os.environ.get("ProgramFiles"), os.environ.get("ProgramW6432"))):
        found = sorted(Path(pf).glob("JetBrains/*/bin/idea64.exe"), reverse=True)
        if found:
            return found[0].as_posix()
    return None


def status(root: Path, suggest_values: bool = True) -> dict:
    config = ac.load(root)
    tracker = str(ac.get(config, "tracker") or "none")
    forge = str(ac.get(config, "forge") or "none")
    shared = ac.shared_overlay(root)
    named = os.environ.get("AFK_CONFIG")
    files = [("explicit", Path(named) if named else None),
             ("checkout", root / ".afk" / "config.local.yaml"),
             ("repository", shared), ("machine", machine_file())]
    need = {
        "trackerAssignee": "required" if tracker != "none" else "n/a",
        "mrReviewer": "required" if forge != "none" else "n/a",
        "mrAssignee": "optional" if forge != "none" else "n/a",
        "worktreeBasePath": "required",
        "ideBinary": "optional",
    }
    suggest = {
        "trackerAssignee": lambda: (jira_email() if tracker == "jira"
                                    else forge_user("github") if tracker == "github-issues" else None),
        "mrReviewer": lambda: None,          # nobody else may pick who reviews this developer's work
        "mrAssignee": lambda: forge_user(forge),
        "worktreeBasePath": lambda: None,
        "ideBinary": ide_guess,
    }
    keys = {}
    for key in ORDER:
        value = ac.developer_value(config, key, root)
        source = next((label for label, p in files if p is not None and key in read_block(p)), None)
        if value is not None and source is None:
            source = "derived"
        entry = {"need": need[key], "value": value, "source": source}
        if suggest_values and value is None and need[key] != "n/a":
            entry["suggestion"] = suggest[key]()
        if key == "worktreeBasePath" and source not in (None, "derived"):
            derived = ac.worktree_base(root)
            entry["derived"] = str(derived).replace("\\", "/") if derived else None
        keys[key] = entry
    return {
        "tracker": tracker, "forge": forge,
        "repository_file": str(shared) if shared else None,
        "machine_file": str(machine_file()),
        "missing": [k for k, e in keys.items() if e["need"] == "required" and e["value"] is None],
        # A machine default may name another repository's person or folder.
        "inherited": [k for k, e in keys.items()
                      if e["need"] != "n/a" and e["source"] == "machine" and k != "ideBinary"],
        "keys": keys,
    }


def main_checkout(root: Path) -> Path | None:
    shared = ac.shared_overlay(root)
    common = shared.parent.parent if shared else None
    return common.parent if common is not None and common.name == ".git" else None


def checkouts(folders: list[Path], current: Path | None = None,
              depth: int = 3, budget: int = 5000) -> dict:
    """Configured main checkouts below `folders`; a worktree is covered by its main checkout."""
    folders = [f.resolve() for f in folders]
    for folder in folders:
        if folder == Path(folder.anchor) or not folder.is_dir():
            raise ValueError(f"name a project folder, not a drive root or a missing path: {folder}")
    found, queue, seen, truncated = [], [(f, 0) for f in folders], 0, False
    while queue:
        folder, level = queue.pop(0)
        if (folder / ".git").is_dir():
            if (folder / ".afk" / "config.yaml").is_file():
                found.append(folder)
            continue
        if level >= depth:
            continue
        try:
            children = sorted(e.path for e in os.scandir(folder) if e.is_dir(follow_symlinks=False)
                              and not e.name.startswith(".") and e.name != "node_modules")
        except OSError:
            continue
        seen += len(children)
        if seen > budget:
            truncated = True
            break
        queue.extend((Path(c), level + 1) for c in children)
    listed = []
    for root in sorted(set(found)):
        entry = {"path": root.as_posix()}
        if current is not None and root == current.resolve():
            entry["current"] = True
        try:
            report = status(root, suggest_values=False)
            entry.update(missing=report["missing"], inherited=report["inherited"])
        except ac.ConfigError as problem:
            entry["error"] = str(problem)
        listed.append(entry)
    return {"folders": [f.as_posix() for f in folders], "truncated": truncated,
            "checkouts": listed}


def record(root: Path, pairs: list[str], machine: bool) -> Path:
    """Write the named keys to one file; raises ValueError naming a bad request."""
    target = machine_file() if machine else ac.shared_overlay(root)
    if target is None:
        raise ValueError("this repository has no git directory to share a file from; use --machine")
    updates = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or key not in ORDER:
            raise ValueError(f"expected KEY=VALUE with KEY one of {', '.join(ORDER)}: {pair!r}")
        if machine and key == "worktreeBasePath" and value.strip():
            raise ValueError("worktreeBasePath is one repository's location; record it without --machine")
        updates[key] = value.strip().replace("\\", "/") if key in ("worktreeBasePath", "ideBinary") else value.strip()
    values = read_block(target)
    for key, value in updates.items():
        if value:
            values[key] = value
        else:
            values.pop(key, None)
    write_block(target, values)
    return target


def main(argv: list[str]) -> int:
    repo = None
    if "--repo" in argv:
        at = argv.index("--repo")
        repo, argv = argv[at + 1:at + 2], argv[:at] + argv[at + 2:]
        if not repo:
            sys.stderr.write("developer_values: --repo needs a path\n")
            return 2
    root = ac.git_root(Path(repo[0])) if repo else ac.git_root()
    try:
        if argv[:1] == ["checkouts"]:
            here = main_checkout(root) if root else None
            folders = [Path(a) for a in argv[1:]] or ([here.parent] if here else [])
            if not folders:
                raise ValueError("outside a git checkout; name the folders to search")
            sys.stdout.write(json.dumps(checkouts(folders, here), indent=2) + "\n")
            return 0
        if root is None:
            raise ValueError("run inside a git checkout, or name one with --repo")
        if argv[:1] == ["status"]:
            sys.stdout.write(json.dumps(status(root), indent=2) + "\n")
            return 0
        if argv[:1] == ["set"] and len(argv) > 1:
            machine = "--machine" in argv
            target = record(root, [a for a in argv[1:] if a != "--machine"], machine)
            sys.stdout.write(f"developer_values: wrote {target}\n")
            return 0
    except (ValueError, ac.ConfigError) as problem:
        sys.stderr.write(f"developer_values: {problem}\n")
        return 2
    sys.stderr.write(__doc__ or "")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

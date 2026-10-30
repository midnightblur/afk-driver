"""afkv2 setup: install, prove the hook, take over from v1, switch back.

Usage: setup.py <verb> [options]   (each verb answers one JSON object)

  status                                   read-only report
  prepare                                  Python 3, rg on every shell, install record
  secrets                                  the developer's own terminal only: Jira values
  copy-config [--spec-folder PATH] [--no-v1-values]
                                           write .afkv2/config.json once, with its spec_folder
  ownership (--own GLOB... --shared GLOB... | --skip)
  takeover --provider claude|codex --end-marker LINE
  switch-back

Exit codes: 0 ok, 1 refused or failed, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jira_values  # noqa: E402
import plugins  # noqa: E402
import repo_config  # noqa: E402
import tools  # noqa: E402
import setup_v1_facts  # noqa: E402
from places import (PROVIDERS, Places, backup_once, has_backup, place_key,  # noqa: E402
                    write_atomic)

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
LOCAL_IGNORE_PATH = ".claude/settings.local.json"
LOCAL_IGNORE_LINE = b"/" + LOCAL_IGNORE_PATH.encode("ascii")
IGNORE_ADDED = "ignore-line-added"
END_LINE = re.compile(r"afkv2-core-behaviors end ([0-9a-f]{12})")
BEGIN_LINE = re.compile(r"afkv2-core-behaviors begin ([0-9a-f]{12})")
TRUST_REVIEW = ("Codex skips an untrusted hook without a message: open a new Codex session, "
                "trust the afkv2 hooks in the hook trust review, then run setup again")


@dataclass
class System:
    """Operating-system hooks; a test replaces each one."""

    run: tools.Runner = field(default_factory=tools.Runner)
    windows: bool = os.name == "nt"
    fresh_env: Callable[[], Mapping[str, str]] | None = None
    add_to_user_path: Callable[[Path], bool] | None = None
    user_env: jira_values.UserEnv | None = None
    ask: Callable[[str], str] = input
    ask_secret: Callable[[str], str] = getpass.getpass
    is_terminal: Callable[[], bool] = lambda: sys.stdin.isatty()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _error(code: str, reason: str, **extra) -> dict:
    return {"ok": False, "error": {"code": code, "reason": reason}, **extra}


# ============================================================ install record

def read_install_record(places: Places) -> dict[str, str]:
    if not places.install_record.exists():
        return {}
    record = {}
    for line in places.install_record.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition(" ")
        record[key] = value
    return record


def write_install_record(places: Places, python: dict, rg: str | None) -> dict:
    """Keep the first `installed` time: the hook proof compares against it."""
    record = read_install_record(places)
    record.setdefault("installed", _now().isoformat())
    record["python"] = f"{python['path']} {python['version']}"
    record["rg"] = rg or "unknown"
    text = "".join(f"{k} {record[k]}\n" for k in ("installed", "python", "rg"))
    write_atomic(places.install_record, text.encode("utf-8"))
    return record


# ============================================================ v1 rule block

def find_blocks(data: bytes) -> tuple[list[tuple[int, int, str]], str | None]:
    """Byte ranges of v1 blocks, each from its full begin line through its full end line."""
    begins = {setup_v1_facts.block_begin(n): n for n in setup_v1_facts.BLOCK_NAMES}
    ends = {setup_v1_facts.block_end(n): n for n in setup_v1_facts.BLOCK_NAMES}
    found, opened, at = [], None, 0
    for number, line in enumerate(data.splitlines(keepends=True), start=1):
        body = line.rstrip(b"\r\n")
        if body in begins:
            if opened:
                return [], f"line {number}: a begin line inside the {opened[1]} block"
            opened = (at, begins[body])
        elif body in ends:
            if not opened or ends[body] != opened[1]:
                return [], f"line {number}: an end line with no matching begin line"
            found.append((opened[0], at + len(line), opened[1]))
            opened = None
        at += len(line)
    if opened:
        return [], f"the {opened[1]} block has no end line"
    return found, None


def _instruction_backup(places: Places, provider: str) -> Path:
    return places.backup / "instructions" / provider


def keep_instruction_backups(places: Places) -> list[str]:
    """Back up each instruction file that holds a v1 block, before any proof."""
    kept = []
    for provider in PROVIDERS:
        target = places.instruction_file(provider)
        if target.exists() and find_blocks(target.read_bytes())[0]:
            if backup_once(target, _instruction_backup(places, provider) / "original"):
                kept.append(str(target))
    return kept


def remove_v1_block(places: Places) -> dict:
    """Remove every v1 block from both instruction files in one run, or from neither."""
    plans = []
    for provider in PROVIDERS:
        target = places.instruction_file(provider)
        data = target.read_bytes() if target.exists() else b""
        blocks, problem = find_blocks(data)
        if problem:
            return _error("bad-block", f"{target}: {problem}; nothing was removed")
        plans.append((provider, target, data, blocks))
    files = []
    for provider, target, data, blocks in plans:
        if not blocks:
            files.append({"path": str(target), "action": "absent"})
            continue
        kept, cursor, removed = [], 0, []
        for start, end, _ in blocks:
            kept.append(data[cursor:start])
            removed.append(data[start:end])
            cursor = end
        kept.append(data[cursor:])
        after = b"".join(kept)
        saved = _instruction_backup(places, provider)
        write_atomic(saved / "original", data)
        write_atomic(saved / "blocks", b"".join(removed))
        write_atomic(saved / "after", after)
        write_atomic(target, after)
        files.append({"path": str(target), "action": "removed", "blocks": len(blocks)})
    return {"ok": True, "files": files}


def restore_v1_block(places: Places) -> list[dict]:
    done = []
    for provider in PROVIDERS:
        saved = _instruction_backup(places, provider)
        if not (saved / "original").exists():
            continue
        target = places.instruction_file(provider)
        try:
            action = _restore_one_instruction_file(target, saved)
            shutil.rmtree(saved)
        except OSError as exc:
            done.append({"path": str(target), "action": "failed", "reason": str(exc),
                         "backup": str(saved)})
            continue
        done.append({"path": str(target), "action": action})
    return done


def _restore_one_instruction_file(target: Path, saved: Path) -> str:
    current = target.read_bytes() if target.exists() else b""
    if not (saved / "after").exists():
        return "kept-backup-dropped"
    if current == (saved / "after").read_bytes():
        write_atomic(target, (saved / "original").read_bytes())
        return "restored"
    if find_blocks(current)[0]:
        return "block-present"
    eol = b"\r\n" if b"\r\n" in current else b"\n"
    sep = b"" if not current or current.endswith((b"\n", b"\r")) else eol
    write_atomic(target, current + sep + (saved / "blocks").read_bytes())
    return "appended"


# ================================================================ hook proof

def expected_sha12s(plugin_root: Path) -> set[str]:
    """sha12 values of the prebuilt core-behaviors files in the plugin tree."""
    found = set()
    for path in plugin_root.rglob("*"):
        if not path.is_file() or "tests" in path.relative_to(plugin_root).parts:
            continue
        if path.stat().st_size > 64_000:
            continue
        try:
            lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        except (UnicodeDecodeError, OSError):
            continue
        if len(lines) < 2:
            continue
        begin, end = BEGIN_LINE.fullmatch(lines[0]), END_LINE.fullmatch(lines[-1])
        if begin and end and begin.group(1) == end.group(1):
            found.add(begin.group(1))
    return found


def required_providers(places: Places, current: str, codex_state: Mapping[str, bool]) -> list[str]:
    """The current provider, plus each provider that still uses v1."""
    needed = {current}
    for provider in PROVIDERS:
        target = places.instruction_file(provider)
        if target.exists() and find_blocks(target.read_bytes())[0]:
            needed.add(provider)
    if any(on for i, on in codex_state.items() if plugins.plugin_name(i) == setup_v1_facts.PLUGIN_NAME):
        needed.add("codex")
    return [p for p in PROVIDERS if p in needed]


def prove_hook(places: Places, provider: str, end_marker: str, plugin_root: Path,
               required: list[str]) -> dict:
    """Pass when each required fired record is newer than the install record
    and the agent's end-marker line carries a sha12 the plugin ships."""
    reasons = []
    installed = read_install_record(places).get("installed")
    if not installed:
        reason = "run `setup.py prepare` first"
        return _error("no-install-record", reason, proved=False, reasons=[reason])
    since = datetime.fromisoformat(installed).timestamp()
    for name in required:
        fired = places.fired_record(name)
        if not fired.exists():
            reasons.append(f"{name}: the afkv2 hook never fired"
                           + ("; " + TRUST_REVIEW if name == "codex" else ""))
        elif fired.stat().st_mtime <= since:
            reasons.append(f"{name}: the hook last fired before setup's install record; "
                           "start a new session and run setup again"
                           + ("; " + TRUST_REVIEW if name == "codex" else ""))
    match = END_LINE.fullmatch(end_marker.strip())
    shipped = expected_sha12s(plugin_root)
    if not match:
        reasons.append(f"{provider}: the agent reported no end-marker line")
    elif match.group(1) not in shipped:
        reasons.append(f"{provider}: the end marker sha12 {match.group(1)} matches no "
                       "prebuilt core-behaviors file (text cut, or a stale session)")
    return {"ok": not reasons, "proved": not reasons, "required": required, "reasons": reasons}


# ============================================================ v1 git hooks

def _git(run: tools.Runner, repo: Path, *args: str) -> tools.Result:
    return run(["git", "-C", str(repo), *args], timeout=60)


def repo_top(run: tools.Runner, start: Path) -> Path | None:
    got = _git(run, start, "rev-parse", "--show-toplevel")
    return Path(got.out.strip()) if got.code == 0 and got.out.strip() else None


def _common_dir(run: tools.Runner, repo: Path) -> Path | None:
    got = _git(run, repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(got.out.strip()) if got.code == 0 and got.out.strip() else None


def is_v1_stub(path: Path, hook: str) -> bool:
    if not path.is_file():
        return False
    wanted = setup_v1_facts.STUB_LINES[hook]
    return any(line.rstrip(b"\r\n") == wanted for line in path.read_bytes().splitlines())


def move_v1_git_hooks(places: Places, repo: Path, run: tools.Runner) -> dict:
    """Move the v1 stubs of this repository into the backup folder."""
    if _git(run, repo, "config", "--get", "core.hooksPath").out.strip():
        return {"ok": True, "action": "skipped", "reason": "core.hooksPath is set; v1 stubs do not run"}
    common = _common_dir(run, repo)
    if common is None:
        return _error("not-a-repo", f"{repo} is not a git repository")
    hooks = common / "hooks"
    saved = places.backup / "git-hooks" / place_key(hooks)
    moved = {}
    for hook in setup_v1_facts.STUB_LINES:
        target, keep = hooks / hook, saved / hook
        if keep.exists():
            moved[hook] = "already-moved"
        elif is_v1_stub(target, hook):
            saved.mkdir(parents=True, exist_ok=True)
            (saved / "place.txt").write_text(str(hooks), encoding="utf-8")
            shutil.move(str(target), str(keep))
            moved[hook] = "moved"
        else:
            moved[hook] = "foreign" if target.exists() else "absent"
    return {"ok": True, "hooks_dir": str(hooks), "hooks": moved}


def _placed_backups(root: Path) -> list[Path]:
    """Backup folders that name their place. `place.txt` goes in before any
    backup does, so a folder without it holds nothing and is dropped."""
    placed = []
    for saved in sorted(root.iterdir()) if root.exists() else []:
        if (saved / "place.txt").exists():
            placed.append(saved)
        else:
            shutil.rmtree(saved, ignore_errors=True)
    return placed


def _remove_backup(saved: Path) -> dict:
    """The fields that report a finished backup that could not be deleted."""
    try:
        shutil.rmtree(saved)
    except OSError as exc:
        return {"action": "failed", "reason": str(exc), "backup": str(saved)}
    return {}


def restore_v1_git_hooks(places: Places) -> list[dict]:
    done = []
    for saved in _placed_backups(places.backup / "git-hooks"):
        hooks = Path((saved / "place.txt").read_text(encoding="utf-8"))
        if not hooks.parent.exists():
            done.append({"path": str(hooks), "action": "repo-missing", **_remove_backup(saved)})
            continue
        for hook in setup_v1_facts.STUB_LINES:
            keep, target = saved / hook, hooks / hook
            if not keep.exists():
                continue
            try:
                action = _restore_one_stub(keep, target)
            except OSError as exc:
                done.append({"path": str(target), "action": "failed", "reason": str(exc),
                             "backup": str(keep)})
                continue
            entry = {"path": str(target), "action": action}
            done.append(entry | {"backup": str(keep)} if action == "conflict" else entry)
        if not any(p.name in setup_v1_facts.STUB_LINES for p in saved.iterdir()):
            failed = _remove_backup(saved)
            if failed:
                done.append({"path": str(hooks), **failed})
    return done


def _restore_one_stub(keep: Path, target: Path) -> str:
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(keep), str(target))
        return "restored"
    if target.read_bytes() == keep.read_bytes():
        keep.unlink()
        return "already-there"
    return "conflict"


# ============================================================ plugin switch

def _codex_state(places: Places, run: tools.Runner) -> tuple[dict[str, bool], str]:
    """Codex plugin state as `codex plugin list` lists it; the config file if no CLI."""
    got = run(["codex", "plugin", "list"], timeout=60)
    if got.code == 0:
        return plugins.parse_codex_list(got.out), "codex plugin list"
    if places.codex_config.exists():
        return plugins.codex_config_state(places.codex_config.read_text(encoding="utf-8")), "config"
    return {}, "none"


def _exclude_file(run: tools.Runner, repo: Path) -> Path | None:
    common = _common_dir(run, repo)
    return common / "info" / "exclude" if common else None


def _ensure_local_ignored(repo: Path, run: tools.Runner, saved: Path | None) -> bool:
    """Keep the personal settings file out of git; `saved` records that this run added the line."""
    if _git(run, repo, "check-ignore", "-q", LOCAL_IGNORE_PATH).code == 0:
        return False
    exclude = _exclude_file(run, repo)
    if exclude is None:
        return False
    old = exclude.read_bytes() if exclude.exists() else b""
    sep = b"" if not old or old.endswith(b"\n") else b"\n"
    if saved is not None:
        (saved / IGNORE_ADDED).write_bytes(b"")
    write_atomic(exclude, old + sep + LOCAL_IGNORE_LINE + b"\n")
    return True


def _drop_ignore_line(repo: Path, run: tools.Runner) -> bool | None:
    """Whether a line was removed; None when git cannot name the file of a live repository."""
    exclude = _exclude_file(run, repo)
    if exclude is None:
        return None if (repo / ".git").exists() else False
    if not exclude.exists():
        return False
    lines = exclude.read_bytes().splitlines(keepends=True)
    kept = [line for line in lines if line.rstrip(b"\r\n") != LOCAL_IGNORE_LINE]
    if len(kept) == len(lines):
        return False
    write_atomic(exclude, b"".join(kept))
    return True


def _switch_claude(places: Places, repo: Path, run: tools.Runner, enable: str,
                   with_backup: bool) -> dict:
    user = places.claude_user_settings
    wanted = plugins.claude_target(user, repo, enable)
    local = repo / ".claude" / "settings.local.json"
    saved = places.backup / "claude-settings" / place_key(repo)
    if with_backup and not has_backup(saved / "settings.local.json"):
        saved.mkdir(parents=True, exist_ok=True)
        (saved / "place.txt").write_text(str(repo), encoding="utf-8")
        backup_once(local, saved / "settings.local.json")
    written = plugins.write_claude_local(repo, wanted)
    ignored_now = local.exists() and _ensure_local_ignored(repo, run, saved if with_backup else None)
    effective = plugins.claude_effective(user, repo)
    answer = {"written": written, "exclude_added": bool(ignored_now), "effective": effective}
    if plugins.only_one_on(effective) != enable:
        return {"ok": False, **answer, "error": {
            "code": "both-enabled" if all(effective.values()) else "switch-failed",
            "reason": f"after the write, Claude does not have only {enable} on in {repo}"}}
    return {"ok": True, **answer}


def _switch_codex(places: Places, run: tools.Runner, enable: str, with_backup: bool) -> dict:
    config = places.codex_config
    if not config.exists():
        return {"ok": True, "action": "no-codex-config"}
    text = config.read_bytes().decode("utf-8")  # keeps CRLF line ends as they are
    state = plugins.codex_config_state(text)
    if not any(plugins.plugin_name(i) == enable for i in state):
        return {"ok": True, "action": "not-installed", "reason": f"Codex has no {enable} plugin"}
    wanted = {i: plugins.plugin_name(i) == enable for i in state}
    written = False
    if any(state[i] != v for i, v in wanted.items()):
        if with_backup:
            try:  # the config can hold the Jira token
                tools.lock_to_current_user(places.backup, run)
            except OSError as exc:
                return {"ok": False, "written": False, "error": {
                    "code": "backup-not-private", "reason": f"{exc}; the Codex config did not change"}}
            backup_once(config, places.backup / "codex" / "config.toml")
        write_atomic(config, plugins.codex_edit(text, wanted).encode("utf-8"))
        written = True
    listed, source = _codex_state(places, run)
    answer = {"written": written, "listed": listed, "listed_by": source}
    if plugins.only_one_on(listed) != enable:
        return {"ok": False, **answer, "error": {
            "code": "both-enabled" if listed and all(listed.values()) else "switch-failed",
            "reason": f"after the write, Codex does not list only {enable} as enabled"}}
    return {"ok": True, **answer}


def switch_plugins(places: Places, repo: Path, run: tools.Runner) -> dict:
    """afkv2 on and v1 off: Claude in this project's local settings, Codex globally."""
    claude = _switch_claude(places, repo, run, plugins.NEW_NAME, with_backup=True)
    codex = _switch_codex(places, run, plugins.NEW_NAME, with_backup=True)
    return {"ok": claude["ok"] and codex["ok"], "claude": claude, "codex": codex}


# ================================================================ switch back

def published_tickets(places: Places) -> list[str]:
    if not places.published_tickets.exists():
        return []
    keys: list[str] = []
    for line in places.published_tickets.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] not in keys:
            keys.append(parts[1])
    return keys


def _attempt(step: Callable[[], dict]) -> dict:
    """One step's answer; an unreadable or unwritable file fails that step only."""
    try:
        return step()
    except (ValueError, OSError) as exc:
        return _error("unreadable-input", f"{type(exc).__name__}: {exc}")


def _leave_v1_only(places: Places, repos: list[Path], run: tools.Runner) -> dict:
    claude = []
    for repo in repos:
        def switch(repo=repo):
            effective = plugins.claude_effective(places.claude_user_settings, repo)
            if plugins.only_one_on(effective) == setup_v1_facts.PLUGIN_NAME:
                return {"ok": True, "written": False, "effective": effective}
            return _switch_claude(places, repo, run, setup_v1_facts.PLUGIN_NAME, with_backup=False)
        claude.append(_attempt(switch) | {"repo": str(repo)})
    codex = _attempt(lambda: _switch_codex(places, run, setup_v1_facts.PLUGIN_NAME, with_backup=False))
    return {"ok": all(c["ok"] for c in claude) and codex["ok"], "claude": claude, "codex": codex}


def _restore_repo_settings(saved: Path) -> dict:
    repo = Path((saved / "place.txt").read_text(encoding="utf-8"))
    if not repo.exists():
        return {"repo": str(repo), "settings": "repo-missing"}
    try:
        action = plugins.restore_claude_local(repo / ".claude" / "settings.local.json",
                                              saved / "settings.local.json")
    except (ValueError, OSError) as exc:
        return {"repo": str(repo), "settings": "failed", "reason": f"{type(exc).__name__}: {exc}",
                "backup": str(saved)}
    return {"repo": str(repo), "settings": action}


def _restore_codex_config(places: Places) -> str:
    saved = places.backup / "codex" / "config.toml"
    if not saved.exists():
        return "no-backup"
    config = places.codex_config
    try:
        before = saved.read_bytes().decode("utf-8")
        now = plugins.codex_restore(config.read_bytes().decode("utf-8"), before) if config.exists() else before
        write_atomic(config, now.encode("utf-8"))
    except (ValueError, OSError):
        return "failed"
    saved.unlink()
    return "restored" if now == before else "merged"


def switch_back(places: Places, run: tools.Runner, env: Mapping[str, str],
                user_env: jira_values.UserEnv | None = None) -> dict:
    """Restore every backup, leave only v1 on, and list the tickets afkv2 published."""
    blocks = restore_v1_block(places)
    hooks = restore_v1_git_hooks(places)
    saved_dirs = _placed_backups(places.backup / "claude-settings")
    settings = [_restore_repo_settings(saved) for saved in saved_dirs]
    live = [Path(s["repo"]) for s in settings if s["settings"] not in ("repo-missing", "failed")]
    codex = _restore_codex_config(places)
    jira = {"claude_user_config": jira_values.restore_claude_user_config(places),
            "user_environment": jira_values.restore_user_env(places, user_env)}
    lavish = _attempt(lambda: tools.restore_lavish(places, run, env))
    one_on = _leave_v1_only(places, live, run)
    not_switched = {c["repo"] for c in one_on["claude"] if not c["ok"]}
    for saved, answer in zip(saved_dirs, settings):
        if answer["settings"] == "failed" or answer["repo"] in not_switched:
            continue
        repo = Path(answer["repo"])
        if (saved / IGNORE_ADDED).exists() and repo in live and not (repo / LOCAL_IGNORE_PATH).exists():
            dropped = _drop_ignore_line(repo, run)
            if dropped is None:
                answer.update(settings="failed", backup=str(saved),
                              reason="git cannot read this repository, so its ignore line stays; "
                                     "fix git access (for example safe.directory), then run switch-back again")
                continue
            answer["ignore_line"] = "removed" if dropped else "absent"
        failed = _remove_backup(saved)
        if failed:
            answer.update(settings="failed", reason=failed["reason"], backup=failed["backup"])
    ok = (lavish["ok"] and one_on["ok"] and codex != "failed"
          and not any(step["action"] == "failed" for step in jira.values())
          and not any(b["action"] == "failed" for b in blocks)
          and not any(h["action"] in ("conflict", "failed") for h in hooks)
          and not any(s["settings"] == "failed" for s in settings))
    if ok:
        places.install_record.unlink(missing_ok=True)
    return {"ok": ok, "blocks": blocks, "git_hooks": hooks, "claude_settings": settings,
            "codex_config": codex, "jira_values": jira, "lavish": lavish, "plugins": one_on,
            "backup_dir": str(places.backup), "published_tickets": published_tickets(places)}


# ==================================================================== verbs

def prepare(places: Places, system: System, env: Mapping[str, str]) -> dict:
    fresh = system.fresh_env or (lambda: env)
    python = tools.find_python(system.run, fresh())
    if not python["ok"]:
        return python
    probes = tools.shell_probes(system.windows, lambda n: system.run.which(n, env))
    rg = tools.ensure_rg(system.run, fresh, probes,
                         system.add_to_user_path or (lambda _f: False), system.windows)
    record = write_install_record(places, python, rg.get("rg") or system.run.which("rg", fresh()))
    return {"ok": rg["ok"], "python": python, "rg": rg, "install_record": record,
            **({"error": rg["error"]} if not rg["ok"] else {})}


def status(places: Places, repo: Path, system: System, env: Mapping[str, str]) -> dict:
    codex_state, codex_source = _codex_state(places, system.run)
    blocks = {}
    for provider in PROVIDERS:
        target = places.instruction_file(provider)
        found, problem = find_blocks(target.read_bytes()) if target.exists() else ([], None)
        blocks[provider] = {"path": str(target), "blocks": len(found), "problem": problem}
    hooks_dir = (_common_dir(system.run, repo) or repo / ".git") / "hooks"
    return {
        "ok": True,
        "repo": str(repo),
        "install_record": read_install_record(places),
        "fired": {p: places.fired_record(p).exists() for p in PROVIDERS},
        "jira": jira_values.status(places, env),
        "v1_config": repo_config.copy_plan(repo),
        "config_file": repo_config.afkv2_config(repo).exists(),
        "spec_folder": repo_config.spec_folder_state(repo),
        "ownership": repo_config.ownership_state(repo, places),
        "v1_blocks": blocks,
        "v1_git_hooks": {h: is_v1_stub(hooks_dir / h, h) for h in setup_v1_facts.STUB_LINES},
        "claude_plugins": plugins.claude_effective(places.claude_user_settings, repo),
        "codex_plugins": codex_state, "codex_listed_by": codex_source,
        "takeover_backups": places.backup.exists() and any(places.backup.iterdir()),
    }


def _check_plugin_inputs(places: Places, repo: Path) -> dict:
    """Read what the plugin switch reads, before the first change."""
    plugins.claude_effective(places.claude_user_settings, repo)
    if places.codex_config.exists():
        places.codex_config.read_bytes().decode("utf-8")
    return {"ok": True}


def takeover(places: Places, repo: Path, system: System, env: Mapping[str, str],
             provider: str, end_marker: str, plugin_root: Path) -> dict:
    kept = keep_instruction_backups(places)
    codex_state, _ = _codex_state(places, system.run)
    proof = prove_hook(places, provider, end_marker, plugin_root,
                       required_providers(places, provider, codex_state))
    if not proof.get("proved"):
        return {"ok": False, "proof": proof, "v1_block": "kept", "backups_kept": kept,
                "next": "start a new session and run setup again. " + TRUST_REVIEW,
                "error": proof.get("error") or {"code": "no-proof", "reason": "; ".join(proof["reasons"])}}
    steps = {"proof": proof}
    for name, step in (("plugin_inputs", lambda: _check_plugin_inputs(places, repo)),
                       ("v1_block", lambda: remove_v1_block(places)),
                       ("git_hooks", lambda: move_v1_git_hooks(places, repo, system.run)),
                       ("plugins", lambda: switch_plugins(places, repo, system.run)),
                       ("lavish", lambda: tools.install_lavish_pin(places, system.run, env))):
        steps[name] = _attempt(step)
        if not steps[name]["ok"]:
            return {"ok": False, **steps, "error": steps[name].get("error")
                    or {"code": f"{name}-failed", "reason": f"the {name} step failed"}}
    return {"ok": True, **steps}


def secrets(places: Places, system: System, env: Mapping[str, str]) -> dict:
    if env.get("CLAUDECODE") or not system.is_terminal():
        return _error("not-a-terminal", "run `setup.py secrets` in your own terminal, "
                      "not through the agent: the token must stay out of the transcript")
    try:
        values = jira_values.ask_values(jira_values.lookup(places, env), system.ask, system.ask_secret)
    except ValueError as exc:
        return _error("bad-value", f"{exc}; nothing was written")
    return jira_values.store_jira_values(
        places, values, system.user_env,
        lambda folder: tools.lock_to_current_user(folder, system.run, system.windows, env))


def default_system() -> System:
    if os.name != "nt":
        return System()
    return System(fresh_env=lambda: tools.fresh_windows_env(os.environ),
                  add_to_user_path=tools.windows_user_path_adder,
                  user_env=jira_values.WINDOWS_USER_ENV)


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None,
         system: System | None = None, plugin_root: Path = PLUGIN_ROOT,
         cwd: Path | None = None) -> int:
    env = os.environ if env is None else env
    system = system or default_system()
    parser = argparse.ArgumentParser(prog="setup.py", description=__doc__.splitlines()[0])
    parser.add_argument("verb", choices=("status", "prepare", "secrets", "copy-config",
                                         "ownership", "takeover", "switch-back"))
    parser.add_argument("--repo")
    parser.add_argument("--provider", choices=PROVIDERS)
    parser.add_argument("--end-marker", default="")
    parser.add_argument("--own", nargs="*", default=[])
    parser.add_argument("--shared", nargs="*", default=[])
    parser.add_argument("--skip", action="store_true")
    parser.add_argument("--spec-folder")
    parser.add_argument("--no-v1-values", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        print(json.dumps(_error("bad-arguments", "see setup.py --help")))
        return 2
    places = Places.from_env(env)
    repo = None
    if args.verb not in ("prepare", "secrets", "switch-back"):
        repo = repo_top(system.run, Path(args.repo) if args.repo else (cwd or Path.cwd()))
        if repo is None:
            print(json.dumps(_error("not-a-repo", "run setup inside a git repository")))
            return 2
    if args.verb == "takeover" and not args.provider:
        print(json.dumps(_error("bad-arguments", "takeover needs --provider")))
        return 2
    try:
        if args.verb == "status":
            answer = status(places, repo, system, env)
        elif args.verb == "prepare":
            answer = prepare(places, system, env)
        elif args.verb == "secrets":
            answer = secrets(places, system, env)
        elif args.verb == "copy-config":
            answer = repo_config.write_config(repo, args.spec_folder, with_v1=not args.no_v1_values)
        elif args.verb == "ownership":
            answer = (repo_config.record_ownership_skip(repo, places) if args.skip
                      else repo_config.write_ownership(repo, places, args.own, args.shared))
        elif args.verb == "takeover":
            answer = takeover(places, repo, system, env, args.provider, args.end_marker, plugin_root)
        else:
            answer = switch_back(places, system.run, env, system.user_env)
    except (ValueError, OSError) as exc:
        print(json.dumps(_error("unreadable-input", f"{type(exc).__name__}: {exc}")))
        return 2
    print(json.dumps(answer, indent=2, default=str))
    return 0 if answer.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

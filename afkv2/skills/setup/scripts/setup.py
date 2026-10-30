"""afkv2 setup: install, prove the hook, take over from v1, switch back.

Usage: setup.py <verb> [options]   (each verb answers one JSON object)

  status                                   read-only report
  prepare                                  Python 3, rg on every shell, install record
  secrets                                  the developer's own terminal only: Jira values
  copy-config                              one copy of the v1 config values into .afkv2
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
import v1_facts  # noqa: E402
from places import (PROVIDERS, Places, backup_once, has_backup, place_key,  # noqa: E402
                    restore, write_atomic)

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
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
    set_user_env: Callable[[str, str], None] | None = None
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
    begins = {v1_facts.block_begin(n): n for n in v1_facts.BLOCK_NAMES}
    ends = {v1_facts.block_end(n): n for n in v1_facts.BLOCK_NAMES}
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
        write_atomic(target, after)
        write_atomic(saved / "after", after)
        files.append({"path": str(target), "action": "removed", "blocks": len(blocks)})
    return {"ok": True, "files": files}


def restore_v1_block(places: Places) -> list[dict]:
    done = []
    for provider in PROVIDERS:
        saved = _instruction_backup(places, provider)
        if not (saved / "original").exists():
            continue
        target = places.instruction_file(provider)
        current = target.read_bytes() if target.exists() else b""
        if not (saved / "after").exists():
            action = "kept-backup-dropped"
        elif current == (saved / "after").read_bytes():
            write_atomic(target, (saved / "original").read_bytes())
            action = "restored"
        elif find_blocks(current)[0]:
            action = "block-present"
        else:
            eol = b"\r\n" if b"\r\n" in current else b"\n"
            sep = b"" if not current or current.endswith((b"\n", b"\r")) else eol
            write_atomic(target, current + sep + (saved / "blocks").read_bytes())
            action = "appended"
        shutil.rmtree(saved)
        done.append({"path": str(target), "action": action})
    return done


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
    if any(on for i, on in codex_state.items() if plugins.plugin_name(i) == v1_facts.PLUGIN_NAME):
        needed.add("codex")
    return [p for p in PROVIDERS if p in needed]


def prove_hook(places: Places, provider: str, end_marker: str, plugin_root: Path,
               required: list[str]) -> dict:
    """Pass when each required fired record is newer than the install record
    and the agent's end-marker line carries a sha12 the plugin ships."""
    reasons = []
    installed = read_install_record(places).get("installed")
    if not installed:
        return _error("no-install-record", "run `setup.py prepare` first", proved=False)
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


def _common_dir(run: tools.Runner, repo: Path) -> Path:
    got = _git(run, repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(got.out.strip())


def is_v1_stub(path: Path, hook: str) -> bool:
    if not path.is_file():
        return False
    wanted = v1_facts.STUB_LINES[hook]
    return any(line.rstrip(b"\r\n") == wanted for line in path.read_bytes().splitlines())


def move_v1_git_hooks(places: Places, repo: Path, run: tools.Runner) -> dict:
    """Move the v1 stubs of this repository into the backup folder."""
    if _git(run, repo, "config", "--get", "core.hooksPath").out.strip():
        return {"ok": True, "action": "skipped", "reason": "core.hooksPath is set; v1 stubs do not run"}
    hooks = _common_dir(run, repo) / "hooks"
    saved = places.backup / "git-hooks" / place_key(hooks)
    moved = {}
    for hook in v1_facts.STUB_LINES:
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


def restore_v1_git_hooks(places: Places) -> list[dict]:
    done = []
    root = places.backup / "git-hooks"
    for saved in sorted(root.iterdir()) if root.exists() else []:
        hooks = Path((saved / "place.txt").read_text(encoding="utf-8"))
        for hook in v1_facts.STUB_LINES:
            keep, target = saved / hook, hooks / hook
            if not keep.exists():
                continue
            if not target.exists():
                shutil.move(str(keep), str(target))
                action = "restored"
            elif target.read_bytes() == keep.read_bytes():
                keep.unlink()
                action = "already-there"
            else:
                done.append({"path": str(target), "action": "conflict", "backup": str(keep)})
                continue
            done.append({"path": str(target), "action": action})
        if not any(p.name in v1_facts.STUB_LINES for p in saved.iterdir()):
            shutil.rmtree(saved)
    return done


# ============================================================ plugin switch

def _codex_state(places: Places, run: tools.Runner) -> tuple[dict[str, bool], str]:
    """Codex plugin state as `codex plugin list` lists it; the config file if no CLI."""
    got = run(["codex", "plugin", "list"], timeout=60)
    if got.code == 0:
        return plugins.parse_codex_list(got.out), "codex plugin list"
    if places.codex_config.exists():
        return plugins.codex_config_state(places.codex_config.read_text(encoding="utf-8")), "config"
    return {}, "none"


def _ensure_local_ignored(repo: Path, run: tools.Runner, saved: Path | None) -> bool:
    if _git(run, repo, "check-ignore", "-q", ".claude/settings.local.json").code == 0:
        return False
    exclude = _common_dir(run, repo) / "info" / "exclude"
    if saved is not None:
        backup_once(exclude, saved / "exclude")
    old = exclude.read_bytes() if exclude.exists() else b""
    sep = b"" if not old or old.endswith(b"\n") else b"\n"
    write_atomic(exclude, old + sep + b"/.claude/settings.local.json\n")
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
    ignored_now = written and _ensure_local_ignored(repo, run, saved if with_backup else None)
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


def _leave_v1_only(places: Places, repos: list[Path], run: tools.Runner) -> dict:
    claude = [_switch_claude(places, r, run, v1_facts.PLUGIN_NAME, with_backup=False) | {"repo": str(r)}
              for r in repos]
    codex = _switch_codex(places, run, v1_facts.PLUGIN_NAME, with_backup=False)
    return {"ok": all(c["ok"] for c in claude) and codex["ok"], "claude": claude, "codex": codex}


def switch_back(places: Places, run: tools.Runner, env: Mapping[str, str]) -> dict:
    """Restore every backup, leave only v1 on, and list the tickets afkv2 published."""
    blocks = restore_v1_block(places)
    hooks = restore_v1_git_hooks(places)
    settings, repos = [], []
    root = places.backup / "claude-settings"
    for saved in sorted(root.iterdir()) if root.exists() else []:
        repo = Path((saved / "place.txt").read_text(encoding="utf-8"))
        repos.append(repo)
        common = _common_dir(run, repo)
        settings.append({"repo": str(repo),
                         "settings": restore(saved / "settings.local.json",
                                             repo / ".claude" / "settings.local.json"),
                         "exclude": restore(saved / "exclude", common / "info" / "exclude")})
        shutil.rmtree(saved)
    codex = restore(places.backup / "codex" / "config.toml", places.codex_config)
    lavish = tools.restore_lavish(places, run, env)
    one_on = _leave_v1_only(places, repos, run)
    ok = lavish["ok"] and one_on["ok"] and not any(h["action"] == "conflict" for h in hooks)
    if ok:
        places.install_record.unlink(missing_ok=True)
    return {"ok": ok, "blocks": blocks, "git_hooks": hooks, "claude_settings": settings,
            "codex_config": codex, "lavish": lavish, "plugins": one_on,
            "published_tickets": published_tickets(places)}


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
    plan = repo_config.copy_plan(repo)
    plan.pop("_blocks", None)
    blocks = {}
    for provider in PROVIDERS:
        target = places.instruction_file(provider)
        found, problem = find_blocks(target.read_bytes()) if target.exists() else ([], None)
        blocks[provider] = {"path": str(target), "blocks": len(found), "problem": problem}
    hooks_dir = _common_dir(system.run, repo) / "hooks"
    return {
        "ok": True,
        "repo": str(repo),
        "install_record": read_install_record(places),
        "fired": {p: places.fired_record(p).exists() for p in PROVIDERS},
        "jira": jira_values.status(places, env),
        "v1_config": plan,
        "ownership": repo_config.ownership_state(repo, places),
        "v1_blocks": blocks,
        "v1_git_hooks": {h: is_v1_stub(hooks_dir / h, h) for h in v1_facts.STUB_LINES},
        "claude_plugins": plugins.claude_effective(places.claude_user_settings, repo),
        "codex_plugins": codex_state, "codex_listed_by": codex_source,
        "takeover_backups": places.backup.exists() and any(places.backup.iterdir()),
    }


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
    for name, step in (("v1_block", lambda: remove_v1_block(places)),
                       ("git_hooks", lambda: move_v1_git_hooks(places, repo, system.run)),
                       ("plugins", lambda: switch_plugins(places, repo, system.run)),
                       ("lavish", lambda: tools.install_lavish_pin(places, system.run, env))):
        steps[name] = step()
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
    return jira_values.store_jira_values(places, values, system.set_user_env)


def default_system() -> System:
    if os.name != "nt":
        return System()
    return System(fresh_env=lambda: tools.fresh_windows_env(os.environ),
                  add_to_user_path=tools.windows_user_path_adder,
                  set_user_env=jira_values.windows_user_env_setter)


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
            answer = repo_config.copy_v1_config(repo)
        elif args.verb == "ownership":
            answer = (repo_config.record_ownership_skip(repo, places) if args.skip
                      else repo_config.write_ownership(repo, places, args.own, args.shared))
        elif args.verb == "takeover":
            answer = takeover(places, repo, system, env, args.provider, args.end_marker, plugin_root)
        else:
            answer = switch_back(places, system.run, env)
    except (ValueError, OSError) as exc:
        print(json.dumps(_error("unreadable-input", f"{type(exc).__name__}: {exc}")))
        return 2
    print(json.dumps(answer, indent=2, default=str))
    return 0 if answer.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

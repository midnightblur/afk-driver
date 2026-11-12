"""The Claude CLI on the path: its version against its release channel, and Fable as the advisor.

Codex is out of scope: nothing here reads or writes under the Codex folder.
Facts (Claude Code docs, 2026-11-12): the advisor needs the `advisorModel` setting
(code.claude.com/docs/en/advisor); a plugin cannot ship that key, because plugin settings
keep only `agent` and `subagentStatusLine` (plugins-reference "settings"); Fable 5.2 needs
v2.1.321 or later; `autoUpdatesChannel` is `latest` (default) or `stable` (setup); on some
plans an interactive session uses Fable only after the one-time usage-credits consent of
`/model fable`, and that command also saves Fable as the main model (model-config).
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Callable, Mapping

from places import Places, backup_once, has_backup, write_atomic
import tools

ADVISOR = "fable"
FABLE_MIN_VERSION = (2, 1, 321)
RELEASES = "https://downloads.claude.ai/claude-code-releases/{channel}"  # not documented: a miss is a warning
CHANNELS = ("latest", "stable")
PROBE_MAIN_MODEL = "sonnet"  # accepts a Fable advisor (advisor docs, "Choose an advisor model")
PROBE_PROMPT = "Answer only: ok"
BLOCKING_ENV = {
    "CLAUDE_CODE_DISABLE_ADVISOR_TOOL": "turns the advisor off",
    "DISABLE_TELEMETRY": "stops the feature-flag fetch that the advisor needs",
    "CLAUDE_CODE_USE_BEDROCK": "Amazon Bedrock has no advisor",
    "CLAUDE_CODE_USE_VERTEX": "Google Cloud's Agent Platform has no advisor",
    "CLAUDE_CODE_USE_FOUNDRY": "Microsoft Foundry has no advisor",
}
UPDATE_COMMANDS = ("claude update", "winget upgrade Anthropic.ClaudeCode", "brew upgrade claude-code",
                   "npm install -g @anthropic-ai/claude-code@latest")
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)")

Fetch = Callable[[str], str]


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=15) as answer:  # noqa: S310 - fixed https URL
        return answer.read(64).decode("ascii", "replace")


def _version(text: str) -> tuple[int, int, int] | None:
    found = VERSION.search(text or "")
    return tuple(int(n) for n in found.groups()) if found else None


def _text(version: tuple[int, int, int] | None) -> str | None:
    return ".".join(map(str, version)) if version else None


def _settings(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def _error(code: str, reason: str, **extra) -> dict:
    return {"ok": False, "error": {"code": code, "reason": reason}, **extra}


# ================================================================== version

def _installed(run: tools.Runner, cli: str, env: Mapping[str, str]) -> tuple[int, int, int] | None:
    got = run([cli, "--version"], env=env, timeout=60)
    return _version(got.out) if got.code == 0 else None


def check_version(places: Places, run: tools.Runner, env: Mapping[str, str], fetch: Fetch = fetch_text) -> dict:
    """Compare the installed CLI with the newest release of its own channel; when it is older, run
    `claude update` once. The session that runs setup keeps the old version until a new session starts."""
    cli = run.which("claude", env)
    if not cli:
        return {"ok": True, "needed": False, "reason": "no claude program on the path: Claude Code is not used here"}
    installed = _installed(run, cli, env)
    if not installed:
        return _error("no-version", "`claude --version` printed no version")
    channel = _settings(places.claude_user_settings).get("autoUpdatesChannel") or "latest"
    channel = channel if channel in CHANNELS else "latest"
    try:
        newest = _version(fetch(RELEASES.format(channel=channel)))
    except OSError:
        newest = None
    answer = {"installed": _text(installed), "channel": channel, "newest": _text(newest),
              "fable_minimum": _text(FABLE_MIN_VERSION)}
    target = max(t for t in (newest, FABLE_MIN_VERSION) if t)
    if installed >= target:
        return {"ok": True, "action": "current", **answer,
                **({"warning": "the newest release could not be read; only the Fable minimum was checked"}
                   if not newest else {})}
    if channel == "stable" and newest and newest < FABLE_MIN_VERSION:
        return _error("channel-too-old", f"the stable channel serves {_text(newest)}, and Fable as the advisor needs "
                      f"{_text(FABLE_MIN_VERSION)}: set autoUpdatesChannel to latest with /config, then run setup "
                      "again", **answer)
    got = run([cli, "update"], env=env, timeout=600)
    after = _installed(run, cli, env)
    answer["update_output"] = (got.out or got.err).strip()[-300:]
    if after and after >= target:
        return {"ok": True, "action": "updated", **answer, "installed": _text(after), "new_session": True}
    return _error("update-required", f"Claude Code {_text(after or installed)} is older than {_text(target)}, and "
                  "`claude update` did not install a newer version. Update with the command of your install "
                  "method, then run setup again", commands=list(UPDATE_COMMANDS), **answer)


# ================================================================== advisor

def answer_file(places: Places) -> Path:
    """The developer's advisor answer, apart from the install record, so that switch-back keeps a no."""
    return places.data / "advisor-answer.txt"


def _backup(places: Places) -> Path:
    return places.backup / "advisor" / "settings.json"


def read_answer(places: Places) -> str | None:
    path = answer_file(places)
    return path.read_text(encoding="utf-8").strip() or None if path.exists() else None


def _record(places: Places, text: str) -> None:
    write_atomic(answer_file(places), (text + "\n").encode("utf-8"))


def blockers(places: Places, env: Mapping[str, str]) -> list[str]:
    """Environment values that keep the advisor off, from the process and the user settings `env`."""
    settings_env = _settings(places.claude_user_settings).get("env") or {}
    found = []
    for name, why in BLOCKING_ENV.items():
        value = env.get(name) or (settings_env.get(name) if isinstance(settings_env, dict) else None)
        if value and str(value) not in ("0", "false"):
            found.append(f"{name} is set: it {why}")
    return found


def overrides(repo: Path | None) -> list[str]:
    """Project and local settings outrank the user file. Managed settings are not read here."""
    if repo is None:
        return []
    found = []
    for layer in (repo / ".claude" / "settings.json", repo / ".claude" / "settings.local.json"):
        value = _settings(layer).get("advisorModel")
        if value is not None and value != ADVISOR:
            found.append(f"{layer} sets advisorModel to {value!r}, which outranks the user settings")
    return found


def status(places: Places, repo: Path | None, run: tools.Runner, env: Mapping[str, str]) -> str:
    """`not-used` (no claude program), `declined`, `ask`, `consent` (set, the consent step is open) or `done`."""
    if not run.which("claude", env):
        return "not-used"
    answer = read_answer(places)
    if answer == "declined":
        return "declined"
    if _settings(places.claude_user_settings).get("advisorModel") != ADVISOR:
        return "ask"
    return "done" if answer and answer.startswith("consent-done") else "consent"


def probe(run: tools.Runner, cli: str, env: Mapping[str, str]) -> dict:
    """1 print-mode call with the Fable advisor: a launch check. Claude Code refuses at launch, with an exit code
    or a line about the advisor, an advisor it cannot use. An API refusal later drops the advisor without a
    message, so a pass does not prove that a session consults Fable."""
    got = run([cli, "-p", "--model", PROBE_MAIN_MODEL, "--advisor", ADVISOR, "--max-turns", "1", PROBE_PROMPT],
              env=env, timeout=300)
    said = "\n".join(line for line in (got.out + "\n" + got.err).splitlines() if "advis" in line.lower())
    if got.code != 0 or said:
        return {"ok": False, "reason": (said or (got.err or got.out).strip())[:400]}
    return {"ok": True}


def set_advisor(places: Places, repo: Path | None, run: tools.Runner, env: Mapping[str, str], answer: str) -> dict:
    """Act on the developer's answer. Yes: run the launch check, then back up the user settings once, set
    `advisorModel` to Fable, and return the consent steps the developer types in a Claude session. A re-run
    asks nothing new and keeps the main model recorded first."""
    cli = run.which("claude", env)
    if not cli:
        return {"ok": True, "action": "not-used", "reason": "no claude program on the path"}
    if answer == "no":
        _record(places, "declined")
        return {"ok": True, "action": "declined"}
    found = blockers(places, env)
    if found:
        return _error("advisor-blocked", "; ".join(found) + ". Remove it, then run this step again")
    proof = probe(run, cli, env)
    if not proof["ok"]:
        return _error("proof-failed", proof["reason"])
    settings_path = places.claude_user_settings
    settings = _settings(settings_path)
    action = "already-set"
    if settings.get("advisorModel") != ADVISOR:
        backup_once(settings_path, _backup(places))
        settings["advisorModel"] = ADVISOR
        write_atomic(settings_path, (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        action = "set"
    record = read_answer(places) or ""
    if record.startswith("consent-done"):
        consent = "done"
    else:
        if not record.startswith("consent-open"):
            record = f"consent-open {settings.get('model') or ''}".strip()
            _record(places, record)
        consent = consent_steps(record.partition(" ")[2] or None)
    return {"ok": True, "action": action, "launch_check": proof, "overrides": overrides(repo), "consent": consent}


def consent_steps(previous: str | None) -> list[str]:
    back = f"/model {previous}" if previous else "/model default"
    return ["/model fable", "if Claude Code asks about usage credits, choose to continue on Fable", back]


def consent_done(places: Places) -> dict:
    """Record the consent step after the developer typed it; refuse while the main model is still Fable and
    it was not Fable before."""
    answer = read_answer(places) or ""
    if not answer.startswith(("consent-open", "consent-done")):
        return _error("no-advisor", "set the advisor first: setup.py advisor --answer yes")
    previous = answer.partition(" ")[2] or None
    model = _settings(places.claude_user_settings).get("model")
    if model != previous and "fable" in str(model or "") and "fable" not in str(previous or ""):
        return _error("model-not-restored", f"the main model is still {model!r}; type "
                      f"{consent_steps(previous)[-1]} in the Claude session, then run this step again")
    _record(places, f"consent-done {previous or ''}".strip())
    return {"ok": True, "action": "consent-done", "model": model}


def restore(places: Places) -> str:
    """Switch-back: put back the user's own `advisorModel` when the key still holds Fable; keep every other
    key of the file as the harness left it."""
    saved = _backup(places)
    if not has_backup(saved):
        return "no-backup"
    path = places.claude_user_settings
    try:
        before = _settings(saved).get("advisorModel") if saved.exists() else None
        settings = _settings(path)
        action = "kept-changed"
        if settings.get("advisorModel") == ADVISOR:
            if before is None:
                settings.pop("advisorModel")
            else:
                settings["advisorModel"] = before
            write_atomic(path, (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
            action = "restored"
    except (ValueError, OSError):
        return "failed"
    for leftover in (saved, saved.with_name(saved.name + ".absent")):
        leftover.unlink(missing_ok=True)
    if read_answer(places) != "declined":
        answer_file(places).unlink(missing_ok=True)
    return action

#!/usr/bin/env afk-python
"""ship.py — the ship script beside /afk:fix: one named step over one diagnosis.

Usage:
    afk-python ship.py open  DIAGNOSIS.md
    afk-python ship.py proof DIAGNOSIS.md --proof P-1=PATH --proof P-2=PATH [--evidence-link URL]
    afk-python ship.py ready DIAGNOSIS.md
    afk-python ship.py land  DIAGNOSIS.md

Run it in the diagnosis worktree, with a diagnosis the check script accepts.

- open: on the Diagnosis branch, look the change up by that branch, push the
  branch, open one Draft change onto the Base branch unless the lookup found
  one, list it (`change:`), then run rationale-post on it.
- proof: one comment with P-1, P-2 and the link to the ticket's evidence
  comment (required when the diagnosis names a ticket) — on the listed change,
  else, after a land, on the Base branch's open change. Listed as
  `evidence: afk-evidence {work id} change-proof`.
- ready: `ci-wait` on the listed change, polling every 180 s for at most
  5400 s, so run this step as a tracked background job. Only green marks the
  change ready, then adds the `mrReviewer` when one is configured.
- land: on the Diagnosis branch, fetch the Base branch, check the push is a
  fast-forward, and push HEAD onto it with plain git and upstream set, never
  forced. Listed as `push: {branch}@{commit}`. Refused when Base is the
  repository's base branch (`auto` reads as the remote's default branch, main
  and master): a fix for it ships through open, never land. Refused too when
  no commit past the Base commit was made on the Diagnosis branch.

A step whose entry is listed is skipped. Every other write is read back first
and retried at most twice, each time after a read-back shows it left nothing
(`outside_writes.py`). A protected push target and an empty change id are
refused before any write, as is a diagnosis with no Outside writes part.

Prints one JSON object: `step`, `status`, `reason` and the step's details.
Status: done; skipped (already listed); draft (CI not green, the change stays
Draft); no-change (no open change for the proof: put `text` in the run report);
refused (nothing written); not-fast-forward (the Base branch moved: rebase
once, run every tier, then land again); blocked (a write may have taken
effect: re-run the step, which reads back first). Exit 0 for done, skipped,
draft and no-change, 1 for refused, 2 for not-fast-forward and blocked.
"""
from __future__ import annotations

import argparse
import functools
import importlib.util
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

PLUGIN_ROOT = Path(__file__).resolve().parents[4]
DIAGNOSE_SCRIPTS = PLUGIN_ROOT / "skills" / "utils" / "diagnose" / "scripts"
LEDGER = PLUGIN_ROOT / "skills" / "afk" / "review" / "scripts" / "forge_ledger.py"
if str(DIAGNOSE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DIAGNOSE_SCRIPTS))

from check_diagnosis import check_diagnosis  # noqa: E402
from diagnosis_file import entry_problem, load_format, outside_write_kinds, sections  # noqa: E402
from outside_writes import append_outside_write, failed, listed, retry_with_read_back  # noqa: E402

STEPS = ("open", "proof", "ready", "land")
PROOF_KINDS = ("P-1", "P-2")
# The bug mode's own proof step writes `afk-evidence {work id} proof` to the same list.
PROOF_STEP = "change-proof"
CI_INTERVAL = 180
CI_BUDGET = 5400
CI_GRACE = 300
FORGE_TIMEOUT = 120
GIT_TIMEOUT = 300
LEDGER_TIMEOUT = 900
NOT_WRITABLE = {"closed", "merged", "locked"}
MADE_HERE = {"commit", "commit (amend)", "commit (merge)", "commit (initial)", "cherry-pick",
             "revert"}
EXIT = {"done": 0, "skipped": 0, "draft": 0, "no-change": 0, "refused": 1,
        "not-fast-forward": 2, "blocked": 2}


class Stop(Exception):
    """Ends a step with a status other than done."""

    def __init__(self, status: str, reason: str, **details):
        super().__init__(reason)
        self.status, self.reason, self.details = status, reason, details


def refuse(reason: str, **details) -> Stop:
    return Stop("refused", reason, **details)


def block(reason: str, **details) -> Stop:
    return Stop("blocked", reason, **details)


@functools.lru_cache(maxsize=None)
def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_answer(stdout: str):
    """The one JSON object a forge verb printed, or None."""
    text = (stdout or "").strip()
    for candidate in (text, text.splitlines()[-1] if text else ""):
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


class Forge:
    """`afk_adapter forge <verb>`, the payload on stdin: a native Windows argv loses its quotes."""

    def __init__(self, cwd: Path):
        self.cwd = Path(cwd)

    def run(self, verb: str, payload: dict, timeout: float):
        """(exit code, stdout, stderr) of one verb; raises subprocess.TimeoutExpired."""
        ledger = _load("afk_forge_ledger", LEDGER)
        bash = ledger.find_bash()
        if bash is None:
            return 127, "", "bash is unavailable"
        env = ledger.shell_env(bash)
        env.setdefault("AFK_PLUGIN_ROOT", str(PLUGIN_ROOT))
        command = [str(bash), "-c", '. "$AFK_PLUGIN_ROOT/hooks/lib/adapter.sh"; afk_adapter forge "$1"',
                   "--", verb]
        done = subprocess.run(command, cwd=self.cwd, env=env, input=json.dumps(payload),
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout)
        return done.returncode, done.stdout, done.stderr

    def call(self, verb: str, payload: dict) -> dict:
        try:
            code, out, err = self.run(verb, payload, FORGE_TIMEOUT)
        except subprocess.TimeoutExpired:
            return {"error": True, "reason": f"forge {verb} gave no answer within {FORGE_TIMEOUT} s"}
        answer = parse_answer(out)
        if answer is None:
            return {"error": True, "reason": (err.strip() or f"forge {verb} exited {code} with no answer")[-500:]}
        return answer

    def ci_wait(self, change: str):
        """(exit code, answer, stderr); the code is None when the wait outlived its budget."""
        payload = {"id": change, "budget": CI_BUDGET, "interval": CI_INTERVAL}
        try:
            code, out, err = self.run("ci-wait", payload, CI_BUDGET + CI_GRACE)
        except subprocess.TimeoutExpired:
            return None, None, f"ci-wait gave no answer within {CI_BUDGET + CI_GRACE} s"
        return code, parse_answer(out), err


def route_ci(code, answer, stderr: str = "") -> tuple[bool, str]:
    """(green, reason) from `ci-wait`'s exit code and stdout together: the codes collide
    with dispatch (2) and with a forge that has no CI (3)."""
    if code is None:
        return False, stderr
    if isinstance(answer, dict):
        status = str(answer.get("status") or "")
        reason = str(answer.get("reason") or "")
        if code == 3 and answer.get("unsupported"):
            return False, f"no CI: {reason or 'the forge has no ci-wait'}"
        if code == 0 and status == "success":
            return True, "CI green"
        if code == 1 and status in ("failed", "canceled"):
            return False, f"CI {status}"
        if code == 2 and status == "running":
            return False, f"CI still running after {CI_BUDGET} s; it keeps running"
        if code == 3 and status == "unreadable":
            return False, ("CI status unreadable 3 times running — auth, network, or a head commit "
                           f"with no CI: {reason}")
    shown = json.dumps(answer) if answer is not None else "no JSON answer"
    tail = f"; stderr: {stderr.strip()[-300:]}" if stderr and stderr.strip() else ""
    return False, f"ci-wait answer not understood: exit {code}, {shown}{tail}"


@dataclass
class Tools:
    """What a step reaches outside the worktree; a field left None takes its real default."""

    forge: object = None
    protected: Callable[[str], bool] | None = None
    setting: Callable[[str], str] | None = None
    post_reasons: Callable[[str], dict] | None = None
    base_branch: Callable[[], str] | None = None
    sleep: Callable[[float], None] = time.sleep


def _bind(tools: Tools, cwd: Path) -> Tools:
    return Tools(
        forge=tools.forge or Forge(cwd),
        protected=tools.protected or (lambda branch: _lookup_protected(branch, cwd)),
        setting=tools.setting or (lambda key: _resolve_setting(key, cwd)),
        post_reasons=tools.post_reasons or (lambda change: _rationale_post(change, cwd)),
        base_branch=tools.base_branch or (lambda: _base_branch(cwd)),
        sleep=tools.sleep,
    )


def _lookup_protected(branch: str, cwd: Path) -> bool:
    module = _load("afk_protected_lookup", PLUGIN_ROOT / "scripts" / "protected-lookup.py")
    return bool(module.lookup(branch, Path(cwd)).get("protected"))


def _resolve_setting(key: str, cwd: Path) -> str:
    """A developer setting through `afk-config.py resolve`; `none` and unset give ""."""
    done = subprocess.run([sys.executable, str(PLUGIN_ROOT / "scripts" / "afk-config.py"), "resolve", key],
                          cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=FORGE_TIMEOUT)
    return done.stdout.strip() if done.returncode == 0 else ""


def _base_branch(cwd: Path) -> str:
    """The repository's `git.base-branch` through `afk-config.py get`, as written (`auto` stays
    `auto`), or "" when the lookup fails."""
    try:
        done = subprocess.run([sys.executable, str(PLUGIN_ROOT / "scripts" / "afk-config.py"), "get",
                               "git.base-branch"], cwd=cwd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=FORGE_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _rationale_post(change: str, cwd: Path) -> dict:
    try:
        done = subprocess.run([sys.executable, str(LEDGER), "rationale-post", "--change", change],
                              cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=LEDGER_TIMEOUT)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": f"rationale-post gave no answer within {LEDGER_TIMEOUT} s"}
    answer = parse_answer(done.stdout) or {}
    if done.returncode or answer.get("ok") is not True:
        reason = answer.get("reason") or done.stderr.strip()[-300:] or f"exit {done.returncode}"
        return {**answer, "ok": False, "reason": reason}
    return answer


# ---- the diagnosis ---------------------------------------------------------

@dataclass
class Diagnosis:
    path: Path
    work_id: str
    ticket: str
    base: str
    branch: str
    symptom: str
    entries: list[tuple[str, str]]
    base_commit: str = ""

    def value(self, kind: str) -> str:
        """The first listed entry of `kind`, or ""."""
        return next((value for found, value in self.entries if found == kind), "")


def read_diagnosis(path) -> Diagnosis:
    path = Path(path)
    if not path.is_file():
        raise refuse(f"no diagnosis file at {path}")
    checked = check_diagnosis(path)
    if not checked.ok:
        raise refuse("the diagnosis check refuses the file: "
                     + "; ".join([f"missing {m}" for m in checked.missing] + checked.problems))
    found = sections(path.read_text(encoding="utf-8"))
    if "outside writes" not in found:
        raise refuse("the diagnosis has no `## Outside writes` part, so no write could be listed")

    def first(name: str) -> str:
        return next((line.strip() for line in found.get(name, []) if line.strip()), "")

    entries = []
    for line in found.get("outside writes", []):
        kind, _, value = line.strip().removeprefix("- ").partition(":")
        if value.strip():
            entries.append((kind.strip(), value.strip()))
    base, *rest = re.split(r"[@\s]+", first("base").replace("`", "").strip(), maxsplit=1)
    commit = re.search(r"\b[0-9a-fA-F]{7,40}\b", rest[0]) if rest else None
    symptom = re.sub(r"^[-*]\s+(\[[a-z]+\]\s*)?", "", first("symptom"))
    diagnosis = Diagnosis(path, first("work id"), first("ticket key"), base,
                          first("diagnosis branch").replace("`", ""), symptom, entries,
                          commit.group(0) if commit else "")
    diagnosis.ticket = diagnosis.ticket or diagnosis.value("ticket")
    return diagnosis


# ---- git -------------------------------------------------------------------

def _git(cwd: Path, *args: str, check: bool = True):
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise block(f"git {args[0]} gave no answer within {GIT_TIMEOUT} s") from None
    if check and done.returncode:
        raise block(f"git {' '.join(args)} failed: {_tail(done.stderr)}")
    return done


def _tail(text: str) -> str:
    return (text or "").strip()[-500:] or "no message"


def _on_branch(cwd: Path, d: Diagnosis) -> str:
    """HEAD's commit, when the checkout is on the Diagnosis branch."""
    current = _git(cwd, "symbolic-ref", "--quiet", "--short", "HEAD", check=False).stdout.strip()
    if current != d.branch:
        raise refuse(f"run this step in the diagnosis worktree on {d.branch}; "
                     f"this checkout is on {current or 'a detached HEAD'}")
    return _git(cwd, "rev-parse", "HEAD").stdout.strip()


def _remote(cwd: Path, branch: str) -> str:
    return _git(cwd, "config", f"branch.{branch}.remote", check=False).stdout.strip() or "origin"


def _branch_name(cwd: Path, ref: str) -> str:
    """`ref` without a leading `<remote>/` that names a remote-tracking branch."""
    for remote in _git(cwd, "remote", check=False).stdout.split():
        name = ref.removeprefix(f"{remote}/")
        if name != ref and _git(cwd, "rev-parse", "--verify", "--quiet",
                                f"refs/remotes/{ref}", check=False).returncode == 0:
            return name
    return ref


def _base_names(cwd: Path, base: str) -> set[str]:
    """`base` as written and without a leading `<remote>/`, fetched or not."""
    remotes = _git(cwd, "remote", check=False).stdout.split()
    return {base, *(base.removeprefix(f"{r}/") for r in remotes if base.startswith(f"{r}/"))}


def _check_entry(entry: str):
    """Refuse, before the write, an Outside writes entry the format would reject after it."""
    problem = entry_problem(entry, outside_write_kinds(load_format()))
    if problem:
        raise refuse(f"the step could not list its write: {problem}")


def _guard_target(tools: Tools, branch: str):
    try:
        hit = tools.protected(branch)
    except Exception as error:
        raise refuse(f"cannot tell whether {branch} is protected: {error}") from None
    if hit:
        raise refuse(f"{branch} is a protected branch; the ship script never pushes to one")


def _push(cwd: Path, tools: Tools, remote: str, target: str, head: str, *, contained: bool = False):
    """Plain `git push --set-upstream` of HEAD onto `target`, read back first and before each retry;
    a tip HEAD does not reach answers `moved`, unless `contained` is set and the tip holds HEAD."""
    ref = f"refs/heads/{target}"

    def write():
        done = _git(cwd, "push", "--set-upstream", remote, f"HEAD:{ref}", check=False)
        return {"error": True, "reason": _tail(done.stderr)} if done.returncode else {"ok": True}

    def read_back():
        seen = _git(cwd, "ls-remote", "--heads", remote, ref, check=False)
        if seen.returncode:
            return {"error": True, "reason": f"cannot read {remote}: {_tail(seen.stderr)}"}
        tip = (seen.stdout.split() or [""])[0]
        if not tip:
            return None
        if tip == head:
            return {"ok": True, "commit": head}
        known = _git(cwd, "cat-file", "-e", f"{tip}^{{commit}}", check=False).returncode == 0
        if not known and _git(cwd, "fetch", "--quiet", remote, ref, check=False).returncode:
            return {"error": True, "reason": f"cannot fetch {remote}/{target} to compare its tip"}
        if contained and _git(cwd, "merge-base", "--is-ancestor", head, tip, check=False).returncode == 0:
            return {"ok": True, "commit": head, "contained_in": tip}
        if _git(cwd, "merge-base", "--is-ancestor", tip, head, check=False).returncode == 0:
            return None
        return {"error": True, "moved": True, "tip": tip,
                "reason": f"{remote}/{target} is at {tip[:12]}, which {head[:12]} does not contain"}

    return retry_with_read_back(write, read_back, read_first=True, sleep=tools.sleep)


# ---- forge lookups ---------------------------------------------------------

def _number(link: str) -> str:
    match = re.search(r"(?:^|/)(\d+)/?(?:[?#].*)?$", (link or "").strip())
    return match.group(1) if match else ""


def _writable(answer: dict, what: str) -> dict:
    state = str(answer.get("state") or "").lower()
    if state in NOT_WRITABLE:
        raise block(f"the change {answer.get('url') or what} is {state}; reopen it or remove its "
                    "Outside writes entry by hand")
    return answer


def _open_or_none(answer):
    """A by-branch change-view answer: None when the forge confirms no open change
    (missing, or only a closed or merged one), else the answer as it came."""
    if isinstance(answer, dict) and answer.get("error") and answer.get("missing"):
        return None
    if not failed(answer) and str(answer.get("state") or "").lower() in NOT_WRITABLE:
        return None
    return answer


def _change_by_branch(forge, branch: str):
    """The open change for `branch`, or None when the forge confirms there is none."""
    answer = _open_or_none(forge.call("change-view", {"id": branch}))
    if answer is not None and failed(answer):
        raise block(f"the change lookup by branch {branch} failed, so no change opens (several "
                    f"changes on one branch end here too; pick one by hand): {_why(answer)}")
    return answer


def _change_by_number(forge, number: str) -> dict:
    answer = forge.call("change-view", {"id": number})
    if failed(answer):
        raise block(f"the change lookup by recorded number {number} failed: {_why(answer)}")
    return _writable(answer, number)


def _why(answer) -> str:
    if isinstance(answer, dict):
        return str(answer.get("reason") or answer)
    return repr(answer)


def _listed_change(d: Diagnosis) -> tuple[str, str]:
    """(link, number) of the listed change; refused when none is listed or its id is empty."""
    link = d.value("change")
    if not link:
        raise refuse("no change is listed in Outside writes: run the open step first")
    number = _number(link)
    if not number:
        raise refuse(f"the listed change link `{link}` carries an empty change id")
    return link, number


# ---- steps -----------------------------------------------------------------

def step_open(d: Diagnosis, tools: Tools, cwd: Path) -> dict:
    head = _on_branch(cwd, d)
    _guard_target(tools, d.branch)
    result, missing = {}, []
    if d.value("change"):
        link, number = _listed_change(d)
        result["change_step"] = "skipped"
    else:
        existing = _change_by_branch(tools.forge, d.branch)
        remote = _remote(cwd, d.branch)
        pushed = _push(cwd, tools, remote, d.branch, head)
        if not pushed.ok:
            raise block(f"the push of {d.branch} to {remote} did not take effect, never forced: "
                        f"{_why(pushed.answer) if pushed.answer else pushed.reason}")
        result["push"] = "found" if pushed.found else "pushed"
        if existing:
            link, result["change_step"] = str(existing.get("url") or ""), "found"
        else:
            assignee = tools.setting("mrAssignee")
            if not assignee:
                missing.append("mrAssignee")
            link, result["change_step"] = _create(d, tools, cwd, assignee)
        number = _number(link)
        if not number:
            raise block(f"the forge answered the change link `{link}` with an empty change id")
        append_outside_write(d.path, f"change: {link}")
    reasons = tools.post_reasons(number)
    if not reasons.get("ok"):
        raise block(f"the change {link} is open and listed; rationale-post did not finish: "
                    f"{_why(reasons)}", change=link, reasons=reasons)
    status = "skipped" if result["change_step"] == "skipped" else "done"
    return {"status": status, "change": link, **result, "reasons": reasons,
            **({"missing": missing} if missing else {})}


def _create(d: Diagnosis, tools: Tools, cwd: Path, assignee: str) -> tuple[str, str]:
    ref = d.ticket or d.work_id
    title = f"Fix {ref}: {d.symptom}" if d.symptom else f"Fix {ref}"
    payload = {"title": title[:72].rstrip(), "source": d.branch,
               "target": _branch_name(cwd, d.base),
               "body": f"Work id: `{d.work_id}`. Ticket: {d.ticket or 'none'}. "
                       "The proof follows as a comment on this change."}
    if assignee:
        payload["assignee"] = assignee

    def read_back():
        return _open_or_none(tools.forge.call("change-view", {"id": d.branch}))

    outcome = retry_with_read_back(lambda: tools.forge.call("change-create-draft", payload),
                                   read_back, key="id", sleep=tools.sleep)
    if not outcome.ok:
        raise block(f"the Draft change for {d.branch} did not open: {outcome.reason}")
    return str(outcome.answer.get("url") or ""), "found" if outcome.found else "opened"


def step_proof(d: Diagnosis, tools: Tools, cwd: Path, proof: dict, evidence_link: str) -> dict:
    marker = f"afk-evidence {d.work_id} {PROOF_STEP}"
    entry = f"evidence: {marker}"
    if listed(d.path, entry):
        return {"status": "skipped", "reason": f"`{entry}` is listed"}
    _check_entry(entry)
    texts = _proof_texts(proof)
    if d.ticket and not evidence_link:
        raise refuse(f"the diagnosis names ticket {d.ticket}: pass --evidence-link, the link to "
                     "its evidence comment")
    text = "\n\n".join([marker, *(f"### {kind}\n\n{texts[kind]}" for kind in PROOF_KINDS),
                        *([f"Ticket evidence: {evidence_link}"] if evidence_link else [])])
    if d.value("change"):
        link, number = _listed_change(d)
        _change_by_number(tools.forge, number)
    else:
        target = _branch_name(cwd, d.base)
        if not any(value.startswith(f"{target}@") for kind, value in d.entries if kind == "push"):
            raise refuse("nothing is shipped yet: run the open step, or land, first")
        found = _change_by_branch(tools.forge, target)
        if found is None:
            return {"status": "no-change", "reason": f"{target} has no open change; put the text "
                    "in the run report", "text": text}
        link, number = str(found.get("url") or ""), str(found.get("id") or "")
        if not number:
            raise refuse(f"the change found for {target} carries an empty change id")

    def read_back():
        notes = tools.forge.call("note-list", {"id": number})
        if failed(notes):
            return notes
        for note in notes.get("notes") or []:
            if marker in (line.strip() for line in str(note.get("body") or "").splitlines()):
                return note
        return None

    outcome = retry_with_read_back(
        lambda: tools.forge.call("change-comment", {"id": number, "text": text}),
        read_back, key="comment", read_first=True, sleep=tools.sleep)
    if not outcome.ok:
        raise block(f"the proof comment on {link} did not post: {outcome.reason}")
    append_outside_write(d.path, entry)
    return {"status": "done", "change": link, "comment": "found" if outcome.found else "posted",
            "url": str(outcome.answer.get("url") or "")}


def _proof_texts(proof: dict) -> dict:
    proof = dict(proof or {})
    unknown = sorted(set(proof) - set(PROOF_KINDS))
    if unknown:
        raise refuse(f"proof kinds {', '.join(unknown)} are not {' or '.join(PROOF_KINDS)}")
    texts = {}
    for kind in PROOF_KINDS:
        if kind not in proof:
            raise refuse(f"--proof {kind}=PATH is required")
        try:
            texts[kind] = Path(proof[kind]).read_text(encoding="utf-8").strip()
        except OSError as error:
            raise refuse(f"{kind} file {proof[kind]} cannot be read: {error}") from None
        if not texts[kind]:
            raise refuse(f"{kind} file {proof[kind]} is empty")
    return texts


def step_ready(d: Diagnosis, tools: Tools, cwd: Path) -> dict:
    link, number = _listed_change(d)
    if _change_by_number(tools.forge, number).get("draft") is False:
        return {"status": "skipped", "change": link,
                "reason": "the change is already ready; its reviewers are not read back"}
    code, answer, stderr = tools.forge.ci_wait(number)
    green, why = route_ci(code, answer, stderr)
    if not green:
        return {"status": "draft", "change": link, "reason": f"{why}; the change stays Draft"}

    def ready_back():
        view = tools.forge.call("change-view", {"id": number})
        return view if failed(view) or view.get("draft") is False else None

    ready = retry_with_read_back(lambda: tools.forge.call("change-ready", {"id": number}),
                                 ready_back, sleep=tools.sleep)
    if not ready.ok:
        raise block(f"CI is green but {link} was not marked ready: {ready.reason}", change=link)
    reviewer = tools.setting("mrReviewer")
    if not reviewer:
        return {"status": "done", "change": link, "reason": why, "missing": ["mrReviewer"]}
    added = retry_with_read_back(
        lambda: tools.forge.call("change-reviewers", {"id": number, "reviewers": reviewer}),
        None, sleep=tools.sleep)
    if not added.ok:
        raise block(f"{link} is ready, but reviewer {reviewer} was not added (no read-back, so no "
                    f"retry; add them by hand): {added.reason}", change=link)
    return {"status": "done", "change": link, "reason": why, "reviewer": reviewer}


def step_land(d: Diagnosis, tools: Tools, cwd: Path) -> dict:
    head = _on_branch(cwd, d)
    target = _branch_name(cwd, d.base)
    _guard_target(tools, target)
    try:
        base = tools.base_branch()
    except Exception as error:
        raise refuse(f"cannot tell the repository's base branch: {error}") from None
    if not base:
        raise refuse("cannot tell the repository's base branch (`git.base-branch`), so land "
                     "cannot rule it out")
    remote = _remote(cwd, target)
    if target in (_auto_base_names(cwd, remote) if base == "auto" else _base_names(cwd, base)):
        raise refuse(f"{target} is the repository's base branch; a fix for it ships through "
                     "open, never land")
    entry = f"push: {target}@{head}"
    if listed(d.path, entry):
        return {"status": "skipped", "reason": f"`{entry}` is listed"}
    _check_entry(entry)
    fetched = _git(cwd, "fetch", "--quiet", remote, f"refs/heads/{target}", check=False)
    if fetched.returncode:
        raise block(f"cannot fetch {target} from {remote}: {_tail(fetched.stderr)}")
    _carries_a_fix(cwd, d, head, _git(cwd, "rev-parse", "FETCH_HEAD").stdout.strip())
    pushed = _push(cwd, tools, remote, target, head, contained=True)
    if not pushed.ok:
        if isinstance(pushed.answer, dict) and pushed.answer.get("moved"):
            return {"status": "not-fast-forward", "tip": pushed.answer["tip"],
                    "reason": f"{pushed.answer['reason']}: not a fast-forward, nothing pushed"}
        raise block(f"the push onto {target} did not take effect, never forced: {pushed.reason}")
    append_outside_write(d.path, entry)
    return {"status": "done", "push": entry.removeprefix("push: "),
            "how": "found" if pushed.found else "pushed"}


def _auto_base_names(cwd: Path, remote: str) -> set[str]:
    """`auto` (CONFIG.md) widened for land: the remote's default branch (as protected-lookup.py
    `default_branch` reads it), main and master; refused when the remote names none of them."""
    prefix = f"refs/remotes/{remote}/"
    head = _git(cwd, "symbolic-ref", "--quiet", f"{prefix}HEAD", check=False).stdout.strip()
    found = {head.removeprefix(prefix)} if head.startswith(prefix) else set()
    found |= {name for name in ("main", "master") if _git(
        cwd, "rev-parse", "--verify", "--quiet", f"{prefix}{name}", check=False).returncode == 0}
    if not found:
        raise refuse(f"`git.base-branch` is `auto` and {remote} names no default branch, main or "
                     "master, so land cannot rule out the base branch")
    return found | {"main", "master"}


def _carries_a_fix(cwd: Path, d: Diagnosis, head: str, tip: str):
    """Refuse a land with no commit past the Base commit that the Diagnosis branch made: a commit,
    cherry-pick or revert in its reflog, or a rebase result the fetched `tip` does not hold."""
    if not d.base_commit:
        raise refuse("the diagnosis Base names no commit (write it as `{branch}@{commit id}`), so "
                     f"land cannot tell whether {d.branch} carries a fix commit")
    ahead = _git(cwd, "rev-list", f"{d.base_commit}..{head}", check=False)
    if ahead.returncode:
        raise refuse(f"the Base commit {d.base_commit} is not in this checkout, so land cannot "
                     f"tell whether {d.branch} carries a fix commit")
    commits = set(ahead.stdout.split())
    if not commits:
        raise refuse(f"{d.branch} carries no commit past the Base commit {d.base_commit}; "
                     "nothing to land")
    log = _git(cwd, "reflog", "show", "--format=%H %gs", f"refs/heads/{d.branch}", check=False).stdout
    made = set()
    for sha, _, subject in (line.partition(" ") for line in log.splitlines()):
        action = subject.partition(": ")[0]
        if action in MADE_HERE or ("rebase" in action and action.endswith("(finish)") and _git(
                cwd, "merge-base", "--is-ancestor", sha, tip, check=False).returncode == 1):
            made.add(sha)
    if not commits & made:
        raise refuse(f"none of the {len(commits)} commits past the Base commit {d.base_commit} "
                     f"was made on {d.branch}, so land would ship no fix")


def run_ship_step(step: str, diagnosis, *, proof: dict | None = None, evidence_link: str = "",
                  cwd=None, tools: Tools | None = None) -> dict:
    """Step name + diagnosis path in -> step result (`step`, `status`, details)."""
    cwd = Path(cwd or Path.cwd())
    try:
        if step not in STEPS:
            raise refuse(f"unknown step `{step}`; the steps are {', '.join(STEPS)}")
        if step != "proof" and (proof or evidence_link):
            raise refuse("--proof and --evidence-link belong to the proof step")
        d = read_diagnosis(diagnosis)
        bound = _bind(tools or Tools(), cwd)
        if step == "proof":
            result = step_proof(d, bound, cwd, proof or {}, evidence_link)
        else:
            result = {"open": step_open, "ready": step_ready, "land": step_land}[step](d, bound, cwd)
    except Stop as stop:
        result = {"status": stop.status, "reason": stop.reason, **stop.details}
    except Exception as error:  # a write may already have taken effect: never exit as refused
        result = {"status": "blocked", "reason": f"{type(error).__name__}: {error}; a write may "
                  "have taken effect, so re-run the step, which reads back first"}
    return {"step": step, **result}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=STEPS)
    parser.add_argument("diagnosis")
    parser.add_argument("--proof", action="append", default=[], metavar="P-n=PATH")
    parser.add_argument("--evidence-link", default="")
    args = parser.parse_args(argv)
    proof = {}
    for item in args.proof:
        kind, sep, path = item.partition("=")
        if not sep or not path:
            parser.error(f"--proof takes P-n=PATH, not `{item}`")
        proof[kind] = path
    result = run_ship_step(args.step, args.diagnosis, proof=proof, evidence_link=args.evidence_link)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return EXIT.get(result.get("status"), 2)


if __name__ == "__main__":
    sys.exit(main())

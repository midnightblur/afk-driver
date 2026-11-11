"""The other-provider adapter: 1 headless, read-only call of the other provider's CLI.

Command: `other_provider.py which|judge|attack --session claude|codex [--input DIR] [--log PATH]`.
Answers one JSON object. Exit 0 ok, 1 refused, 2 unreadable input.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from afkv2_config import Refusal, data_folder  # noqa: E402

PROVIDERS = ("claude", "codex")
EFFORT = "medium"
CLI_DEFAULT = "cli-default"
JUDGE_KEY = "judge_{provider}"
STATUS_SECONDS = 30
STATUS_COMMAND = {"claude": ["auth", "status"], "codex": ["login", "status"]}
CALL_SECONDS = 300
ATTEMPTS = 2
INPUT_ENTRIES = {"rows.json": "file", "evidence": "folder", "tests": "folder"}
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")
CHECKS = ("VC-2", "VC-4", "VC-6", "VC-7", "level", "flaky")
SCHEMA_CHECK = "verdict-schema"
ROW_FIELDS = ("row", "seen", "compare", "checks", "result")
CHECK_FIELDS = ("check", "result", "why")
RESULTS = ("pass", "fail")

_TEXT_LIST = {"type": "array", "items": {"type": "string"}}
_CHECK = {"type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS),
          "properties": {"check": {"type": "string", "enum": list(CHECKS)},
                         "result": {"type": "string", "enum": list(RESULTS)}, "why": {"type": "string"}}}

# The answer of 1 judge call: 1 entry per plan row, `seen` before `compare`.
ANSWER_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["rows"],
    "properties": {"rows": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS),
        "properties": {"row": {"type": "string"}, "seen": _TEXT_LIST, "compare": _TEXT_LIST,
                       "checks": {"type": "array", "items": _CHECK},
                       "result": {"type": "string", "enum": list(RESULTS)}}}}},
}

# The verdict of 1 row, as a caller stores it. An empty `seen` fails the row; `verdict-schema` names a broken answer.
VERDICT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["provider", "model", "effort", "seen", "compare", "checks", "result"],
    "properties": {
        "provider": {"type": "string", "enum": list(PROVIDERS)}, "model": {"type": "string"},
        "effort": {"type": "string"}, "seen": _TEXT_LIST, "compare": _TEXT_LIST,
        "checks": {"type": "array", "items": {**_CHECK, "properties": {
            **_CHECK["properties"], "check": {"type": "string", "enum": [*CHECKS, SCHEMA_CHECK]}}}},
        "result": {"type": "string", "enum": list(RESULTS)},
    },
}

JUDGE_PROMPT = """You are the judge of high-level test proofs. You see only this folder: `rows.json` (the plan rows; \
each row says what you should see), `evidence/` (the screenshots, answers and logs of the test runs) and `tests/` \
(the test files). Read every file. Change nothing.

For each row of `rows.json`, answer 1 entry of `rows`, with its fields in this order:
1. `row`: the row id.
2. `seen`: describe, in your own words, what you see in each evidence file of the row. Describe before you compare.
3. `compare`: compare what you saw with what the row says you should see.
4. `checks`: 1 entry per check below, each with `result` pass or fail and 1 sentence `why`:
   - VC-2 refactor: the test still passes after a change that keeps behavior.
   - VC-4 outcome: the test asserts on a result, not only "no error".
   - VC-6 no logic: the expected values are literals.
   - VC-7 clear failure: a failure shows expected, actual and input.
   - level: the test has the attributes of its level and no sign of no value. API: asserts status, body and \
effect; owns its data; covers error and permission paths; polls, never sleeps. UI end to end: asserts what the user \
sees; role or label locators; waiting assertions; isolated; a trace on failure. Acceptance: business language; a \
concrete outcome; each outcome bound to its own evidence. Signs of no value: a status-only assert, fixed sleeps, \
structural selectors, a screenshot nobody asserts, a test that depends on the test before.
   - flaky: no flaky sign: no fixed sleep, no dependence on order, time or shared state.
5. `result`: pass only when what you saw matches the row and every check passes; else fail.

Answer only the JSON object of the schema, with no other field.
"""


@dataclass
class Ran:
    exit: int | None
    stdout: str
    timed_out: bool


def run_cli(argv, *, stdin, cwd, timeout) -> Ran:
    try:
        done = subprocess.run(argv, input=(stdin or "").encode("utf-8"), cwd=cwd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return Ran(None, "", True)
    except OSError as error:
        return Ran(None, str(error), False)
    return Ran(done.returncode, done.stdout.decode("utf-8", "replace"), False)


# ---------------------------------------------------------------- which

def which(session_provider, *, lookup=shutil.which, runner=run_cli) -> dict:
    """The judge: the other provider if its CLI is on the path and signed in, else the own provider at the
    judge model the install record names. Raises `Refusal` `no-provider` when neither can run."""
    if session_provider not in PROVIDERS:
        raise Refusal("bad-input", f"the session provider must be one of {', '.join(PROVIDERS)}, not {session_provider!r}")
    other = next(name for name in PROVIDERS if name != session_provider)
    models = _judge_models()
    cli = lookup(other)
    if cli and _signed_in(other, cli, runner):
        return {"provider": other, "model": models.get(other) or CLI_DEFAULT, "effort": EFFORT, "cli": cli}
    own = lookup(session_provider)
    if own and models.get(session_provider):
        return {"provider": session_provider, "model": models[session_provider], "effort": EFFORT, "cli": own}
    raise Refusal("no-provider", f"{other} is not on the path or not signed in, and the install record names no "
                  f"`{JUDGE_KEY.format(provider=session_provider)}` model: run the judge step of /afkv2:setup")


def _signed_in(provider, cli, runner) -> bool:
    return runner([cli, *STATUS_COMMAND[provider]], stdin="", cwd=None, timeout=STATUS_SECONDS).exit == 0


def _judge_models() -> dict:
    try:
        path = data_folder() / "install.txt"
        lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    except (Refusal, OSError):
        lines = []
    record = dict(line.partition(" ")[::2] for line in lines)
    return {name: record[JUDGE_KEY.format(provider=name)].strip() for name in PROVIDERS
            if record.get(JUDGE_KEY.format(provider=name), "").strip()}


# ---------------------------------------------------------------- judge

def judge(input_folder, session_provider, *, lookup=shutil.which, runner=run_cli) -> dict:
    """1 judge call on a folder of plan rows, evidence and test files. Answers 1 verdict per row id."""
    folder = Path(input_folder).resolve()
    rows = _rows(folder)
    judge_cli = which(session_provider, lookup=lookup, runner=runner)
    images = sorted(str(path) for path in (folder / "evidence").rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)
    answer = _call(judge_cli, JUDGE_PROMPT, folder, ANSWER_SCHEMA, images, runner)
    given = {key: judge_cli[key] for key in ("provider", "model", "effort")}
    return {"ok": True, **given, "verdicts": _verdicts(rows, answer, given)}


def _rows(folder: Path) -> list[str]:
    if not folder.is_dir():
        raise Refusal("bad-input", f"no judge input folder at {folder}")
    extra = sorted(entry.name for entry in folder.iterdir() if entry.name not in INPUT_ENTRIES)
    if extra:
        raise Refusal("bad-input", f"the judge input holds only {', '.join(INPUT_ENTRIES)}; remove {', '.join(extra)}")
    for name, kind in INPUT_ENTRIES.items():
        path = folder / name
        if not (path.is_file() if kind == "file" else path.is_dir()):
            raise Refusal("bad-input", f"the judge input has no {kind} {name}")
    try:
        rows = json.loads((folder / "rows.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Refusal("bad-input", f"rows.json is not JSON: {error}") from None
    ids = [row.get("id") if isinstance(row, dict) else None for row in rows] if isinstance(rows, list) else [None]
    if not ids or not all(isinstance(item, str) and item for item in ids) or len(set(ids)) != len(ids):
        raise Refusal("bad-input", "rows.json must be a list of plan rows, each with a unique text `id`")
    return ids


def _command(judge_cli, folder: Path, schema_file: Path, images) -> list[str]:
    if judge_cli["provider"] == "codex":
        argv = [judge_cli["cli"], "exec", "-s", "read-only", "-C", str(folder), "--skip-git-repo-check", "--ephemeral",
                "--output-schema", str(schema_file), "-c", f'model_reasoning_effort="{judge_cli["effort"]}"']
        if judge_cli["model"] != CLI_DEFAULT:
            argv += ["-m", judge_cli["model"]]
        for image in images:
            argv += ["-i", image]
        return argv
    argv = [judge_cli["cli"], "-p", "--output-format", "json", "--json-schema", schema_file.read_text(encoding="utf-8"),
            "--tools", "Read,Glob,Grep", "--permission-mode", "dontAsk", "--strict-mcp-config",
            "--no-session-persistence", "--disable-slash-commands", "--effort", judge_cli["effort"]]
    if judge_cli["model"] != CLI_DEFAULT:
        argv += ["--model", judge_cli["model"]]
    return argv


def _call(judge_cli, prompt, folder: Path, schema, images, runner):
    """Run the CLI; a transport failure gets 1 retry, an answer never. Answers the object as (key, value) pairs
    in their order. Raises `Refusal` after the second transport failure."""
    for attempt in range(ATTEMPTS):
        try:
            return _call_once(judge_cli, prompt, folder, schema, images, runner)
        except Refusal:
            if attempt == ATTEMPTS - 1:
                raise


def _call_once(judge_cli, prompt, folder: Path, schema, images, runner):
    with tempfile.TemporaryDirectory(prefix="afkv2-judge-") as scratch:
        schema_file = Path(scratch) / "answer-schema.json"
        schema_file.write_text(json.dumps(schema), encoding="utf-8")
        ran = runner(_command(judge_cli, folder, schema_file, images), stdin=prompt, cwd=str(folder),
                     timeout=CALL_SECONDS)
    if ran.timed_out:
        raise Refusal("judge-timeout", f"{judge_cli['provider']} gave no answer in {CALL_SECONDS} s")
    answer = _answer(judge_cli["provider"], ran.stdout) if ran.exit == 0 else None
    if answer is None:
        raise Refusal("judge-unreadable", f"{judge_cli['provider']} exited {ran.exit} with no readable answer on stdout")
    return answer


def _pairs(text):
    try:
        return json.loads(text, object_pairs_hook=list)
    except (TypeError, ValueError):
        return None


def _is_object(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, tuple) and len(item) == 2 for item in value)


def _answer(provider, stdout):
    """The answer object as a list of (key, value) pairs, or None when stdout holds none."""
    parsed = _pairs(stdout.strip())
    if provider == "claude" and _is_object(parsed):
        envelope = dict(parsed)
        if _is_object(envelope.get("structured_output")):
            return envelope["structured_output"]
        parsed = _pairs(envelope["result"]) if isinstance(envelope.get("result"), str) else None
    return parsed if _is_object(parsed) else None


def _verdicts(row_ids, answer, given) -> dict:
    top = dict(answer)
    problems = [f"field `{key}` is outside the schema" for key, _ in answer if key != "rows"]
    entries = top.get("rows") if isinstance(top.get("rows"), list) else []
    if not isinstance(top.get("rows"), list):
        problems.append("the answer has no `rows` list")
    by_row = {}
    for entry in entries:
        row = dict(entry).get("row") if _is_object(entry) else None
        if isinstance(row, str):
            by_row.setdefault(row, []).append(entry)
    return {row: _verdict(by_row.get(row, []), problems, given) for row in row_ids}


def _verdict(entries, top_problems, given) -> dict:
    problems = list(top_problems)
    pairs = entries[0] if entries else []
    keys, fields = [key for key, _ in pairs], dict(pairs)
    if not entries:
        problems.append("the judge gave no verdict for this row")
    else:
        if len(entries) > 1:
            problems.append("the judge gave more than 1 verdict for this row")
        problems += [f"field `{key}` is outside the schema" for key in keys if key not in ROW_FIELDS]
        problems += [f"field `{key}` is missing" for key in ROW_FIELDS if key not in fields]
    seen, compare = _texts(fields.get("seen")), _texts(fields.get("compare"))
    if entries and not seen:
        problems.append("`seen` is empty: the judge must describe what it sees")
    if "seen" in keys and "compare" in keys and keys.index("compare") < keys.index("seen"):
        problems.append("`compare` comes before `seen`: the judge must describe before it compares")
    raw_checks = fields.get("checks") if isinstance(fields.get("checks"), list) else []
    checks = [check for check in map(_check, raw_checks) if check]
    if len(checks) != len(raw_checks):
        problems.append("a check breaks the schema `{check, result, why}`")
    named = {check["check"] for check in checks}
    if entries:
        problems += [f"check {name} is missing" for name in CHECKS if name not in named]
        if fields.get("result") not in RESULTS:
            problems.append("`result` is not pass or fail")
    checks += [{"check": SCHEMA_CHECK, "result": "fail", "why": problem} for problem in problems]
    passed = fields.get("result") == "pass" and all(check["result"] == "pass" for check in checks)
    return {**given, "seen": seen, "compare": compare, "checks": checks, "result": "pass" if passed else "fail"}


def _texts(value) -> list[str]:
    return [item for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []


def _check(value):
    if not _is_object(value) or sorted(key for key, _ in value) != sorted(CHECK_FIELDS):
        return None
    fields = dict(value)
    if fields["check"] not in CHECKS or fields["result"] not in RESULTS or not isinstance(fields["why"], str):
        return None
    return {key: fields[key] for key in CHECK_FIELDS}

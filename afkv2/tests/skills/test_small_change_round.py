"""Acceptance: an agent that follows step 4 of /afkv2:small-change as written gets the developer's go on the page
that step 1 gave it.

The test plays the agent and the developer. It takes the commands of step 4 from SKILL.md, puts in the values that
`start` of step 1 answered, and runs them through the real scripts in a scratch repository. No page host runs in a
test: `present` runs with `--no-show`, and the test writes the developer's send to `raw_file`, as `wait` does. Then
it runs `go` of step 5. Each command and its answer goes to `$AFKV2_EVIDENCE`, else to the test folder.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

AFKV2 = Path(__file__).resolve().parents[2]
SKILL = AFKV2 / "skills" / "small-change"
SKILL_MD = SKILL / "SKILL.md"
STEP = re.compile(r"^ *```sh step=([\w-]+)\n *(.*?)\n *```", re.S | re.M)
VERB = re.compile(r'\.py" (\w[\w-]*)')
GO_CARD = "i-go"
SEND = "[round R-1]\ni-go sign\n"


def step_4():
    text = SKILL_MD.read_text(encoding="utf-8")
    start = text.index("\n4. **")
    return text[start:text.index("\n5. **", start)]


def run(argv, cwd, stdin=None):
    done = subprocess.run(argv, cwd=cwd, input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=300)
    try:
        answer = json.loads(done.stdout)
    except ValueError:
        answer = {"stdout": done.stdout, "stderr": done.stderr}
    return done.returncode, answer


def repository(root):
    root.mkdir()
    for args in (["init", "-q"], ["add", "."], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed"]):
        if args[0] == "add":
            (root / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, timeout=60)
    return root


def round_input(path):
    """The cards of the table of step 4, for an enhancement: the picture, the fix, the test plan and the go."""
    def card(id_, kind, title, words):
        return {"id": id_, "kind": kind, "title": title,
                "body": {"type": "text", "id": f"{id_}-text", "props": {"text": words}}}
    path.write_text(json.dumps({
        "short_title": "Value from 1 to 2",
        "banner": {"settled": [], "unlocks": [], "parked": []},
        "items": [card("i-picture", "info", "Now against proposed", "Now VALUE is 1. Proposed: 2. Changed: VALUE."),
                  card("i-fix", "info", "The fix", "Set VALUE to 2 in app.py."),
                  card("i-tests", "info", "The test plan", "acceptance: the check reads VALUE 2. It is the proof."),
                  card(GO_CARD, "signoff", "The go", "Go: set VALUE to 2, proven by the acceptance check.")]}),
        encoding="utf-8")
    return path


def test_an_agent_that_follows_step_4_gets_the_go_on_the_page_of_step_1(tmp_path):
    evidence = Path(os.environ.get("AFKV2_EVIDENCE") or tmp_path / "evidence")
    evidence.mkdir(parents=True, exist_ok=True)
    commands = [line.strip() for _, line in STEP.findall(step_4())]
    (evidence / "step-4-commands.txt").write_text("\n".join(commands) + "\n", encoding="utf-8")
    verbs = [match.group(1) if (match := VERB.search(line)) else line for line in commands]
    assert verbs == ["build", "present", "wait", "ingest"], (
        f"expected step 4 to show the page commands build, present, wait, ingest in that order; actual: {verbs}; "
        f"input: the command blocks of step 4 of {SKILL_MD}, in {evidence / 'step-4-commands.txt'}")

    repo = repository(tmp_path / "repo")
    code, started = run([sys.executable, str(SKILL / "scripts" / "small_lane.py"), "start"], repo,
                        json.dumps({"kind": "enhancement", "why": "1 file"}))
    assert code == 0 and started.get("ok"), f"expected start of step 1 to answer ok; actual: exit {code}, {started}"
    values = {"<python>": Path(sys.executable).as_posix(), "<this skill's folder>": SKILL.as_posix(),
              "<doc>": started["doc"], "<session>": started["session"], "<raw file>": started["raw_file"],
              "<round input>": round_input(tmp_path / "round.json").as_posix()}

    runs = []
    for line, verb in zip(commands, verbs):
        for placeholder, value in values.items():
            line = line.replace(placeholder, value)
        if verb == "wait":
            Path(started["raw_file"]).write_text(SEND, encoding="utf-8")
            runs.append({"command": line, "played by the test": f"wrote the developer's send {SEND!r} to raw_file"})
            continue
        if verb == "present":
            line = line.replace(" present ", " present --no-show ")
        code, answer = run(shlex.split(line), repo)
        runs.append({"command": line, "exit": code, "answer": answer})
        (evidence / "runs.json").write_text(json.dumps(runs, indent=1), encoding="utf-8")
        assert code == 0 and answer.get("ok"), f"expected {verb} to answer ok; actual: exit {code}, {answer}; input: {line}"

    pages = sorted(path.name for path in Path(started["doc"]).parent.glob("*.json"))
    page = json.loads(Path(started["doc"]).read_text(encoding="utf-8"))
    (evidence / "page.json").write_text(json.dumps(page, indent=1), encoding="utf-8")
    assert pages == [f"small-change-{started['session']}.json"], (
        f"expected 1 page, the doc of step 1; actual: {pages}; evidence: {evidence / 'page.json'}")
    assert page["session"]["skill"] == "small-change", (
        f"expected the page writer small-change; actual: {page['session']['skill']!r}; evidence: {evidence / 'page.json'}")

    code, go = run([sys.executable, str(SKILL / "scripts" / "small_lane.py"), "go"], repo,
                   json.dumps({"doc": started["doc"], "card": GO_CARD, "test_plan": "acceptance: the check reads 2"}))
    (evidence / "go.json").write_text(json.dumps(go, indent=1), encoding="utf-8")
    assert code == 0 and go.get("ok") and go["go"]["card"] == GO_CARD, (
        f"expected go of step 5 to answer ok with the card {GO_CARD}; actual: exit {code}, {go}; "
        f"evidence: {evidence / 'go.json'}")

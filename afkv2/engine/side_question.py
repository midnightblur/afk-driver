"""Answer one side question from the page in the agent's own terminal, like the CLI `/btw`.

    side_question.py ask --question "<text>" [--harness claude|codex] [--pane <herdr pane id>]

The agent session runs in a herdr pane: `HERDR_PANE_ID` names it, `HERDR_BIN_PATH` (else `herdr` on
PATH) runs herdr. A command the agent starts inherits both. `ask` types the harness's side-question
command into that pane, reads the pane until the answer is complete, and closes the overlay.

    Claude  `/btw <question>`; the overlay ends with a footer line `... to browse ... Esc to close`.
    Codex   `/side <question>`; the answer is not read until a live check defines its markers.

Esc goes to the pane only while the footer is visible: Esc at a working prompt interrupts the agent.
Answer: `{"question", "status", "answer"}`. Status:
    answered     `answer` holds the text of the overlay
    busy         an overlay was already open; nothing was typed
    timeout      no complete answer within 90 s; no Esc was sent
    not-read     typed, but this harness's answer is not read (Codex)
    failed       herdr refused a command
    unanswered   no herdr pane or no known harness: the agent answers the question in its session
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass

TIMEOUT_S = 90
INTERVAL_S = 1.5
READ_LINES = "400"
COMMAND_TIMEOUT_S = 15


@dataclass(frozen=True)
class Harness:
    command: str
    footer: re.Pattern | None  # None: the answer of this harness is not read


HARNESSES = {
    "claude": Harness("/btw", re.compile(r"to browse\b.*\bEsc to close")),
    "codex": Harness("/side", None),
}

TEXTS = {
    "busy": "The terminal is busy with another side question. Ask again.",
    "timeout": f"No answer within {TIMEOUT_S} s; see the terminal.",
    "not-read": "Asked in the Codex side chat. Read the answer in the terminal.",
    "unanswered": "Not answered here: no terminal pane to ask in. The agent answers it in the session.",
}
BLOCK_START = re.compile(r"^(?:[-*+•]\s|\d+[.)]\s|#|\||>|```)")


def detect_harness(env) -> str | None:
    if env.get("CLAUDECODE"):
        return "claude"
    if env.get("CODEX_THREAD_ID"):
        return "codex"
    return None


def herdr_binary(env) -> str | None:
    named = env.get("HERDR_BIN_PATH")
    if named and os.path.isfile(named):
        return named
    return shutil.which("herdr")


def run_herdr(argv: list[str]) -> tuple[int, str]:
    """The one place that runs herdr: `(exit code, stdout)`."""
    try:
        done = subprocess.run(argv, capture_output=True, timeout=COMMAND_TIMEOUT_S, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as problem:
        return 1, str(problem)
    return done.returncode, done.stdout.decode("utf-8", "replace")


def one_line(question: str) -> str:
    """A newline would submit the prompt early: the question goes as one line."""
    return " ".join(question.split())


def _question_end(lines: list[str], start: int, sent: str) -> int | None:
    """The index after the question line(s) at `start`, when they hold `sent`; a long question wraps."""
    if not lines[start].strip().startswith(sent.split(" ", 1)[0] + " "):
        return None
    joined = ""
    for end in range(start, len(lines)):
        joined = one_line(f"{joined} {lines[end]}")
        if joined == sent:
            return end + 1
        if len(joined) >= len(sent):
            return None
    return None


def extract_answer(screen: str, sent: str, footer: re.Pattern) -> str | None:
    """The answer between the last question line equal to `sent` and the footer after it, or None."""
    lines = screen.replace("\r\n", "\n").split("\n")
    footers = [i for i, line in enumerate(lines) if footer.search(line)]
    if not footers:
        return None
    last = footers[-1]
    for start in range(last - 1, -1, -1):
        end = _question_end(lines, start, sent)
        if end is not None:
            text = paragraphs(lines[end:last])
            return text or None
    return None


def paragraphs(lines: list[str]) -> str:
    """De-indent, keep blank lines, and join a hard-wrapped line to the line before it (best effort):
    a line that starts a list item, a heading, a quote, a table row or a code fence starts a new line."""
    body = textwrap.dedent("\n".join(line.rstrip() for line in lines)).split("\n")
    out: list[str] = []
    fenced = False
    for line in body:
        stripped = line.strip()
        if stripped.startswith("```"):
            fenced = not fenced
            out.append(line)
            continue
        joins = (not fenced and stripped and out and out[-1].strip() and not out[-1].strip().startswith("```")
                 and not BLOCK_START.match(stripped))
        if joins:
            out[-1] = f"{out[-1]} {stripped}"
        else:
            out.append(line)
    return "\n".join(out).strip("\n")


class Pane:
    def __init__(self, binary: str, pane: str, run=None):
        self.binary, self.pane = binary, pane
        self.run = run or run_herdr

    def read(self, source: str) -> str | None:
        code, out = self.run([self.binary, "pane", "read", self.pane, "--source", source, "--lines", READ_LINES])
        return out if code == 0 else None

    def send_text(self, text: str) -> bool:
        return self.run([self.binary, "pane", "send-text", self.pane, text])[0] == 0

    def send_keys(self, *keys: str) -> bool:
        return self.run([self.binary, "pane", "send-keys", self.pane, *keys])[0] == 0


def _result(question: str, status: str, answer: str | None = None) -> dict:
    return {"question": question, "status": status, "answer": answer if answer is not None else TEXTS[status]}


def _footer_visible(pane: Pane, footer: re.Pattern) -> bool:
    screen = pane.read("visible") or ""
    return any(footer.search(line) for line in screen.split("\n"))


def ask(question: str, env=None, harness: str | None = None, run=None, sleep=time.sleep,
        clock=time.monotonic, timeout_s: float = TIMEOUT_S) -> dict:
    env = os.environ if env is None else env
    harness = harness or detect_harness(env)
    pane_id, binary = env.get("HERDR_PANE_ID"), herdr_binary(env)
    if harness not in HARNESSES or not pane_id or not binary:
        return _result(question, "unanswered")
    spec, pane = HARNESSES[harness], Pane(binary, pane_id, run)
    sent = one_line(f"{spec.command} {question}")
    if spec.footer is not None:
        screen = pane.read("visible")
        if screen is None:
            return _result(question, "failed", "The terminal could not be read. Ask again.")
        if any(spec.footer.search(line) for line in screen.split("\n")):
            return _result(question, "busy")
    if not (pane.send_text(sent) and pane.send_keys("enter")):
        return _result(question, "failed", "The terminal did not take the question. Ask again.")
    if spec.footer is None:
        return _result(question, "not-read")
    deadline, last = clock() + timeout_s, None
    while clock() < deadline:
        sleep(INTERVAL_S)
        if not _footer_visible(pane, spec.footer):
            last = None
            continue
        text = extract_answer(pane.read("recent") or "", sent, spec.footer)
        if text and text == last:
            if _footer_visible(pane, spec.footer):
                pane.send_keys("esc")
            return _result(question, "answered", text)
        last = text
    return _result(question, "timeout")


def reply_markdown(results: list[dict]) -> str:
    """One reply for the page: each question in bold, then its answer."""
    return "\n\n".join(f"**btw:** {one_line(r['question'])}\n\n{r['answer']}" for r in results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="side_question.py")
    verbs = parser.add_subparsers(dest="verb", required=True)
    asking = verbs.add_parser("ask")
    asking.add_argument("--question", required=True)
    asking.add_argument("--harness", choices=sorted(HARNESSES))
    asking.add_argument("--pane", help="the herdr pane of the agent; default HERDR_PANE_ID")
    args = parser.parse_args(argv)
    env = {**os.environ, **({"HERDR_PANE_ID": args.pane} if args.pane else {})}
    print(json.dumps(ask(args.question, env=env, harness=args.harness)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

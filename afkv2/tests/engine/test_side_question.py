"""Side questions from the page: asked in the agent's herdr pane, answered on the page, kept out of the round.

herdr runs in-process only: each test replaces `side_question.run_herdr` with a fake pane.
"""

import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
for folder in (PLUGIN / "engine", PLUGIN / "skills" / "use-lavish" / "scripts"):
    sys.path.insert(0, str(folder))

import page_round  # noqa: E402
import side_question  # noqa: E402
from grill_common import Refusal  # noqa: E402

FOOTER = "  ⇧←/→ to browse · c to copy · f to fork · x to clear history · Esc to close"
PROMPT_SCREEN = "> \n  ? for shortcuts"
ANSWER = ("You are grilling PROJ-123, the export feature. The round asks about the file format and the order "
          "of the columns in the export.\n\n- CSV is the default.\n- Excel waits on a later ticket.")


def overlay(question="which ticket are we grilling?"):
    """The /btw overlay as `herdr pane read` shows it: earlier questions, the newest, the answer, the footer."""
    return "\n".join([
        "  /btw what does round 1 settle?",
        f"  /btw {question}",
        "  You are grilling PROJ-123, the export feature. The round asks",
        "  about the file format and the order of the columns in the",
        "  export.",
        "",
        "  - CSV is the default.",
        "  - Excel waits on a",
        "    later ticket.",
        "",
        FOOTER,
    ])


class FakePane:
    """A pane that shows the overlay `delay` reads after Enter; `screen` replaces the overlay when given."""

    def __init__(self, before=PROMPT_SCREEN, delay=1, screen=None, refuse=()):
        self.calls, self.before, self.delay, self.screen, self.refuse = [], before, delay, screen, refuse
        self.entered, self.reads, self.closed = False, 0, False

    def __call__(self, argv):
        verb = argv[2]
        self.calls.append(argv[2:])
        if verb in self.refuse:
            return 1, ""
        if verb == "send-keys" and argv[4:] == ["enter"]:
            self.entered = True
        if verb == "send-keys" and argv[4:] == ["esc"]:
            self.closed = True
        if verb != "read":
            return 0, ""
        if not self.entered or self.closed:
            return 0, self.before
        self.reads += 1
        if self.reads < self.delay:
            return 0, self.before
        return 0, self.screen if self.screen is not None else overlay(self.sent()[len("/btw "):])

    def sent(self):
        return next(call[2] for call in self.calls if call[0] == "send-text")

    def verbs(self):
        return [f"{call[0]} {call[1]}" if call[0] != "read" else f"read {call[3]}" for call in self.calls]


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def herdr_env(tmp_path):
    binary = tmp_path / "herdr-path.txt"
    binary.write_text("", "utf-8")
    return {"HERDR_PANE_ID": "w1:p1", "HERDR_BIN_PATH": str(binary), "CLAUDECODE": "1"}


def ask(question, env, pane, clock=None):
    clock = clock or Clock()
    return side_question.ask(question, env=env, run=pane, sleep=clock.sleep, clock=clock)


def test_the_answer_is_the_text_between_the_question_line_and_the_footer():
    footer = side_question.HARNESSES["claude"].footer
    assert side_question.extract_answer(overlay(), "/btw which ticket are we grilling?", footer) == ANSWER
    assert side_question.extract_answer(overlay(), "/btw another question?", footer) is None
    assert side_question.extract_answer(overlay().replace(FOOTER, ""), "/btw which ticket are we grilling?",
                                        footer) is None


def test_a_wrapped_question_line_still_matches():
    long = "which ticket are we grilling, and which rounds are still open on the page today?"
    screen = overlay(long).replace(f"  /btw {long}", "  /btw which ticket are we grilling, and which rounds\n"
                                                    "  are still open on the page today?")
    footer = side_question.HARNESSES["claude"].footer
    assert side_question.extract_answer(screen, f"/btw {long}", footer) == ANSWER


def test_a_question_wrapped_inside_a_word_still_matches():
    long = "which ticket are we grilling, and which rounds are still open on the page today?"
    screen = overlay(long).replace(f"  /btw {long}", "  /btw which ticket are we grilling, and which rou\n"
                                                    "  nds are still open on the page today?")
    footer = side_question.HARNESSES["claude"].footer
    assert side_question.extract_answer(screen, f"/btw {long}", footer) == ANSWER


def test_a_code_fence_keeps_its_lines():
    lines = ["  Run this:", "  ```", "  a", "  b", "  ```"]
    assert side_question.paragraphs(lines) == "Run this:\n```\na\nb\n```"


def test_ask_types_the_question_reads_the_answer_and_closes_the_overlay(herdr_env):
    pane = FakePane()
    result = ask("which ticket are we\ngrilling?", herdr_env, pane)
    assert result == {"question": "which ticket are we\ngrilling?", "status": "answered", "answer": ANSWER}
    assert pane.sent() == "/btw which ticket are we grilling?"
    assert pane.verbs()[:3] == ["read visible", "send-text w1:p1", "send-keys w1:p1"]
    assert pane.calls[2] == ["send-keys", "w1:p1", "enter"] and pane.calls[-1] == ["send-keys", "w1:p1", "esc"]
    assert pane.calls[0][-2:] == ["--lines", side_question.READ_LINES]


def test_ask_waits_until_the_answer_stops_changing(herdr_env):
    pane = FakePane(delay=3)
    clock = Clock()
    assert ask("q?", herdr_env, pane, clock)["status"] == "answered"
    assert pane.verbs().count("read recent") == 2


def test_ask_refuses_to_type_while_an_overlay_is_open(herdr_env):
    pane = FakePane(before=overlay())
    result = ask("which ticket?", herdr_env, pane)
    assert result["status"] == "busy" and "Ask again" in result["answer"]
    assert pane.verbs() == ["read visible"]


def test_no_answer_within_90_seconds_sends_no_esc(herdr_env):
    pane, clock = FakePane(delay=10**6), Clock()
    result = ask("q?", herdr_env, pane, clock)
    assert result == {"question": "q?", "status": "timeout", "answer": "No answer within 90 s; see the terminal."}
    assert clock.now >= 90 and ["send-keys", "w1:p1", "esc"] not in pane.calls


def test_an_overlay_that_closes_before_the_answer_is_read_sends_no_esc(herdr_env):
    pane, clock = FakePane(screen=PROMPT_SCREEN), Clock()
    assert ask("q?", herdr_env, pane, clock)["status"] == "timeout"
    assert ["send-keys", "w1:p1", "esc"] not in pane.calls


def test_without_herdr_the_question_returns_unanswered(herdr_env):
    pane = FakePane()
    for missing in ("HERDR_PANE_ID", "CLAUDECODE"):
        env = {k: v for k, v in herdr_env.items() if k != missing}
        assert ask("q?", env, pane)["status"] == "unanswered"
    assert pane.calls == []


def test_codex_types_side_and_does_not_read_the_answer(herdr_env):
    env = {**{k: v for k, v in herdr_env.items() if k != "CLAUDECODE"}, "CODEX_THREAD_ID": "t-1"}
    pane = FakePane()
    result = ask("q?", env, pane)
    assert result["status"] == "not-read" and pane.sent() == "/side q?"
    assert [call[0] for call in pane.calls] == ["send-text", "send-keys"]


def test_a_refused_herdr_command_fails_the_question(herdr_env):
    assert ask("q?", herdr_env, FakePane(refuse=("send-text",)))["status"] == "failed"
    assert ask("q?", herdr_env, FakePane(refuse=("read",)))["status"] == "failed"


def test_the_cli_answers_one_json_object(herdr_env, monkeypatch, capsys):
    pane = FakePane()
    monkeypatch.setattr(side_question, "run_herdr", pane)
    monkeypatch.setattr(side_question, "INTERVAL_S", 0)
    for key, value in herdr_env.items():
        monkeypatch.setenv(key, value)
    assert side_question.main(["ask", "--question", "q?", "--harness", "claude", "--pane", "w9:p9"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "answered"
    assert pane.calls[0][1] == "w9:p9"


# --- the wait: a send of side questions only never wakes the agent


class FakeEngine:
    def __init__(self, polls):
        self.polls, self.calls, self.replies = list(polls), [], []

    def __call__(self, verb, doc, *args, timeout=None):
        self.calls.append([verb, *args])
        if "--reply-file" in args:
            self.replies.append(Path(args[args.index("--reply-file") + 1]).read_text("utf-8"))
        if verb == "reply":
            return {"ok": True}
        return self.polls.pop(0)


def round_answer(btw=(), round_prompts=1):
    raw = "[round R-1]\ni-a accept" if round_prompts else "[round R-1]"
    return {"ok": True, "raw": raw, "prompts": [{"prompt": "i-a accept"}], "btw": list(btw),
            "round_prompts": round_prompts, "session_ended": False}


@pytest.fixture
def pane(herdr_env, monkeypatch):
    fake = FakePane()
    monkeypatch.setattr(side_question, "run_herdr", fake)
    monkeypatch.setattr(side_question, "INTERVAL_S", 0)
    for key in ("HERDR_PANE_ID", "HERDR_BIN_PATH", "CLAUDECODE", "CODEX_THREAD_ID"):
        monkeypatch.delenv(key, raising=False)
    for key, value in herdr_env.items():
        monkeypatch.setenv(key, value)
    return fake


def test_the_wait_answers_a_side_question_on_the_page_and_waits_for_the_round(pane, tmp_path, monkeypatch):
    engine = FakeEngine([round_answer(["which ticket?"], 0), round_answer()])
    monkeypatch.setattr(page_round, "_engine", engine)
    raw_file = tmp_path / "raw.txt"
    answer = page_round.wait("doc.json", str(raw_file))
    assert raw_file.read_text("utf-8") == "[round R-1]\ni-a accept" and answer["btw"] == []
    assert [call[0] for call in engine.calls] == ["poll", "poll"] and engine.calls[1][1] == "--reply-file"
    assert engine.replies == [f"**btw:** which ticket?\n\n{ANSWER}"]
    assert not page_round.reply_file_of(raw_file).exists()


def test_a_side_question_sent_with_the_round_is_answered_before_the_round_returns(pane, tmp_path, monkeypatch):
    engine = FakeEngine([round_answer(["which ticket?"], 2)])
    monkeypatch.setattr(page_round, "_engine", engine)
    answer = page_round.wait("doc.json", str(tmp_path / "raw.txt"))
    assert [call[0] for call in engine.calls] == ["poll", "reply"] and answer["btw"] == []
    assert answer["raw_file"] == str(tmp_path / "raw.txt") and len(engine.replies) == 1


def test_without_herdr_the_wait_hands_the_side_question_to_the_agent(pane, tmp_path, monkeypatch):
    monkeypatch.delenv("HERDR_PANE_ID")
    engine = FakeEngine([round_answer(["which ticket?"], 0)])
    monkeypatch.setattr(page_round, "_engine", engine)
    answer = page_round.wait("doc.json", str(tmp_path / "raw.txt"))
    assert answer == {"ok": True, "raw_file": None, "btw": ["which ticket?"]}
    assert engine.calls == [["poll"]] and not (tmp_path / "raw.txt").exists() and pane.calls == []


def test_a_refused_page_reply_hands_every_question_to_the_agent(pane, tmp_path, monkeypatch):
    engine = FakeEngine([round_answer(["which ticket?"], 1)])

    def refusing(verb, doc, *args, timeout=None):
        if verb == "reply":
            raise Refusal("host-error", "gone")
        return engine(verb, doc, *args)

    monkeypatch.setattr(page_round, "_engine", refusing)
    answer = page_round.wait("doc.json", str(tmp_path / "raw.txt"))
    assert answer["btw"] == ["which ticket?"] and (tmp_path / "raw.txt").is_file()


def test_page_round_reply_shows_a_reply_file(tmp_path, monkeypatch):
    engine = FakeEngine([])
    monkeypatch.setattr(page_round, "_engine", engine)
    reply = tmp_path / "reply.md"
    reply.write_text("An answer.", "utf-8")
    assert page_round.main(["reply", "--doc", "doc.json", "--reply-file", str(reply)]) == {"ok": True}
    assert engine.replies == ["An answer."]
    with pytest.raises(Refusal):
        page_round.main(["reply", "--doc", "doc.json", "--reply-file", str(tmp_path / "none.md")])

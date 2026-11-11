"""The other-provider adapter, with an in-process fake CLI: no real provider runs here."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import other_provider as op  # noqa: E402

CHECKS = ["VC-2", "VC-4", "VC-6", "VC-7", "level", "flaky"]


class FakeCli:
    """Answers each call from a queue and records argv, stdin and cwd. A queued item is
    (exit, stdout) or "timeout"."""

    def __init__(self, *answers, signed_in=("claude", "codex"), on_path=("claude", "codex")):
        self.answers = list(answers)
        self.calls = []
        self.signed_in = set(signed_in)
        self.on_path = set(on_path)
        self.stderr = ""

    def lookup(self, name):
        return f"/bin/{name}" if name in self.on_path else None

    def run(self, argv, *, stdin, cwd, timeout):
        name = Path(argv[0]).name
        if argv[1:] in (["auth", "status"], ["login", "status"]):
            return op.Ran(0 if name in self.signed_in else 1, "", False)
        self.calls.append({"argv": argv, "stdin": stdin, "cwd": cwd, "timeout": timeout})
        answer = self.answers.pop(0)
        if answer == "timeout":
            return op.Ran(None, "", True)
        return op.Ran(answer[0], answer[1], False, self.stderr)


def record(lines):
    folder = Path(os.environ["LOCALAPPDATA"]) / "afkv2"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "install.txt").write_text("".join(f"{k} {v}\n" for k, v in lines.items()), encoding="utf-8")


# ---------------------------------------------------------------- which


def test_which_picks_the_other_provider_when_its_cli_is_on_the_path_and_signed_in():
    fake = FakeCli()
    assert op.which("claude", lookup=fake.lookup, runner=fake.run) == {
        "provider": "codex", "model": "cli-default", "effort": "medium", "cli": "/bin/codex"}
    assert op.which("codex", lookup=fake.lookup, runner=fake.run)["provider"] == "claude"


def test_which_gives_the_other_provider_the_judge_model_the_install_record_names():
    record({"judge_codex": "gpt-9"})
    fake = FakeCli()
    assert op.which("claude", lookup=fake.lookup, runner=fake.run)["model"] == "gpt-9"


def test_which_falls_back_to_the_own_provider_at_the_recorded_judge_model_when_the_other_is_signed_out():
    record({"judge_claude": "opus-x"})
    fake = FakeCli(signed_in=("claude",))
    assert op.which("claude", lookup=fake.lookup, runner=fake.run) == {
        "provider": "claude", "model": "opus-x", "effort": "medium", "cli": "/bin/claude"}


def test_which_falls_back_when_the_other_cli_is_not_on_the_path():
    record({"judge_codex": "gpt-9"})
    fake = FakeCli(on_path=("codex",))
    assert op.which("codex", lookup=fake.lookup, runner=fake.run)["provider"] == "codex"


def test_which_refuses_no_provider_when_the_record_names_no_own_judge_model():
    fake = FakeCli(on_path=("claude",))
    with pytest.raises(op.Refusal) as refused:
        op.which("claude", lookup=fake.lookup, runner=fake.run)
    assert refused.value.code == "no-provider"


def test_which_refuses_an_unknown_session_provider():
    fake = FakeCli()
    with pytest.raises(op.Refusal) as refused:
        op.which("gemini", lookup=fake.lookup, runner=fake.run)
    assert refused.value.code == "bad-input"


# ---------------------------------------------------------------- judge


def input_folder(tmp_path, rows=("VR-1",), extra=None):
    folder = tmp_path / "judge-input"
    (folder / "evidence").mkdir(parents=True)
    (folder / "tests").mkdir()
    (folder / "rows.json").write_text(json.dumps([{"id": row, "then": "the list shows Approved"} for row in rows]))
    (folder / "evidence" / "shot.png").write_bytes(b"\x89PNG")
    (folder / "tests" / "test_list.py").write_text("def test_list(): assert True\n")
    if extra:
        (folder / extra).write_text("the builder says it works")
    return folder


def row_text(row="VR-1", seen=("a table with the Status column, value Approved",), result="pass", checks=None, first="seen", extra=""):
    checks = checks if checks is not None else [{"check": name, "result": "pass", "why": "ok"} for name in CHECKS]
    seen_part = f'"seen": {json.dumps(list(seen))}'
    compare_part = '"compare": ["the Then asks for Approved; the table shows Approved"]'
    parts = [seen_part, compare_part] if first == "seen" else [compare_part, seen_part]
    return "{" + f'"row": "{row}", ' + ", ".join(parts) + f', "checks": {json.dumps(checks)}, "result": "{result}"{extra}' + "}"


def codex_answer(*rows):
    return (0, '{"rows": [' + ", ".join(rows) + "]}\n")


def judge(folder, fake, session="claude"):
    return op.judge(folder, session, lookup=fake.lookup, runner=fake.run)


def test_judge_returns_one_verdict_per_row_naming_provider_model_and_effort(tmp_path):
    fake = FakeCli(codex_answer(row_text()))
    answer = judge(input_folder(tmp_path), fake)
    verdict = answer["verdicts"]["VR-1"]
    assert answer["ok"] is True
    assert (verdict["provider"], verdict["model"], verdict["effort"]) == ("codex", "cli-default", "medium")
    assert verdict["seen"] == ["a table with the Status column, value Approved"]
    assert verdict["result"] == "pass"
    assert list(verdict) == ["provider", "model", "effort", "seen", "compare", "checks", "result"]


def test_judge_runs_codex_read_only_in_the_input_folder_with_the_answer_schema(tmp_path):
    folder = input_folder(tmp_path)
    fake = FakeCli(codex_answer(row_text()))
    judge(folder, fake)
    argv = fake.calls[0]["argv"]
    assert argv[:2] == ["/bin/codex", "exec"]
    assert argv[argv.index("-s") + 1] == "read-only"
    assert argv[argv.index("-C") + 1] == str(folder)
    assert fake.calls[0]["cwd"] == str(folder)
    assert "--output-schema" in argv
    assert 'model_reasoning_effort="medium"' in argv
    assert argv[argv.index("-i") + 1] == str(folder / "evidence" / "shot.png")


def test_judge_runs_claude_with_read_tools_only_and_json_output(tmp_path):
    record({"judge_claude": "opus-x"})
    fake = FakeCli((0, json.dumps({"type": "result", "result": "", "structured_output": None}) .replace(
        '"structured_output": null', '"structured_output": {"rows": [' + row_text() + "]}")), signed_in=("claude",))
    answer = judge(input_folder(tmp_path), fake)
    argv = fake.calls[0]["argv"]
    assert argv[:2] == ["/bin/claude", "-p"]
    assert argv[argv.index("--tools") + 1] == "Read,Glob,Grep"
    assert argv[argv.index("--model") + 1] == "opus-x"
    assert argv[argv.index("--effort") + 1] == "medium"
    assert argv[argv.index("--output-format") + 1] == "json"
    assert json.loads(argv[argv.index("--json-schema") + 1]) == op.ANSWER_SCHEMA
    assert answer["verdicts"]["VR-1"]["result"] == "pass"


def test_judge_refuses_an_input_folder_with_anything_but_rows_evidence_and_tests(tmp_path):
    fake = FakeCli()
    with pytest.raises(op.Refusal) as refused:
        judge(input_folder(tmp_path, extra="CLAIMS.md"), fake)
    assert refused.value.code == "bad-input"
    assert fake.calls == []


def test_the_prompt_names_every_check_and_asks_to_describe_before_comparing(tmp_path):
    fake = FakeCli(codex_answer(row_text()))
    judge(input_folder(tmp_path), fake)
    prompt = fake.calls[0]["stdin"]
    for name in CHECKS:
        assert name in prompt
    assert prompt.index("seen") < prompt.index("compare")


@pytest.mark.parametrize("text, why", [
    (row_text(seen=()), "seen"),
    (row_text(first="compare"), "compare"),
    (row_text(extra=', "confidence": 0.9'), "confidence"),
])
def test_a_verdict_breaking_the_schema_fails_the_row(tmp_path, text, why):
    fake = FakeCli(codex_answer(text))
    verdict = judge(input_folder(tmp_path), fake)["verdicts"]["VR-1"]
    assert verdict["result"] == "fail"
    schema_fails = [item for item in verdict["checks"] if item["check"] == "verdict-schema"]
    assert schema_fails and why in schema_fails[0]["why"]
    assert len(fake.calls) == 1


def test_a_top_level_field_outside_the_schema_fails_every_row(tmp_path):
    fake = FakeCli((0, '{"rows": [' + row_text() + '], "note": "looks fine"}'))
    verdict = judge(input_folder(tmp_path), fake)["verdicts"]["VR-1"]
    assert verdict["result"] == "fail"


def test_a_missing_check_fails_the_row_and_names_the_check(tmp_path):
    checks = [{"check": name, "result": "pass", "why": "ok"} for name in CHECKS if name != "VC-6"]
    fake = FakeCli(codex_answer(row_text(checks=checks)))
    verdict = judge(input_folder(tmp_path), fake)["verdicts"]["VR-1"]
    assert verdict["result"] == "fail"
    assert any(item["check"] == "verdict-schema" and "VC-6" in item["why"] for item in verdict["checks"])


def test_a_failed_check_makes_the_row_fail_and_keeps_its_name(tmp_path):
    checks = [{"check": name, "result": "fail" if name == "VC-4" else "pass", "why": "asserts only no error"} for name in CHECKS]
    fake = FakeCli(codex_answer(row_text(checks=checks, result="pass")))
    verdict = judge(input_folder(tmp_path), fake)["verdicts"]["VR-1"]
    assert verdict["result"] == "fail"
    assert [item["check"] for item in verdict["checks"] if item["result"] == "fail"] == ["VC-4"]


def test_a_row_the_judge_left_out_fails(tmp_path):
    fake = FakeCli(codex_answer(row_text("VR-1")))
    verdicts = judge(input_folder(tmp_path, rows=("VR-1", "VR-2")), fake)["verdicts"]
    assert verdicts["VR-1"]["result"] == "pass"
    assert verdicts["VR-2"]["result"] == "fail"
    assert verdicts["VR-2"]["seen"] == []


# ---------------------------------------------------------------- retry


@pytest.mark.parametrize("first", ["timeout", (1, ""), (0, "not json")])
def test_a_transport_failure_gets_1_retry(tmp_path, first):
    fake = FakeCli(first, codex_answer(row_text()))
    answer = judge(input_folder(tmp_path), fake)
    assert answer["verdicts"]["VR-1"]["result"] == "pass"
    assert len(fake.calls) == 2


@pytest.mark.parametrize("answers, code", [
    (("timeout", "timeout"), "judge-timeout"),
    (((1, ""), (0, "not json")), "judge-unreadable"),
    (((0, "not json"), "timeout"), "judge-timeout"),
])
def test_a_second_transport_failure_refuses(tmp_path, answers, code):
    fake = FakeCli(*answers)
    with pytest.raises(op.Refusal) as refused:
        judge(input_folder(tmp_path), fake)
    assert refused.value.code == code
    assert len(fake.calls) == 2


def test_a_fail_verdict_is_never_retried(tmp_path):
    fake = FakeCli(codex_answer(row_text(result="fail")), codex_answer(row_text()))
    assert judge(input_folder(tmp_path), fake)["verdicts"]["VR-1"]["result"] == "fail"
    assert len(fake.calls) == 1


# ---------------------------------------------------------------- attack


def grill_log(tmp_path):
    folder = tmp_path / "ticket"
    folder.mkdir()
    (folder / "GRILL-LOG.md").write_text("## grill-requirements\n- R-1 the list shows a Status column\n", encoding="utf-8")
    (folder / "PRD.md").write_text("not for the devil")
    return folder / "GRILL-LOG.md"


FINDING = {"kind": "conflict", "what": "R-1 and R-2 ask for different sort orders", "where": "R-1, R-2"}


def test_attack_runs_1_read_only_call_on_a_copy_of_the_log_alone(tmp_path):
    log = grill_log(tmp_path)
    seen_files = []
    fake = FakeCli((0, json.dumps({"findings": [FINDING]})))
    run = fake.run

    def spy(argv, *, stdin, cwd, timeout):
        if cwd:
            seen_files.extend(sorted(path.name for path in Path(cwd).iterdir()))
        return run(argv, stdin=stdin, cwd=cwd, timeout=timeout)

    answer = op.attack(log, "claude", lookup=fake.lookup, runner=spy)
    argv = fake.calls[0]["argv"]
    assert argv[argv.index("-s") + 1] == "read-only"
    assert seen_files == ["GRILL-LOG.md"]
    assert "symptom" in fake.calls[0]["stdin"]
    assert answer == {"ok": True, "provider": "codex", "model": "cli-default", "effort": "medium", "findings": [FINDING]}


def test_attack_retries_an_answer_that_breaks_the_findings_schema_once(tmp_path):
    bad = (0, json.dumps({"findings": [{**FINDING, "score": 3}]}))
    fake = FakeCli(bad, bad)
    with pytest.raises(op.Refusal) as refused:
        op.attack(grill_log(tmp_path), "claude", lookup=fake.lookup, runner=fake.run)
    assert refused.value.code == "judge-unreadable"
    assert len(fake.calls) == 2


def test_attack_refuses_a_missing_log(tmp_path):
    fake = FakeCli()
    with pytest.raises(op.Refusal) as refused:
        op.attack(tmp_path / "GRILL-LOG.md", "claude", lookup=fake.lookup, runner=fake.run)
    assert refused.value.code == "bad-input"


def test_the_command_answers_one_json_object_and_exit_2_on_bad_input(capsys):
    assert op.main(["which", "--session", "gemini"]) == 2
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "bad-input"


# ---------------------------------------------------------------- claude output forms


def claude_envelope(model="claude-x"):
    return ('{"type": "result", "is_error": false, "result": "", "modelUsage": {"' + model + '": {"inputTokens": 1}}, '
            '"structured_output": {"rows": [' + row_text() + "]}}")


def test_judge_reads_the_result_of_a_verbose_claude_message_list(tmp_path):
    stdout = '[{"type": "system", "subtype": "init", "model": "claude-x"}, ' + claude_envelope() + "]"
    fake = FakeCli((0, stdout), on_path=("claude",))
    record({"judge_claude": "opus-x"})
    assert judge(input_folder(tmp_path), fake)["verdicts"]["VR-1"]["result"] == "pass"
    assert len(fake.calls) == 1


def test_a_cli_default_judge_names_the_model_the_cli_reports(tmp_path):
    fake = FakeCli((0, claude_envelope("claude-y")))
    answer = judge(input_folder(tmp_path), fake, session="codex")
    assert answer["model"] == "claude-y"
    assert answer["verdicts"]["VR-1"]["model"] == "claude-y"


def test_a_cli_default_codex_judge_names_the_model_of_its_header(tmp_path):
    fake = FakeCli(codex_answer(row_text()))
    fake.stderr = "OpenAI Codex v0\n--------\nworkdir: x\nmodel: gpt-z\nprovider: openai\n"
    assert judge(input_folder(tmp_path), fake)["verdicts"]["VR-1"]["model"] == "gpt-z"


def test_attack_gives_the_log_text_in_the_prompt(tmp_path):
    fake = FakeCli((0, json.dumps({"findings": []})))
    op.attack(grill_log(tmp_path), "claude", lookup=fake.lookup, runner=fake.run)
    assert "R-1 the list shows a Status column" in fake.calls[0]["stdin"]


# ---------------------------------------------------------------- isolation and input hardening


def test_the_codex_judge_ignores_the_user_config_and_rules_and_takes_the_recorded_model(tmp_path):
    record({"judge_codex": "gpt-9"})
    fake = FakeCli(codex_answer(row_text()))
    judge(input_folder(tmp_path), fake)
    argv = fake.calls[0]["argv"]
    assert "--ignore-user-config" in argv and "--ignore-rules" in argv
    assert argv[argv.index("-m") + 1] == "gpt-9"


def test_the_claude_judge_runs_in_safe_and_restricted_mode_with_no_mcp(tmp_path):
    fake = FakeCli((0, '{"type": "result", "structured_output": {"rows": [' + row_text() + "]}}"))
    judge(input_folder(tmp_path), fake, session="codex")
    argv = fake.calls[0]["argv"]
    assert "--safe-mode" in argv and "--restricted" in argv and "--strict-mcp-config" in argv
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"


def test_a_cmd_shim_cli_is_refused(tmp_path):
    fake = FakeCli()
    fake.lookup = lambda name: f"C:/npm/{name}.cmd"
    with pytest.raises(op.Refusal) as refused:
        judge(input_folder(tmp_path), fake)
    assert refused.value.code == "no-provider"
    assert fake.calls == []


@pytest.mark.parametrize("text, why", [
    (row_text().replace('"compare": ["the Then asks for Approved; the table shows Approved"]', '"compare": 5'), "compare"),
    (row_text(seen=("x", 7)), "seen"),
    (row_text(seen=(" ",)), "seen"),
    (row_text().replace(', "compare": ["the Then asks for Approved; the table shows Approved"]', ""), "compare"),
])
def test_a_verdict_with_a_wrong_field_type_or_a_missing_field_fails_the_row(tmp_path, text, why):
    fake = FakeCli(codex_answer(text))
    verdict = judge(input_folder(tmp_path), fake)["verdicts"]["VR-1"]
    assert verdict["result"] == "fail"
    assert any(item["check"] == "verdict-schema" and why in item["why"] for item in verdict["checks"])


def test_two_verdicts_for_one_row_fail_it(tmp_path):
    fake = FakeCli(codex_answer(row_text(), row_text()))
    verdict = judge(input_folder(tmp_path), fake)["verdicts"]["VR-1"]
    assert verdict["result"] == "fail"
    assert any("more than 1" in item["why"] for item in verdict["checks"] if item["check"] == "verdict-schema")


def test_a_top_level_field_outside_the_schema_fails_each_row_naming_the_field(tmp_path):
    fake = FakeCli((0, '{"rows": [' + row_text("VR-1") + ", " + row_text("VR-2") + '], "note": "fine"}'))
    verdicts = judge(input_folder(tmp_path, rows=("VR-1", "VR-2")), fake)["verdicts"]
    for row in ("VR-1", "VR-2"):
        assert verdicts[row]["result"] == "fail"
        assert any("`note`" in item["why"] for item in verdicts[row]["checks"])


@pytest.mark.parametrize("breakage", ["no-evidence", "rows-object", "same-id", "no-id"])
def test_a_bad_input_folder_is_refused_before_any_call(tmp_path, breakage):
    folder = input_folder(tmp_path)
    if breakage == "no-evidence":
        for item in (folder / "evidence").iterdir():
            item.unlink()
        (folder / "evidence").rmdir()
    else:
        rows = {"rows-object": {}, "same-id": [{"id": "VR-1"}, {"id": "VR-1"}], "no-id": [{"then": "x"}]}[breakage]
        (folder / "rows.json").write_text(json.dumps(rows))
    fake = FakeCli()
    with pytest.raises(op.Refusal) as refused:
        judge(folder, fake)
    assert refused.value.code == "bad-input"
    assert fake.calls == []


def test_a_verdict_validates_against_the_verdict_schema(tmp_path):
    fake = FakeCli(codex_answer(row_text(seen=())))
    verdict = judge(input_folder(tmp_path), fake)["verdicts"]["VR-1"]
    schema = op.VERDICT_SCHEMA
    assert set(verdict) == set(schema["required"]) == set(schema["properties"])
    assert verdict["provider"] in schema["properties"]["provider"]["enum"]
    assert verdict["result"] in schema["properties"]["result"]["enum"]
    check_enum = schema["properties"]["checks"]["items"]["properties"]["check"]["enum"]
    assert all(item["check"] in check_enum and set(item) == {"check", "result", "why"} for item in verdict["checks"])


def test_claude_answer_in_the_result_text_and_the_busiest_model_are_read(tmp_path):
    envelope = {"type": "result", "result": '{"rows": [' + row_text() + "]}",
                "modelUsage": {"claude-small": {"outputTokens": 3}, "claude-big": {"outputTokens": 900}}}
    fake = FakeCli((0, json.dumps(envelope)))
    answer = judge(input_folder(tmp_path), fake, session="codex")
    assert answer["verdicts"]["VR-1"]["result"] == "pass"
    assert answer["model"] == "claude-big"


@pytest.mark.parametrize("bad", [
    {"findings": [{**FINDING, "kind": "style"}]},
    {"findings": [{**FINDING, "what": 3}]},
    {"findings": [], "note": "x"},
])
def test_attack_counts_a_findings_answer_that_breaks_the_schema_as_unreadable(tmp_path, bad):
    fake = FakeCli((0, json.dumps(bad)), (0, json.dumps(bad)))
    with pytest.raises(op.Refusal) as refused:
        op.attack(grill_log(tmp_path), "claude", lookup=fake.lookup, runner=fake.run)
    assert refused.value.code == "judge-unreadable"


def test_attack_refuses_a_log_that_is_not_utf8(tmp_path):
    log = tmp_path / "GRILL-LOG.md"
    log.write_bytes(b"\xff\xfe\x00bad")
    fake = FakeCli()
    with pytest.raises(op.Refusal) as refused:
        op.attack(log, "claude", lookup=fake.lookup, runner=fake.run)
    assert refused.value.code == "bad-input"


def test_the_unreadable_reason_carries_the_tail_of_stderr(tmp_path):
    fake = FakeCli((1, ""), (1, ""))
    fake.stderr = "ERROR: the model is not supported"
    with pytest.raises(op.Refusal) as refused:
        judge(input_folder(tmp_path), fake)
    assert "the model is not supported" in refused.value.reason


def test_the_command_exits_1_on_a_refusal(capsys, monkeypatch):
    monkeypatch.setattr(op.shutil, "which", lambda name: None)
    assert op.main(["which", "--session", "claude"]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "no-provider"


def test_the_judge_prompt_holds_every_text_file_so_no_shell_is_needed(tmp_path):
    fake = FakeCli(codex_answer(row_text()))
    judge(input_folder(tmp_path), fake)
    prompt = fake.calls[0]["stdin"]
    assert "the list shows Approved" in prompt
    assert "def test_list(): assert True" in prompt
    assert "<evidence/shot.png>" not in prompt


def test_an_input_too_large_to_inline_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(op, "INLINE_CHARS", 10)
    fake = FakeCli()
    with pytest.raises(op.Refusal) as refused:
        judge(input_folder(tmp_path), fake)
    assert refused.value.code == "bad-input"

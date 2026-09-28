import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[2] / "skills" / "afk" / "review" / "scripts" / "forge_ledger.py"


def load_module():
    spec = importlib.util.spec_from_file_location("forge_ledger", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finding(**overrides):
    value = {
        "id": "r-001",
        "concern": "logic-correctness",
        "criterion": "reachable-path",
        "severity": "high",
        "class": "correctness",
        "file": "src/new.py",
        "line": 2,
        "finding": "The result is wrong.",
        "why": "The reachable branch returns zero.",
        "fix": "Return the computed value.",
        "evidence": "return 0",
    }
    value.update(overrides)
    return value


class FakeAdapter:
    def __init__(self, author="bot"):
        self.author = author
        self.notes = []
        self.threads = []
        self.calls = []
        self.head = "abc"
        self.cwd = Path.cwd()
        self.next_id = 1
        self.diff = ""
        self.view_overrides = {}

    def _id(self):
        value = str(self.next_id)
        self.next_id += 1
        return value

    def _note(self, body, note_id):
        return {"id": note_id, "author": self.author, "body": body,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z", "url": f"https://f/{note_id}"}

    def call(self, verb, payload, mode="read"):
        self.calls.append((verb, payload))
        if verb == "auth-status":
            return {"user": self.author}
        if verb == "change-view":
            return {"head_sha": self.head, "base_sha": "base", "head_ref": "topic",
                    "blob_base": "https://f/blob", "cross_fork": False, **self.view_overrides}
        if verb == "change-diff":
            return {"diff": self.diff}
        if verb == "note-list":
            return {"notes": self.notes, "count": len(self.notes)}
        if verb == "thread-list":
            return {"threads": self.threads, "count": len(self.threads)}
        if verb == "change-comment":
            number = self._id()
            if payload.get("line") is not None or payload.get("old_line") is not None:
                thread = {"id": "t" + number, "resolved": False,
                          "url": f"https://f/t{number}", "notes": [self._note(payload["text"], number)]}
                self.threads.append(thread)
                return {"ok": True, "inline": True, "thread": thread["id"],
                        "comment": number, "url": thread["url"]}
            self.notes.append(self._note(payload["text"], number))
            return {"ok": True, "inline": False, "thread": "", "comment": number,
                    "url": f"https://f/{number}"}
        if verb == "thread-reply":
            thread = next(t for t in self.threads if t["id"] == payload["thread"])
            number = self._id()
            thread["notes"].append(self._note(payload["text"], number))
            return {"ok": True, "comment": number}
        if verb == "thread-resolve":
            thread = next(t for t in self.threads if t["id"] == payload["thread"])
            thread["resolved"] = payload["resolved"]
            return {"ok": True, "thread": thread["id"], "resolved": thread["resolved"]}
        raise AssertionError(verb)


def args(**values):
    defaults = {"trust": [], "reject": []}
    defaults.update(values)
    return type("Args", (), defaults)()


def test_marker_round_trip_is_deterministic_and_normalizes_paths():
    ledger = load_module()
    item = finding(file="./src\\new.py")
    locator = ledger.normalize_locator(item)
    first = ledger.make_finding_marker("slice/f001", "slice", "abc", item, locator)
    second = ledger.make_finding_marker("slice/f001", "slice", "abc", item, locator)
    assert first == second
    parsed = ledger.parse_marker(first)
    assert parsed["key"] == "slice/f001"
    assert parsed["file"] == "src/new.py"
    assert parsed["data"] == item
    assert len(parsed["rfp"]) == 64
    assert len(parsed["sfp"]) == 64


@pytest.mark.parametrize(
    ("path", "line", "side", "expected"),
    [
        ("src/new.py", 2, "new", True),
        ("src/new.py", 1, "context", True),
        ("src/old.py", 2, "old", True),
        ("src/new.py", 90, "new", False),
    ],
)
def test_diff_parser_tracks_added_context_removed_and_renamed_lines(path, line, side, expected):
    ledger = load_module()
    diff = """diff --git a/src/old.py b/src/new.py
similarity index 80%
rename from src/old.py
rename to src/new.py
--- a/src/old.py
+++ b/src/new.py
@@ -1,2 +1,2 @@
 same
-old
+new
"""
    parsed = ledger.parse_diff(diff)
    locator = {"file": path, "old_path": "src/old.py", "new_path": "src/new.py",
               "line": line if side != "old" else None,
               "old_line": line if side == "old" else None, "side": side}
    assert ledger.is_anchorable(locator, parsed) is expected


def test_transition_table_rejects_deferred_to_product_debt():
    ledger = load_module()
    with pytest.raises(ledger.LedgerError):
        ledger.validate_transition(
            {"kind": "deferred", "attrs": {"gate": "feature"}},
            "disposition",
            {"result": "product-debt", "home": "AGENTS.md"},
        )
    ledger.validate_transition(
        {"kind": "verdict", "attrs": {"result": "stands"}},
        "disposition",
        {"result": "product-debt", "home": "AGENTS.md"},
    )


def test_op_id_changes_for_second_dispute_after_stands():
    ledger = load_module()
    first = ledger.operation_id("slice/f001", "dispute", {}, 1)
    replay = ledger.operation_id("slice/f001", "dispute", {}, 1)
    second = ledger.operation_id("slice/f001", "dispute", {}, 3)
    assert first == replay
    assert first != second


def test_ledger_only_defaults_are_narrow_and_globs_are_segment_aware():
    ledger = load_module()
    defaults = ledger.DEFAULT_LEDGER_ONLY_PATHS
    assert ledger.is_ledger_only("plan/review/a.md", defaults)
    assert ledger.is_ledger_only("plan/JOURNAL.md", defaults)
    assert not ledger.is_ledger_only("plan/PLAN.md", defaults)
    assert not ledger.is_ledger_only("plan/DECISIONS.md", defaults)
    assert not ledger.is_ledger_only("skills/afk/review/SKILL.md", defaults)
    assert ledger.is_ledger_only("docs/a/b.md", ["docs/**"])
    assert not ledger.is_ledger_only("docs/a/b.md", ["docs/*"])


def test_changed_paths_preserves_non_ascii_ledger_only_path_from_git(tmp_path):
    ledger = load_module()

    def git(*arguments):
        return ledger.subprocess.run(
            ["git", *arguments], cwd=tmp_path, check=True,
            text=True, capture_output=True).stdout.strip()

    git("init", "-q")
    git("config", "user.name", "Ledger Test")
    git("config", "user.email", "ledger@example.test")
    git("commit", "--allow-empty", "-qm", "base")
    start = git("rev-parse", "HEAD")
    review_dir = tmp_path / "plan" / "review"
    review_dir.mkdir(parents=True)
    (review_dir / "café.md").write_text("review\n", encoding="utf-8")
    git("add", "--", "plan/review/café.md")
    git("commit", "-qm", "ledger")
    end = git("rev-parse", "HEAD")

    paths = ledger.changed_paths(tmp_path, start, end)
    assert paths == ["plan/review/café.md"]
    assert ledger.is_ledger_only(paths[0], ledger.DEFAULT_LEDGER_ONLY_PATHS)


def test_changed_paths_reports_both_sides_and_rejects_code_to_ledger_rename(
        tmp_path, monkeypatch):
    ledger = load_module()

    def git(*arguments):
        return ledger.subprocess.run(
            ["git", *arguments], cwd=tmp_path, check=True,
            text=True, capture_output=True).stdout.strip()

    git("init", "-q")
    git("config", "user.name", "Ledger Test")
    git("config", "user.email", "ledger@example.test")
    source = tmp_path / "src" / "code.py"
    source.parent.mkdir()
    source.write_text("value = 1\n", encoding="utf-8")
    git("add", "--", "src/code.py")
    git("commit", "-qm", "base")
    start = git("rev-parse", "HEAD")
    review_dir = tmp_path / "plan" / "review"
    review_dir.mkdir(parents=True)
    source.rename(review_dir / "code.md")
    git("add", "-A")
    git("commit", "-qm", "move")
    end = git("rev-parse", "HEAD")

    paths = ledger.changed_paths(tmp_path, start, end)
    assert set(paths) == {"src/code.py", "plan/review/code.md"}
    assert any(not ledger.is_ledger_only(path, ledger.DEFAULT_LEDGER_ONLY_PATHS)
               for path in paths)
    adapter = FakeAdapter()
    adapter.cwd = tmp_path
    adapter.head = end
    adapter.view_overrides["base_sha"] = start
    monkeypatch.setattr(ledger, "Adapter", lambda: adapter)
    history = tmp_path / "history.json"
    history.write_text(json.dumps({
        "round": 1, "start_head": start, "reviewed_head": end,
        "code_changed": True, "keys_new": [], "keys_remediated": [],
        "scope_shape_keys": [], "agents_md_chain_new": [],
        "scope_escalated": False, "ledger_only": True, "observed": [],
    }), encoding="utf-8")
    summary = tmp_path / "summary.txt"
    summary.write_text("Summary.", encoding="utf-8")
    assert ledger.main([
        "summary", "--change", "1", "--unit", "slice", "--round", "1",
        "--head", end, "--clean", "false", "--ledger-only", "true",
        "--text-file", str(summary), "--history-file", str(history),
    ]) == 2
    assert not [verb for verb, _ in adapter.calls
                if verb in {"change-comment", "thread-reply", "thread-resolve"}]


def test_trailers_deduplicate_and_keep_order():
    ledger = load_module()
    assert ledger.trailers("slice/f002,slice/f001,slice/f002") == {
        "trailers": ["Settles: slice/f002", "Settles: slice/f001"]
    }
    with pytest.raises(ledger.UsageError):
        ledger.trailers("")


def test_trust_classification_fails_closed_and_rejects_conflicts():
    ledger = load_module()
    with pytest.raises(ledger.LedgerError, match="unclassified_authors"):
        ledger.classify_author("alice", {"bob"}, set())
    assert ledger.classify_author("alice", {"bob"}, {"alice"}) == "rejected"
    with pytest.raises(ledger.UsageError):
        ledger.validate_trust({"alice"}, {"alice"})


def test_edited_marker_is_counted_before_trust():
    ledger = load_module()
    note = {
        "id": "1",
        "author": "mallory",
        "body": "<!-- afk:record v1 key=slice%2Ff001 seq=2 kind=carried op=x -->",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:01:00Z",
    }
    scan = ledger.scan_entries([note], trusted={"bob"}, rejected={"mallory"})
    assert scan.edited_markers == 1


def test_reconstruct_rejects_malformed_version_sequence_op_and_transition():
    ledger = load_module()
    cases = [
        "<!-- afk:record v2 key=slice%2Ff001 seq=2 kind=carried op=x -->",
        ledger.make_record_marker("slice/f001", 3, "carried", {}, 1),
        "<!-- afk:record v1 key=slice%2Ff001 seq=2 kind=carried op=wrong -->",
        ledger.make_record_marker("slice/f001", 2, "verdict", {"result": "stands", "reason": "no"}, 1),
    ]
    for record in cases:
        adapter = FakeAdapter()
        marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                            ledger.normalize_locator(finding()))
        adapter.notes = [adapter._note(marker, "1"), adapter._note(record, "2")]
        with pytest.raises(ledger.LedgerError):
            ledger.reconstruct_state(adapter, "1")


def test_duplicate_note_ids_keep_latest_and_reject_equal_time_divergence():
    ledger = load_module()
    older = {"id": "7", "body": "old", "updated_at": "2026-01-01T00:00:00Z"}
    newer = {"id": "7", "body": "new", "updated_at": "2026-01-01T00:01:00Z"}
    assert ledger.dedupe_notes([older, newer]) == [newer]
    divergent = {**newer, "body": "different"}
    with pytest.raises(ledger.LedgerError, match="duplicate note id"):
        ledger.dedupe_notes([newer, divergent])


def test_summary_history_prefix_is_immutable():
    ledger = load_module()
    old = [{"round": 1, "reviewed_head": "a"}]
    assert ledger.append_history(old, old[0]) == old
    with pytest.raises(ledger.LedgerError):
        ledger.append_history(old, {"round": 1, "reviewed_head": "b"})
    assert ledger.append_history(old, {"round": 2, "reviewed_head": "b"})[-1]["round"] == 2


def test_history_schema_rejects_missing_fields_wrong_types_and_foreign_keys():
    ledger = load_module()
    valid = {
        "round": 1, "start_head": "base", "reviewed_head": "abc",
        "code_changed": False, "keys_new": [], "keys_remediated": [],
        "scope_shape_keys": [], "agents_md_chain_new": [],
        "scope_escalated": False, "ledger_only": False, "observed": [],
    }
    ledger.validate_history_entry(valid, "slice", set())
    for broken in (
        {k: v for k, v in valid.items() if k != "observed"},
        {**valid, "scope_escalated": "false"},
        {**valid, "keys_new": ["other/f001"]},
    ):
        with pytest.raises(ledger.LedgerError):
            ledger.validate_history_entry(broken, "slice", set())


def test_parse_adapter_output_rejects_extra_stdout_and_errors():
    ledger = load_module()
    assert ledger.parse_adapter_output('{"ok":true}\n', "write") == {"ok": True}
    with pytest.raises(ledger.LedgerError):
        ledger.parse_adapter_output('{"ok":true}\nnoise\n', "write")
    with pytest.raises(ledger.LedgerError):
        ledger.parse_adapter_output('{"unsupported":true}\n', "read")


def test_full_post_reconstruct_reply_and_resolve_round(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "change.diff"
    diff.write_text("""diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -1,1 +1,2 @@
 same
+new
""", encoding="utf-8")
    posted = ledger.command_post(args(change="1", unit="slice", findings=str(findings),
                                      diff=str(diff), head="abc", hints=None, map=None, state=None), adapter)
    assert posted["posted"] == 1
    assert posted["anchored"] == 1
    state = ledger.reconstruct_state(adapter, "1")
    key = state["units"]["slice"]["keys"]["slice/f001"]
    assert key["anchored"]
    assert key["routing"]["blocks_ship"]

    disputed = ledger.command_reply(args(change="1", key="slice/f001", kind="dispute",
                                          attr=[], text="The rule does not apply."), adapter)
    assert disputed["kind"] == "dispute"
    ledger.command_reply(args(change="1", key="slice/f001", kind="verdict",
                              attr=[["result", "withdrawn"], ["reason", "Evidence accepted"]],
                              text="Withdrawn."), adapter)
    resolved = ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), adapter)
    assert resolved["resolved"]
    state = ledger.reconstruct_state(adapter, "1")
    assert state["units"]["slice"]["keys"]["slice/f001"]["outcome"] == "verdict withdrawn"


def test_unanchored_records_are_new_immutable_notes(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([finding(line=99)]), encoding="utf-8")
    diff = tmp_path / "change.diff"
    diff.write_text("", encoding="utf-8")
    ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                             head="abc", hints=None, map=None, state=None), adapter)
    first_body = adapter.notes[0]["body"]
    ledger.command_reply(args(change="1", key="slice/f001", kind="carried", attr=[],
                              text="Carry this finding."), adapter)
    assert len(adapter.notes) == 2
    assert adapter.notes[0]["body"] == first_body
    assert "afk:record" in adapter.notes[1]["body"]


def test_every_stateful_command_fails_before_write_for_unclassified_author(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter(author="new-bot")
    marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                        ledger.normalize_locator(finding()))
    foreign = adapter._note(marker, "foreign")
    foreign["author"] = "old-bot"
    adapter.notes.append(foreign)
    before = len(adapter.calls)
    with pytest.raises(ledger.LedgerError, match="unclassified_authors"):
        ledger.reconstruct_state(adapter, "1")
    assert all(verb not in {"change-comment", "thread-reply", "thread-resolve"}
               for verb, _ in adapter.calls[before:])


def test_summary_is_new_note_and_history_reconstructs(tmp_path):
    ledger = load_module()
    ledger.changed_paths = lambda cwd, start, end: []
    adapter = FakeAdapter()
    text = tmp_path / "summary.txt"
    text.write_text("Round accounting.", encoding="utf-8")
    history = tmp_path / "history.json"
    entry = {"round": 1, "reviewed_head": "abc", "start_head": "base",
             "observed": [], "scope_shape_keys": [], "agents_md_chain_new": [],
             "scope_escalated": False, "ledger_only": False, "code_changed": False,
             "keys_new": [], "keys_remediated": []}
    history.write_text(json.dumps(entry), encoding="utf-8")
    result = ledger.command_summary(args(change="1", unit="slice", round=1, head="abc",
                                         clean=True, ledger_only=False, text_file=str(text),
                                         history_file=str(history)), adapter)
    assert result["ok"]
    state = ledger.reconstruct_state(adapter, "1")
    unit = state["units"]["slice"]
    assert unit["round"] == 1
    assert unit["clean"]
    assert unit["history"] == [entry]


def test_summary_rejects_caller_truncation_and_wrong_start_head(tmp_path):
    ledger = load_module()
    ledger.changed_paths = lambda cwd, start, end: []
    adapter = FakeAdapter()
    text = tmp_path / "summary.txt"
    text.write_text("Round accounting.", encoding="utf-8")
    base = {"round": 1, "reviewed_head": "abc", "start_head": "base",
            "scope_shape_keys": [], "agents_md_chain_new": [],
            "scope_escalated": False, "ledger_only": False, "code_changed": False,
            "keys_new": [], "keys_remediated": []}
    history = tmp_path / "history.json"
    history.write_text(json.dumps(base), encoding="utf-8")
    with pytest.raises(ledger.LedgerError, match="history fields"):
        ledger.command_summary(args(change="1", unit="slice", round=1, head="abc",
                                    clean=True, ledger_only=False, text_file=str(text),
                                    history_file=str(history)), adapter)
    history.write_text(json.dumps({**base, "observed": [], "start_head": "caller"}),
                       encoding="utf-8")
    with pytest.raises(ledger.LedgerError, match="start_head"):
        ledger.command_summary(args(change="1", unit="slice", round=1, head="abc",
                                    clean=True, ledger_only=False, text_file=str(text),
                                    history_file=str(history)), adapter)


def test_product_debt_proof_is_scoped_to_known_debt_section(tmp_path):
    ledger = load_module()
    home = tmp_path / "AGENTS.md"
    home.write_text("ledger: slice/f001\n\n## Known debt\n\n- another entry\n", encoding="utf-8")
    assert not ledger.known_debt_has_key(home, "slice/f001")
    home.write_text("## Known debt\n\n- debt; ledger: slice/f001\n\n## Rules\n", encoding="utf-8")
    assert ledger.known_debt_has_key(home, "slice/f001")


def test_reviewer_product_debt_is_rejected():
    ledger = load_module()
    with pytest.raises(ledger.UsageError, match="product-debt"):
        ledger.validate_finding(finding(**{"class": "product-debt"}))


def test_open_reuse_reanchors_and_reclassifies_before_seen(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "change.diff"
    diff.write_text("""diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -1,1 +1,2 @@
 same
+new
""", encoding="utf-8")
    base_args = dict(change="1", unit="slice", findings=str(findings), diff=str(diff),
                     head="abc", hints=None, map=None, state=None)
    ledger.command_post(args(**base_args), adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="carried", attr=[],
                              text="Carry."), adapter)

    changed = finding(line=3, severity="medium")
    findings.write_text(json.dumps([changed]), encoding="utf-8")
    diff.write_text("""diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -2,1 +2,2 @@
 same
+new
""", encoding="utf-8")
    mapped = tmp_path / "map.json"
    mapped.write_text(json.dumps({"0": "slice/f001"}), encoding="utf-8")
    result = ledger.command_post(args(**{**base_args, "map": str(mapped)}), adapter)
    assert result["reused_open"] == 1
    assert result["stale_locator"] == 0
    state = ledger.reconstruct_state(adapter, "1")
    key = state["units"]["slice"]["keys"]["slice/f001"]
    assert key["line"] == 3
    assert key["locator_current"]
    assert key["routing"]["severity"] == "medium"
    assert len(key["threads"]) == 2


@pytest.mark.parametrize("kind", ["fixed", "verified"])
def test_cli_reply_normalizes_line_and_reconstructs(kind, monkeypatch, capsys):
    ledger = load_module()
    adapter = FakeAdapter()
    marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                        ledger.normalize_locator(finding()))
    adapter.notes.append(adapter._note(marker, "1"))
    adapter.next_id = 2
    monkeypatch.setattr(ledger, "Adapter", lambda: adapter)
    code = ledger.main(["reply", "--change", "1", "--key", "slice/f001", "--kind", kind,
                        "--sha", "abc", "--path", "src/new.py", "--line", "2",
                        "--side", "new", "--text", "Done."])
    assert code == 0, capsys.readouterr().out
    assert ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]["outcome"] == kind


def test_illegal_fixed_does_not_move_unanchored_key(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(line=99),
                                        ledger.normalize_locator(finding(line=99)))
    adapter.notes.append(adapter._note(marker, "1"))
    adapter.next_id = 2
    ledger.command_reply(args(change="1", key="slice/f001", kind="dispute", attr=[],
                              text="Dispute."), adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="verdict",
                              attr=[["result", "withdrawn"], ["reason", "accepted"]],
                              text="Withdrawn."), adapter)
    adapter.diff = """diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -1,1 +1,2 @@
 same
+new
"""
    before = list(adapter.calls)
    with pytest.raises(ledger.LedgerError, match="terminal"):
        ledger.command_reply(args(change="1", key="slice/f001", kind="fixed", attr=[],
                                  sha="abc", path="src/new.py", line="2", side="new",
                                  text="Fixed."), adapter)
    assert not any(verb == "change-comment" for verb, _ in adapter.calls[len(before):])


@pytest.mark.parametrize("terminal", ["withdrawn", "disposition"])
def test_terminal_reuse_with_changed_routing_remains_readable(tmp_path, terminal):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "change.diff"
    diff.write_text("""diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -1,1 +1,2 @@
 same
+new
""", encoding="utf-8")
    post = args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                head="abc", hints=None, map=None, state=None)
    ledger.command_post(post, adapter)
    if terminal == "withdrawn":
        ledger.command_reply(args(change="1", key="slice/f001", kind="dispute", attr=[], text="D"), adapter)
        ledger.command_reply(args(change="1", key="slice/f001", kind="verdict",
                                  attr=[["result", "withdrawn"], ["reason", "R"]], text="V"), adapter)
    else:
        ledger.command_reply(args(change="1", key="slice/f001", kind="disposition",
                                  attr=[["result", "pattern-debt"]], text="D"), adapter)
    findings.write_text(json.dumps([finding(severity="medium")]), encoding="utf-8")
    result = ledger.command_post(post, adapter)
    assert result["reused_closed"] == 1
    state = ledger.reconstruct_state(adapter, "1")
    assert state["units"]["slice"]["keys"]["slice/f001"]["routing"]["severity"] == "medium"


def test_seen_is_current_finding_and_same_head_retry_writes_nothing(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "change.diff"
    diff.write_text("", encoding="utf-8")
    base = args(change="1", unit="slice", findings=str(findings), diff=str(diff), head="abc",
                hints=None, map=None, state=None)
    ledger.command_post(base, adapter)
    mapped = tmp_path / "map.json"
    mapped.write_text(json.dumps({"0": "slice/f001"}), encoding="utf-8")
    findings.write_text(json.dumps([finding(finding="Paraphrased.")]), encoding="utf-8")
    mapped_args = args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                       head="abc", hints=None, map=str(mapped), state=None)
    ledger.command_post(mapped_args, adapter)
    state = ledger.reconstruct_state(adapter, "1")
    assert state["units"]["slice"]["keys"]["slice/f001"]["finding"]["finding"] == "Paraphrased."
    writes = len([c for c in adapter.calls if c[0] in {"change-comment", "thread-reply"}])
    ledger.command_post(mapped_args, adapter)
    assert len([c for c in adapter.calls if c[0] in {"change-comment", "thread-reply"}]) == writes


def test_reply_rejects_unknown_and_missing_attrs_before_write():
    ledger = load_module()
    adapter = FakeAdapter()
    marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                        ledger.normalize_locator(finding()))
    adapter.notes.append(adapter._note(marker, "1"))
    adapter.next_id = 2
    for kind, attrs in (("carried", [["extra", "poison"]]), ("deferred", [])):
        before = len(adapter.calls)
        with pytest.raises((ledger.LedgerError, ledger.UsageError)):
            ledger.command_reply(args(change="1", key="slice/f001", kind=kind,
                                      attr=attrs, text="x"), adapter)
        assert not any(v in {"change-comment", "thread-reply"} for v, _ in adapter.calls[before:])


def test_adapter_requires_complete_change_view(monkeypatch):
    ledger = load_module()
    answer = type("Run", (), {"returncode": 0, "stdout": '{"head_sha":"a","base_sha":"b"}\n', "stderr": ""})()
    monkeypatch.setenv("AFK_LEDGER_ADAPTER_CMD", "stub")
    monkeypatch.setattr(ledger.subprocess, "run", lambda *a, **k: answer)
    with pytest.raises(ledger.LedgerError, match="omitted"):
        ledger.Adapter().call("change-view", {"id": "1"})


def test_closure_rejects_cross_fork_and_pending_move():
    ledger = load_module()
    adapter = FakeAdapter()
    adapter.call = lambda verb, payload, mode="read": (
        {"user": "bot"} if verb == "auth-status" else
        {"head_sha": "abc", "base_sha": "base", "head_ref": "topic",
         "blob_base": "https://f/blob", "cross_fork": True} if verb == "change-view" else
        {"notes": [], "count": 0} if verb == "note-list" else {"threads": [], "count": 0})
    with pytest.raises(ledger.LedgerError, match="cross-fork"):
        ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                 round=1, expected=None), adapter)


def test_public_finding_locator_uses_rename_and_context_diff():
    ledger = load_module()
    parsed = ledger.parse_diff("""diff --git a/src/old.py b/src/new.py
similarity index 90%
rename from src/old.py
rename to src/new.py
--- a/src/old.py
+++ b/src/new.py
@@ -7,2 +10,2 @@
 same
-old
+new
""")
    old = ledger.locator_from_diff(finding(file="src/new.py", line=8, side="old"), parsed)
    assert old == {"file": "src/old.py", "old_path": "src/old.py", "new_path": "src/new.py",
                   "line": None, "old_line": 8, "side": "old"}
    context = ledger.locator_from_diff(finding(file="src/new.py", line=10, side="context"), parsed)
    assert context["old_path"] == "src/old.py"
    assert context["old_line"] == 7


def test_progress_gate_accepts_mapped_seen_and_rejects_skipped_post(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "findings.json"
    diff = tmp_path / "change.diff"
    diff.write_text("", encoding="utf-8")
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    post = args(change="1", unit="slice", findings=str(findings), diff=str(diff), head="abc",
                hints=None, map=None, state=None)
    ledger.command_post(post, adapter)
    mapped = tmp_path / "map.json"
    mapped.write_text(json.dumps({"0": "slice/f001"}), encoding="utf-8")
    current = finding(finding="Equivalent paraphrase.")
    findings.write_text(json.dumps([current]), encoding="utf-8")
    ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                             head="abc", hints=None, map=str(mapped), state=None), adapter)
    assert ledger.command_gate(args(change="1", unit="slice", phase="progress", head="abc",
                                    expected=str(findings), round=None), adapter)["ok"]
    missing = tmp_path / "missing.json"
    missing.write_text(json.dumps([finding(id="other", finding="Different")]), encoding="utf-8")
    with pytest.raises(ledger.LedgerError, match="missing durable"):
        ledger.command_gate(args(change="1", unit="slice", phase="progress", head="abc",
                                 expected=str(missing), round=None), adapter)


def _add_clean_summary(ledger, adapter, unit="slice", head="abc", round_number=1):
    history = {"round": round_number, "start_head": "base", "reviewed_head": head,
               "code_changed": False, "keys_new": [], "keys_remediated": [],
               "scope_shape_keys": [], "agents_md_chain_new": [],
               "scope_escalated": False, "ledger_only": False, "observed": []}
    body = (f"<!-- afk:settle:summary v1 unit={unit} round={round_number} "
            f"reviewed_head={head} clean=true ledger_only=false -->\n\n"
            f"<!-- afk:settle:history v1 data={ledger.b64(history)} -->")
    adapter.notes.append(adapter._note(body, adapter._id()))


def test_closure_rejects_moved_head_and_unanchored_key():
    ledger = load_module()
    adapter = FakeAdapter()
    _add_clean_summary(ledger, adapter)
    with pytest.raises(ledger.LedgerError, match="forge head moved"):
        ledger.command_gate(args(change="1", unit="slice", phase="closure", head="old",
                                 expected=None, round=1), adapter)
    marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(line=99),
                                        ledger.normalize_locator(finding(line=99)))
    adapter.notes.insert(0, adapter._note(marker, adapter._id()))
    ledger.command_reply(args(change="1", key="slice/f001", kind="disposition",
                              attr=[["result", "pattern-debt"]], text="Debt."), adapter)
    with pytest.raises(ledger.LedgerError, match="no current inline"):
        ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                 expected=None, round=1), adapter)


def test_main_exit_codes_and_atomic_state_cache(tmp_path, monkeypatch, capsys):
    ledger = load_module()
    adapter = FakeAdapter()
    marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                        ledger.normalize_locator(finding()))
    adapter.notes.append(adapter._note(marker, "1"))
    adapter.next_id = 2
    monkeypatch.setattr(ledger, "Adapter", lambda: adapter)
    state_file = tmp_path / "state.json"
    code = ledger.main(["reply", "--change", "1", "--key", "slice/f001", "--kind", "carried",
                        "--text", "Carry.", "--state", str(state_file)])
    assert code == 0
    assert json.loads(state_file.read_text(encoding="utf-8"))["ok"] is True
    assert not state_file.with_suffix(".json.tmp").exists()
    assert ledger.main(["reply", "--change", "1", "--key", "slice/f001", "--kind", "bogus",
                        "--text", "x"]) == 3
    assert ledger.main(["gate", "--change", "1", "--unit", "slice", "--phase", "closure",
                        "--head", "abc", "--round", "1"]) == 2
    capsys.readouterr()


def test_fixed_recurrence_creates_regression_key(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "change.diff"
    diff.write_text("", encoding="utf-8")
    post = args(change="1", unit="slice", findings=str(findings), diff=str(diff), head="abc",
                hints=None, map=None, state=None)
    ledger.command_post(post, adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="fixed", attr=[], sha="abc",
                              path="src/new.py", line="2", side="new", text="Fixed."), adapter)
    result = ledger.command_post(post, adapter)
    assert result["posted"] == 1
    assert set(result["keys"]) == {"slice/f002"}


def test_identical_post_retry_writes_nothing(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "change.diff"
    diff.write_text("", encoding="utf-8")
    post = args(change="1", unit="slice", findings=str(findings), diff=str(diff), head="abc",
                hints=None, map=None, state=None)
    ledger.command_post(post, adapter)
    writes = len([call for call in adapter.calls if call[0] in {"change-comment", "thread-reply"}])
    result = ledger.command_post(post, adapter)
    assert result["posted"] == 0
    assert len([call for call in adapter.calls if call[0] in {"change-comment", "thread-reply"}]) == writes


def test_ambiguous_match_requires_one_to_one_map(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([finding(), finding(id="r-002", line=3)]), encoding="utf-8")
    diff = tmp_path / "change.diff"
    diff.write_text("", encoding="utf-8")
    post = args(change="1", unit="slice", findings=str(findings), diff=str(diff), head="abc",
                hints=None, map=None, state=None)
    ledger.command_post(post, adapter)
    findings.write_text(json.dumps([finding(id="r-003", line=4)]), encoding="utf-8")
    with pytest.raises(ledger.LedgerError, match="ambiguous sfp"):
        ledger.command_post(post, adapter)
    mapping = tmp_path / "map.json"
    mapping.write_text(json.dumps({"0": "slice/f001", "r-003": "slice/f001"}), encoding="utf-8")
    with pytest.raises(ledger.LedgerError, match="one-to-one"):
        ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                                 head="abc", hints=None, map=str(mapping), state=None), adapter)


def test_feature_post_moves_deferred_slice_key(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "change.diff"
    diff.write_text("""diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -1,1 +1,2 @@
 same
+new
""", encoding="utf-8")
    ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                             head="abc", hints=None, map=None, state=None), adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="deferred",
                              attr=[["gate", "feature"]], text="Defer."), adapter)
    findings.write_text(json.dumps([finding(line=3)]), encoding="utf-8")
    diff.write_text("""diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -2,1 +2,2 @@
 same
+new
""", encoding="utf-8")
    result = ledger.command_post(args(change="1", unit="feature", findings=str(findings),
                                      diff=str(diff), head="abc", hints=None, map=None, state=None), adapter)
    assert result["reused_open"] == 1
    assert ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]["line"] == 3


def test_next_write_repairs_interrupted_move_on_old_thread():
    ledger = load_module()
    adapter = FakeAdapter()
    origin = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                        ledger.normalize_locator(finding()))
    first = adapter.call("change-comment", {"id": "1", "text": origin, "file": "src/new.py",
                                             "old_path": "src/new.py", "new_path": "src/new.py",
                                             "line": 2, "old_line": None, "side": "new"}, "write")
    state = ledger.reconstruct_state(adapter, "1")
    key_state = state["units"]["slice"]["keys"]["slice/f001"]
    _, marker = ledger._record(adapter, "1", key_state, "slice/f001", "move-intent",
                               {"to": ledger.b64({"file": "src/new.py"})}, "Move.")
    op = ledger.parse_marker(marker)["op"]
    moved = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(line=3),
                                       ledger.normalize_locator(finding(line=3)), moved_from=op)
    adapter.call("change-comment", {"id": "1", "text": moved, "file": "src/new.py",
                                     "old_path": "src/new.py", "new_path": "src/new.py",
                                     "line": 3, "old_line": None, "side": "new"}, "write")
    adapter.threads[-1]["notes"][0]["created_at"] = "2026-01-01T00:00:01Z"
    adapter.threads[-1]["notes"][0]["updated_at"] = "2026-01-01T00:00:01Z"
    assert ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]["pending_move"]
    ledger.command_reply(args(change="1", key="slice/f001", kind="carried", attr=[], text="Carry."), adapter)
    repaired = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    assert not repaired["pending_move"]
    old_thread = next(thread for thread in adapter.threads if thread["id"] == first["thread"])
    assert any("kind=moved" in note["body"] for note in old_thread["notes"])


def test_foreign_duplicate_origin_fails_reconstruction():
    ledger = load_module()
    adapter = FakeAdapter()
    marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                        ledger.normalize_locator(finding()))
    adapter.notes.extend([adapter._note(marker, "1"), adapter._note(marker, "2")])
    with pytest.raises(ledger.LedgerError, match="duplicate finding origin"):
        ledger.reconstruct_state(adapter, "1")


def _post_one(ledger, adapter, tmp_path, item=None, unit="slice"):
    item = item or finding()
    findings = tmp_path / f"{unit}-findings.json"
    findings.write_text(json.dumps([item]), encoding="utf-8")
    diff = tmp_path / f"{unit}.diff"
    line = item["line"]
    diff.write_text(f"""diff --git a/{item['file']} b/{item['file']}
--- a/{item['file']}
+++ b/{item['file']}
@@ -{max(1, line - 1)},1 +{max(1, line - 1)},2 @@
 same
+new
""", encoding="utf-8")
    return ledger.command_post(args(change="1", unit=unit, findings=str(findings), diff=str(diff),
                                    head="abc", hints=None, map=None, state=None), adapter)


def _summarize(ledger, adapter, tmp_path, unit="slice", clean=True, ledger_only=False, paths=()):
    ledger.changed_paths = lambda cwd, start, end: list(paths)
    state = ledger.reconstruct_state(adapter, "1")
    unit_state = state["units"].get(unit, {"keys": {}, "history": []})
    extra = {}
    if unit == "feature":
        extra = {key: value for other in state["units"].values()
                 for key, value in other.get("keys", {}).items()
                 if "feature" in value.get("ever_deferred_to", [])}
    observed = ledger.derive_observed(unit_state, "abc", extra)
    available = {**unit_state.get("keys", {}), **extra}
    patterns = ledger.ledger_only_patterns(adapter.cwd)
    history = {"round": 1, "start_head": "base", "reviewed_head": "abc",
               "code_changed": any(not ledger.is_ledger_only(path, patterns) for path in paths),
               "keys_new": [item["key"] for item in observed],
               "keys_remediated": [item["key"] for item in observed
                                    if ledger._terminal(available[item["key"]])],
               "scope_shape_keys": [], "agents_md_chain_new": [],
               "scope_escalated": False, "ledger_only": ledger_only, "observed": observed}
    history_file = tmp_path / f"{unit}-history.json"
    history_file.write_text(json.dumps(history), encoding="utf-8")
    text_file = tmp_path / f"{unit}-summary.txt"
    text_file.write_text("Round complete.", encoding="utf-8")
    call_args = args(change="1", unit=unit, round=1, head="abc", clean=clean,
                     ledger_only=ledger_only, text_file=str(text_file),
                     history_file=str(history_file))
    return ledger.command_summary(call_args, adapter), call_args


def test_full_happy_round_and_verified_resolution(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    _post_one(ledger, adapter, tmp_path)
    ledger.command_reply(args(change="1", key="slice/f001", kind="verified", attr=[],
                              sha="abc", path="src/new.py", line="2", side="new",
                              text="Verified."), adapter)
    with pytest.raises(ledger.LedgerError, match="unresolved"):
        _summarize(ledger, adapter, tmp_path)
        ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                 expected=None, round=1), adapter)
    result = ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), adapter)
    assert result["resolved"]
    assert ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                    expected=None, round=1), adapter)["settled"]


def test_fixed_closure_requires_reachable_sha_and_trailer(tmp_path, monkeypatch):
    ledger = load_module()
    adapter = FakeAdapter()
    _post_one(ledger, adapter, tmp_path)
    ledger.command_reply(args(change="1", key="slice/f001", kind="fixed", attr=[],
                              sha="fixsha", path="src/new.py", line="2", side="new", text="Fixed."), adapter)
    ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), adapter)
    _summarize(ledger, adapter, tmp_path)
    run = type("Run", (), {"returncode": 1, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(ledger.subprocess, "run", lambda *a, **k: run)
    with pytest.raises(ledger.LedgerError, match="not reachable"):
        ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                 expected=None, round=1), adapter)
    calls = iter([type("Run", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
                  type("Run", (), {"returncode": 0, "stdout": "No trailer", "stderr": ""})()])
    monkeypatch.setattr(ledger.subprocess, "run", lambda *a, **k: next(calls))
    with pytest.raises(ledger.LedgerError, match="lacks trailer"):
        ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                 expected=None, round=1), adapter)


def test_product_debt_home_missing_then_present(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    adapter.cwd = tmp_path
    _post_one(ledger, adapter, tmp_path)
    ledger.command_reply(args(change="1", key="slice/f001", kind="dispute", attr=[], text="Dispute."), adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="verdict",
                              attr=[["result", "stands"], ["reason", "Confirmed"]], text="Stands."), adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="disposition",
                              attr=[["result", "product-debt"], ["home", "AGENTS.md"]], text="Debt."), adapter)
    ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), adapter)
    _summarize(ledger, adapter, tmp_path)
    gate = args(change="1", unit="slice", phase="closure", head="abc", expected=None, round=1)
    with pytest.raises(ledger.LedgerError, match="home is missing"):
        ledger.command_gate(gate, adapter)
    (tmp_path / "AGENTS.md").write_text("## Known debt\n\n- item\n  ledger: slice/f001\n", encoding="utf-8")
    assert ledger.command_gate(gate, adapter)["settled"]


def test_deferred_slice_key_is_checked_and_closed_by_feature(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    _post_one(ledger, adapter, tmp_path)
    ledger.command_reply(args(change="1", key="slice/f001", kind="deferred",
                              attr=[["gate", "feature"]], text="Defer."), adapter)
    _summarize(ledger, adapter, tmp_path, unit="feature")
    gate = args(change="1", unit="feature", phase="closure", head="abc", expected=None, round=1)
    with pytest.raises(ledger.LedgerError, match="key is open"):
        ledger.command_gate(gate, adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="verified", attr=[], sha="abc",
                              path="src/new.py", line="2", side="new", text="Verified."), adapter)
    ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), adapter)
    assert ledger.command_gate(gate, adapter)["settled"]


def test_stale_locator_blocks_progress_and_closure(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    _post_one(ledger, adapter, tmp_path)
    ledger.command_reply(args(change="1", key="slice/f001", kind="carried", attr=[], text="Carry."), adapter)
    findings = tmp_path / "stale.json"
    findings.write_text(json.dumps([finding(line=99)]), encoding="utf-8")
    diff = tmp_path / "stale.diff"
    diff.write_text("", encoding="utf-8")
    result = ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                                      head="abc", hints=None, map=None, state=None), adapter)
    assert result["stale_locator"] == 1
    with pytest.raises(ledger.LedgerError, match="missing durable current"):
        ledger.command_gate(args(change="1", unit="slice", phase="progress", head="abc",
                                 expected=str(findings), round=None), adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="disposition",
                              attr=[["result", "pattern-debt"]], text="Debt."), adapter)
    ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), adapter)
    _summarize(ledger, adapter, tmp_path)
    with pytest.raises(ledger.LedgerError, match="no current inline"):
        ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                 expected=None, round=1), adapter)


def test_summary_duplicate_is_idempotent_and_handoff_trusts_prior_author(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter(author="first")
    result, summary_args = _summarize(ledger, adapter, tmp_path)
    assert result["ok"]
    writes = len(adapter.notes)
    assert ledger.command_summary(summary_args, adapter)["idempotent"]
    assert len(adapter.notes) == writes
    adapter.author = "second"
    summary_args.trust = ["first"]
    assert ledger.command_summary(summary_args, adapter)["idempotent"]


def test_canonical_url_selects_moved_origin_and_resolve_closes_every_thread(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    _post_one(ledger, adapter, tmp_path)
    ledger.command_reply(args(change="1", key="slice/f001", kind="dispute", attr=[], text="D"), adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="verdict",
                              attr=[["result", "withdrawn"], ["reason", "R"]], text="V"), adapter)
    findings = tmp_path / "again.json"
    findings.write_text(json.dumps([finding(line=3)]), encoding="utf-8")
    diff = tmp_path / "again.diff"
    diff.write_text("""diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -2,1 +2,2 @@
 same
+new
""", encoding="utf-8")
    ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                             head="abc", hints=None, map=None, state=None), adapter)
    state = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    assert state["location"] == adapter.threads[-1]["url"]
    assert len(state["threads"]) == 2
    ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), adapter)
    assert all(thread["resolved"] for thread in
               ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]["threads"])


def test_move_failure_records_cleanup_result():
    ledger = load_module()
    adapter = FakeAdapter()
    marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                        ledger.normalize_locator(finding()))
    adapter.notes.append(adapter._note(marker, "1"))
    adapter.next_id = 2
    state = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    original = adapter.call
    adapter.call = lambda verb, payload, mode="read": (
        {"ok": False, "reason": "degraded", "cleaned": True} if
        verb == "change-comment" and payload.get("require_inline") else original(verb, payload, mode))
    assert not ledger._move_key(adapter, "1", "slice/f001", state, finding(line=3),
                                ledger.normalize_locator(finding(line=3)), "abc")
    rebuilt = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    assert any(record["kind"] == "move-failed" for record in rebuilt["records"])
    assert ledger.parse_adapter_output('{"error":true,"note":"orphan"}\n', "move")["note"] == "orphan"

    failed_cleanup = FakeAdapter()
    failed_cleanup.notes.append(failed_cleanup._note(marker, "1"))
    failed_cleanup.next_id = 2
    failed_state = ledger.reconstruct_state(failed_cleanup, "1")["units"]["slice"]["keys"]["slice/f001"]
    original_failed = failed_cleanup.call
    failed_cleanup.call = lambda verb, payload, mode="read": (
        {"error": True, "note": "orphan"} if
        verb == "change-comment" and payload.get("require_inline") else original_failed(verb, payload, mode))
    assert not ledger._move_key(failed_cleanup, "1", "slice/f001", failed_state,
                                finding(line=3), ledger.normalize_locator(finding(line=3)), "abc")
    record = ledger.reconstruct_state(failed_cleanup, "1")["units"]["slice"]["keys"]["slice/f001"]["records"][-1]
    assert record["kind"] == "move-failed"
    assert record["note"] == "orphan"


def test_history_keeps_carried_high_blocking_snapshots():
    ledger = load_module()
    adapter = FakeAdapter()
    marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                        ledger.normalize_locator(finding()))
    adapter.notes.append(adapter._note(marker, "1"))
    observed = [{"key": "slice/f001", "concern": "logic-correctness",
                 "severity": "high", "class": "correctness"}]
    for round_number, head in ((1, "abc"), (2, "def")):
        history = {"round": round_number, "start_head": "base" if round_number == 1 else "abc",
                   "reviewed_head": head, "code_changed": round_number == 1,
                   "keys_new": ["slice/f001"] if round_number == 1 else [], "keys_remediated": [],
                   "scope_shape_keys": [], "agents_md_chain_new": [], "scope_escalated": False,
                   "ledger_only": False, "observed": observed}
        body = (f"<!-- afk:settle:summary v1 unit=slice round={round_number} reviewed_head={head} "
                f"clean=false ledger_only=false -->\n\n<!-- afk:settle:history v1 data={ledger.b64(history)} -->")
        adapter.notes.append(adapter._note(body, str(round_number + 1)))
    unit = ledger.reconstruct_state(adapter, "1")["units"]["slice"]
    history = unit["history"]
    assert [entry["observed"][0]["severity"] for entry in history[-2:]] == ["high", "high"]
    assert unit["keys"]["slice/f001"]["routing"]["blocks_ship"]


def test_ledger_only_terminal_round_closes_and_rejects_code_paths(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    item = finding(file="plan/review/report.md")
    _post_one(ledger, adapter, tmp_path, item=item)
    ledger.command_reply(args(change="1", key="slice/f001", kind="verified", attr=[], sha="abc",
                              path=item["file"], line="2", side="new", text="Verified."), adapter)
    ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), adapter)
    _summarize(ledger, adapter, tmp_path, clean=False, ledger_only=True,
               paths=["plan/review/report.md"])
    assert ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                    expected=None, round=1), adapter)["settled"]

    code_adapter = FakeAdapter()
    _post_one(ledger, code_adapter, tmp_path, item=finding())
    ledger.command_reply(args(change="1", key="slice/f001", kind="verified", attr=[], sha="abc",
                              path="src/new.py", line="2", side="new", text="Verified."), code_adapter)
    with pytest.raises(ledger.LedgerError, match="non-ledger"):
        _summarize(ledger, code_adapter, tmp_path, clean=False, ledger_only=True,
                   paths=["src/new.py"])


def test_ledger_only_rejects_withdrawn_code_finding(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    _post_one(ledger, adapter, tmp_path)
    ledger.command_reply(args(change="1", key="slice/f001", kind="dispute", attr=[], text="D"), adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="verdict",
                              attr=[["result", "withdrawn"], ["reason", "R"]], text="V"), adapter)
    with pytest.raises(ledger.LedgerError, match="non-ledger"):
        _summarize(ledger, adapter, tmp_path, clean=False, ledger_only=True,
                   paths=["plan/review/report.md"])


@pytest.mark.parametrize("edited", [False, True], ids=["untrusted", "edited"])
def test_every_stateful_command_fails_closed_before_write(tmp_path, edited):
    ledger = load_module()
    marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                        ledger.normalize_locator(finding()))
    findings = tmp_path / "findings.json"
    findings.write_text("[]", encoding="utf-8")
    diff = tmp_path / "change.diff"
    diff.write_text("", encoding="utf-8")
    history = tmp_path / "history.json"
    history.write_text("{}", encoding="utf-8")
    text_file = tmp_path / "text.txt"
    text_file.write_text("summary", encoding="utf-8")
    expected = tmp_path / "expected.json"
    expected.write_text("[]", encoding="utf-8")
    commands = [
        lambda a: ledger.command_post(args(change="1", unit="slice", findings=str(findings),
                                           diff=str(diff), head="abc", hints=None, map=None, state=None), a),
        lambda a: ledger.command_reply(args(change="1", key="slice/f001", kind="carried",
                                             attr=[], text="Carry."), a),
        lambda a: ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), a),
        lambda a: ledger.command_summary(args(change="1", unit="slice", round=1, head="abc",
                                               clean=True, ledger_only=False, text_file=str(text_file),
                                               history_file=str(history)), a),
        lambda a: ledger.command_gate(args(change="1", unit="slice", phase="progress", head="abc",
                                            expected=str(expected), round=None), a),
    ]
    for command in commands:
        adapter = FakeAdapter(author="current")
        note = adapter._note(marker, "1")
        if edited:
            note["updated_at"] = "2026-01-01T00:01:00Z"
        else:
            note["author"] = "foreign"
        adapter.notes.append(note)
        before = len(adapter.calls)
        with pytest.raises(ledger.LedgerError, match="edited_markers|unclassified_authors"):
            command(adapter)
        assert not any(verb in {"change-comment", "thread-reply", "thread-resolve"}
                       for verb, _ in adapter.calls[before:])


def test_adapter_seam_passes_environment_and_rejects_bad_process_output(monkeypatch, tmp_path):
    ledger = load_module()
    captured = {}

    def run(command, **kwargs):
        captured.update(command=command, kwargs=kwargs)
        return type("Run", (), {"returncode": 0, "stdout": '{"notes":[],"count":0}\n', "stderr": ""})()

    monkeypatch.setenv("AFK_LEDGER_ADAPTER_CMD", "stub --flag")
    monkeypatch.setattr(ledger.subprocess, "run", run)
    adapter = ledger.Adapter(cwd=tmp_path)
    assert adapter.call("note-list", {"id": "7"})["count"] == 0
    assert captured["command"] == ["stub", "--flag", "note-list"]
    assert json.loads(captured["kwargs"]["input"]) == {"id": "7"}
    assert captured["kwargs"]["env"]["AFK_PLUGIN_ROOT"] == str(adapter.root)

    monkeypatch.setattr(ledger.subprocess, "run", lambda *a, **k:
                        type("Run", (), {"returncode": 0, "stdout": '{}\nnoise\n', "stderr": ""})())
    with pytest.raises(ledger.LedgerError, match="extra stdout"):
        adapter.call("note-list", {"id": "7"})
    monkeypatch.setattr(ledger.subprocess, "run", lambda *a, **k:
                        type("Run", (), {"returncode": 9, "stdout": "", "stderr": "failed"})())
    with pytest.raises(ledger.LedgerError, match="failed"):
        adapter.call("note-list", {"id": "7"})


@pytest.mark.parametrize("outcome", ["carried", "deferred", "withdrawn", "disposition"])
def test_same_head_latest_seen_is_retry_for_every_reusable_outcome(tmp_path, outcome):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / f"{outcome}.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / f"{outcome}.diff"
    diff.write_text("", encoding="utf-8")
    post = args(change="1", unit="slice", findings=str(findings), diff=str(diff), head="abc",
                hints=None, map=None, state=None)
    ledger.command_post(post, adapter)
    if outcome == "carried":
        ledger.command_reply(args(change="1", key="slice/f001", kind="carried", attr=[], text="C"), adapter)
    elif outcome == "deferred":
        ledger.command_reply(args(change="1", key="slice/f001", kind="deferred",
                                  attr=[["gate", "feature"]], text="D"), adapter)
    elif outcome == "withdrawn":
        ledger.command_reply(args(change="1", key="slice/f001", kind="dispute", attr=[], text="D"), adapter)
        ledger.command_reply(args(change="1", key="slice/f001", kind="verdict",
                                  attr=[["result", "withdrawn"], ["reason", "R"]], text="V"), adapter)
    else:
        ledger.command_reply(args(change="1", key="slice/f001", kind="disposition",
                                  attr=[["result", "pattern-debt"]], text="D"), adapter)
    ledger.command_post(post, adapter)
    before = len([call for call in adapter.calls if call[0] in {"change-comment", "thread-reply"}])
    seq = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]["seq"]
    ledger.command_post(post, adapter)
    after = len([call for call in adapter.calls if call[0] in {"change-comment", "thread-reply"}])
    assert after == before
    assert ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]["seq"] == seq


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/acme/repo/pull/7", "https://github.com/acme/repo/blob/abc/src/new.py#L2"),
    ("https://gitlab.example/acme/repo/-/merge_requests/7",
     "https://gitlab.example/acme/repo/-/blob/abc/src/new.py#L2"),
])
def test_reply_reports_target_project_blob_fallback(url, expected):
    ledger = load_module()
    adapter = FakeAdapter()
    adapter.view_overrides = {"blob_base": "", "url": url}
    marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                        ledger.normalize_locator(finding()))
    adapter.notes.append(adapter._note(marker, "1"))
    adapter.next_id = 2
    result = ledger.command_reply(args(change="1", key="slice/f001", kind="verified", attr=[],
                                       sha="abc", path="src/new.py", line="2", side="new",
                                       text="Verified."), adapter)
    assert result["permalink"] == expected
    assert result["target_project_fallback"] is True


def test_terminal_reclassified_record_is_rejected():
    ledger = load_module()
    with pytest.raises(ledger.LedgerError, match="terminal"):
        ledger.validate_transition({"kind": "disposition", "attrs": {"result": "pattern-debt"}},
                                   "reclassified", {"data": ledger.b64(finding())})
    adapter = FakeAdapter()
    origin = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                        ledger.normalize_locator(finding()))
    disposition = ledger.make_record_marker("slice/f001", 2, "disposition",
                                             {"result": "pattern-debt"}, 1)
    reclassified = ledger.make_record_marker("slice/f001", 3, "reclassified",
                                              {"data": ledger.b64(finding(severity="medium"))}, 2)
    adapter.notes.extend([adapter._note(origin, "1"), adapter._note(disposition, "2"),
                          adapter._note(reclassified, "3")])
    with pytest.raises(ledger.LedgerError, match="terminal"):
        ledger.reconstruct_state(adapter, "1")


def _seed_pending_move(ledger, adapter, key="slice/f001", item=None):
    item = item or finding()
    origin = ledger.make_finding_marker(key, key.rsplit("/f", 1)[0], "abc", item,
                                        ledger.normalize_locator(item))
    adapter.call("change-comment", {"id": "1", "text": origin, **ledger.normalize_locator(item)}, "write")
    key_state = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"][key]
    _, intent = ledger._record(adapter, "1", key_state, key, "move-intent",
                               {"to": ledger.b64(ledger.normalize_locator(finding(line=3)))}, "Move.")
    moved = ledger.make_finding_marker(key, "slice", "abc", finding(line=3),
                                       ledger.normalize_locator(finding(line=3)),
                                       moved_from=ledger.parse_marker(intent)["op"])
    adapter.call("change-comment", {"id": "1", "text": moved,
                                     **ledger.normalize_locator(finding(line=3))}, "write")
    adapter.threads[-1]["notes"][0]["created_at"] = "2026-01-01T00:00:01Z"
    adapter.threads[-1]["notes"][0]["updated_at"] = "2026-01-01T00:00:01Z"
    assert ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"][key]["pending_move"]


def test_post_repairs_unrelated_pending_move_before_new_write(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    _seed_pending_move(ledger, adapter)
    findings = tmp_path / "unrelated.json"
    findings.write_text(json.dumps([finding(id="new", finding="Unrelated issue.")]), encoding="utf-8")
    diff = tmp_path / "unrelated.diff"
    diff.write_text("", encoding="utf-8")
    before = len(adapter.calls)
    ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                             head="abc", hints=None, map=None, state=None), adapter)
    writes = [verb for verb, _ in adapter.calls[before:]
              if verb in {"change-comment", "thread-reply", "thread-resolve"}]
    assert writes[0] == "thread-reply"
    assert not ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]["pending_move"]


def test_resolve_and_summary_repair_unrelated_pending_move(tmp_path):
    ledger = load_module()
    for command_name in ("resolve", "summary"):
        adapter = FakeAdapter()
        _seed_pending_move(ledger, adapter)
        second = finding(id="second", finding="Second issue.")
        marker = ledger.make_finding_marker("slice/f002", "slice", "abc", second,
                                            ledger.normalize_locator(second))
        adapter.notes.append(adapter._note(marker, adapter._id()))
        if command_name == "resolve":
            ledger.command_resolve(args(change="1", key="slice/f002", reopen=False), adapter)
        else:
            ledger.changed_paths = lambda cwd, start, end: []
            state = ledger.reconstruct_state(adapter, "1")["units"]["slice"]
            observed = ledger.derive_observed(state, "abc")
            history = {"round": 1, "start_head": "base", "reviewed_head": "abc",
                       "code_changed": False, "keys_new": [item["key"] for item in observed],
                       "keys_remediated": [], "scope_shape_keys": [], "agents_md_chain_new": [],
                       "scope_escalated": False, "ledger_only": False, "observed": observed}
            history_file = tmp_path / f"{command_name}.json"
            history_file.write_text(json.dumps(history), encoding="utf-8")
            text_file = tmp_path / f"{command_name}.txt"
            text_file.write_text("Round.", encoding="utf-8")
            ledger.command_summary(args(change="1", unit="slice", round=1, head="abc", clean=False,
                                        ledger_only=False, text_file=str(text_file),
                                        history_file=str(history_file)), adapter)
        assert not ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]["pending_move"]


def test_progress_rejects_changed_routing_when_post_was_skipped(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "routing.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "routing.diff"
    diff.write_text("", encoding="utf-8")
    post = args(change="1", unit="slice", findings=str(findings), diff=str(diff), head="abc",
                hints=None, map=None, state=None)
    ledger.command_post(post, adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="carried", attr=[], text="Carry."), adapter)
    ledger.command_post(post, adapter)
    findings.write_text(json.dumps([finding(severity="medium")]), encoding="utf-8")
    with pytest.raises(ledger.LedgerError, match="missing durable"):
        ledger.command_gate(args(change="1", unit="slice", phase="progress", head="abc",
                                 expected=str(findings), round=None), adapter)


@pytest.mark.parametrize("item,diff_text", [
    (finding(file="src/new.py", line=2, side="old"), """diff --git a/src/old.py b/src/new.py
similarity index 90%
rename from src/old.py
rename to src/new.py
--- a/src/old.py
+++ b/src/new.py
@@ -1,2 +1,1 @@
 same
-old
"""),
    (finding(file="src/new.py", line=10, side="context"), """diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -7,1 +10,1 @@
 same
"""),
])
def test_diff_resolved_locator_posts_and_passes_progress(tmp_path, item, diff_text):
    ledger = load_module()
    adapter = FakeAdapter()
    adapter.diff = diff_text
    findings = tmp_path / "resolved.json"
    findings.write_text(json.dumps([item]), encoding="utf-8")
    diff = tmp_path / "resolved.diff"
    diff.write_text(diff_text, encoding="utf-8")
    ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                             head="abc", hints=None, map=None, state=None), adapter)
    payload = next(payload for verb, payload in adapter.calls if verb == "change-comment")
    state = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    assert state["finding"] == item
    assert state["routing"]["severity"] == item["severity"]
    assert state["locator_current"]
    assert state["old_path"] == payload["old_path"]
    assert state["old_line"] == payload["old_line"]
    assert ledger.command_gate(args(change="1", unit="slice", phase="progress", head="abc",
                                    expected=str(findings), round=None), adapter)["ok"]


@pytest.mark.parametrize("item,hint,diff_text,expected", [
    (finding(file="src/new.py", line=9, side="context"), {"line": 10}, """diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -7,1 +10,1 @@
 same
""", {"line": 10, "old_line": 7, "old_path": "src/new.py"}),
    (finding(file="src/new.py", line=99, side="old"), {"line": 2}, """diff --git a/src/old.py b/src/new.py
similarity index 90%
rename from src/old.py
rename to src/new.py
--- a/src/old.py
+++ b/src/new.py
@@ -1,2 +1,1 @@
 same
-old
""", {"old_line": 2, "old_path": "src/old.py"}),
])
def test_hint_uses_diff_resolved_locator(tmp_path, item, hint, diff_text, expected):
    ledger = load_module()
    adapter = FakeAdapter()
    adapter.diff = diff_text
    findings = tmp_path / "hint-findings.json"
    findings.write_text(json.dumps([item]), encoding="utf-8")
    diff = tmp_path / "hint.diff"
    diff.write_text(diff_text, encoding="utf-8")
    hints = tmp_path / "hints.json"
    hints.write_text(json.dumps([hint]), encoding="utf-8")
    ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                             head="abc", hints=str(hints), map=None, state=None), adapter)
    payload = next(payload for verb, payload in adapter.calls if verb == "change-comment")
    for name, value in expected.items():
        assert payload[name] == value
    state = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    assert state["finding"] == item
    assert state["routing"]["severity"] == item["severity"]
    assert state["locator_current"]
    for name, value in expected.items():
        assert state[name] == value
    assert ledger.command_gate(args(change="1", unit="slice", phase="progress", head="abc",
                                    expected=str(findings), round=None), adapter)["ok"]


def test_proxy_hint_cannot_change_target_and_stays_unanchored(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    item = finding(file="src/proxy.py", line=99)
    findings = tmp_path / "proxy.json"
    findings.write_text(json.dumps([item]), encoding="utf-8")
    diff = tmp_path / "proxy.diff"
    diff.write_text("""diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -1,1 +1,2 @@
 same
+new
""", encoding="utf-8")
    hints = tmp_path / "proxy-hints.json"
    hints.write_text(json.dumps([{"file": "src/new.py", "line": 2}]), encoding="utf-8")
    result = ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                                      head="abc", hints=str(hints), map=None, state=None), adapter)
    assert result["unanchored"] == 1
    payload = next(payload for verb, payload in adapter.calls if verb == "change-comment")
    assert "line" not in payload


def test_identical_feature_retry_writes_no_second_seen(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "feature-retry.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "feature-retry.diff"
    diff.write_text("", encoding="utf-8")
    ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                             head="abc", hints=None, map=None, state=None), adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="deferred",
                              attr=[["gate", "feature"]], text="Defer."), adapter)
    feature = args(change="1", unit="feature", findings=str(findings), diff=str(diff),
                   head="abc", hints=None, map=None, state=None)
    ledger.command_post(feature, adapter)
    before = len([call for call in adapter.calls if call[0] in {"thread-reply", "change-comment"}])
    before_seq = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]["seq"]
    ledger.command_post(feature, adapter)
    assert len([call for call in adapter.calls if call[0] in {"thread-reply", "change-comment"}]) == before
    after = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    assert after["seq"] == before_seq
    assert after["finding"] == finding()
    assert after["locator_current"]


@pytest.mark.parametrize("kind,data", [("seen", []), ("reclassified", "bad")])
def test_main_returns_exit_2_for_non_object_record_data(kind, data, monkeypatch, capsys):
    ledger = load_module()
    adapter = FakeAdapter()
    origin = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                        ledger.normalize_locator(finding()))
    attrs = ({"head": "abc", "data": ledger.b64(data), "file": "src/new.py",
              "old_path": "src/new.py", "new_path": "src/new.py", "line": 2,
              "old_line": None, "side": "new"} if kind == "seen" else {"data": ledger.b64(data)})
    record = ledger.make_record_marker("slice/f001", 2, kind, attrs, 1)
    adapter.notes.extend([adapter._note(origin, "1"), adapter._note(record, "2")])
    monkeypatch.setattr(ledger, "Adapter", lambda: adapter)
    assert ledger.main(["reconstruct", "--change", "1"]) == 2
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_fallback_statement_is_published_for_both_forges():
    ledger = load_module()
    for url in ("https://github.com/acme/repo/pull/7",
                "https://gitlab.example/acme/repo/-/merge_requests/7"):
        adapter = FakeAdapter()
        adapter.view_overrides = {"blob_base": "", "url": url}
        marker = ledger.make_finding_marker("slice/f001", "slice", "abc", finding(),
                                            ledger.normalize_locator(finding()))
        adapter.notes.append(adapter._note(marker, "1"))
        adapter.next_id = 2
        ledger.command_reply(args(change="1", key="slice/f001", kind="verified", attr=[], sha="abc",
                                  path="src/new.py", line="2", side="new", text="Verified."), adapter)
        body = next(payload["text"] for verb, payload in adapter.calls if verb in {"thread-reply", "change-comment"})
        assert "target project" in body.lower()


@pytest.mark.parametrize("field,value", [
    *((field, None) for field in ("url", "head_sha", "base_sha", "head_ref", "blob_base", "cross_fork")),
    *((field, "false" if field == "cross_fork" else 7)
      for field in ("url", "head_sha", "base_sha", "head_ref", "blob_base", "cross_fork")),
])
def test_change_view_requires_all_consumed_fields_and_types(field, value, monkeypatch):
    ledger = load_module()
    answer = {"url": "https://f/change/1", "head_sha": "a", "base_sha": "b",
              "head_ref": "topic", "blob_base": "https://f/blob", "cross_fork": False}
    if value is None:
        answer.pop(field)
    else:
        answer[field] = value
    run = type("Run", (), {"returncode": 0, "stdout": json.dumps(answer) + "\n", "stderr": ""})()
    monkeypatch.setenv("AFK_LEDGER_ADAPTER_CMD", "stub")
    monkeypatch.setattr(ledger.subprocess, "run", lambda *a, **k: run)
    with pytest.raises(ledger.LedgerError):
        ledger.Adapter().call("change-view", {"id": "1"})


@pytest.mark.parametrize("failure", ["bad-map", "ambiguous"])
def test_post_validates_all_matches_before_pending_repair(tmp_path, failure):
    ledger = load_module()
    adapter = FakeAdapter()
    _seed_pending_move(ledger, adapter)
    if failure == "ambiguous":
        second = ledger.make_finding_marker("slice/f002", "slice", "abc", finding(),
                                            ledger.normalize_locator(finding()))
        adapter.notes.append(adapter._note(second, adapter._id()))
    findings = tmp_path / f"{failure}.json"
    findings.write_text(json.dumps([finding(line=4)]), encoding="utf-8")
    diff = tmp_path / f"{failure}.diff"
    diff.write_text("", encoding="utf-8")
    mapping = None
    if failure == "bad-map":
        mapping = tmp_path / "bad-map-input.json"
        mapping.write_text(json.dumps({"0": "slice/f999"}), encoding="utf-8")
    before = len(adapter.calls)
    with pytest.raises(ledger.LedgerError, match="unknown key|ambiguous sfp"):
        ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                                 head="abc", hints=None, map=str(mapping) if mapping else None,
                                 state=None), adapter)
    assert not any(verb in {"change-comment", "thread-reply", "thread-resolve"}
                   for verb, _ in adapter.calls[before:])
    assert ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]["pending_move"]


def test_closure_rejects_pending_move_after_valid_summary():
    ledger = load_module()
    adapter = FakeAdapter()
    _seed_pending_move(ledger, adapter)
    _add_clean_summary(ledger, adapter)
    with pytest.raises(ledger.LedgerError, match="incomplete move"):
        ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                 expected=None, round=1), adapter)


def test_closure_rejects_summary_head_round_mismatch_and_nonclean_summary():
    ledger = load_module()
    for summary_head, requested_round in (("abc", 2), ("def", 1)):
        adapter = FakeAdapter()
        _add_clean_summary(ledger, adapter, head=summary_head, round_number=1)
        with pytest.raises(ledger.LedgerError, match="requested final head and round"):
            ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                     expected=None, round=requested_round), adapter)
    adapter = FakeAdapter()
    history = {"round": 1, "start_head": "base", "reviewed_head": "abc", "code_changed": False,
               "keys_new": [], "keys_remediated": [], "scope_shape_keys": [],
               "agents_md_chain_new": [], "scope_escalated": False, "ledger_only": False,
               "observed": []}
    body = ("<!-- afk:settle:summary v1 unit=slice round=1 reviewed_head=abc "
            "clean=false ledger_only=false -->\n\n"
            f"<!-- afk:settle:history v1 data={ledger.b64(history)} -->")
    adapter.notes.append(adapter._note(body, "1"))
    with pytest.raises(ledger.LedgerError, match="neither clean nor ledger-only"):
        ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                 expected=None, round=1), adapter)


def test_cli_paths_for_post_resolve_and_summary(tmp_path, monkeypatch, capsys):
    ledger = load_module()
    adapter = FakeAdapter()
    monkeypatch.setattr(ledger, "Adapter", lambda: adapter)
    findings = tmp_path / "cli-findings.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "cli.diff"
    diff.write_text("", encoding="utf-8")
    assert ledger.main(["post", "--change", "1", "--unit", "slice", "--findings", str(findings),
                        "--diff", str(diff), "--head", "abc"]) == 0
    assert ledger.main(["resolve", "--change", "1", "--key", "slice/f001"]) == 0
    empty_adapter = FakeAdapter()
    monkeypatch.setattr(ledger, "Adapter", lambda: empty_adapter)
    ledger.changed_paths = lambda cwd, start, end: []
    history = tmp_path / "cli-history.json"
    history.write_text(json.dumps({"round": 1, "start_head": "base", "reviewed_head": "abc",
                                   "code_changed": False, "keys_new": [], "keys_remediated": [],
                                   "scope_shape_keys": [], "agents_md_chain_new": [],
                                   "scope_escalated": False, "ledger_only": False,
                                   "observed": []}), encoding="utf-8")
    text_file = tmp_path / "cli-summary.txt"
    text_file.write_text("Summary.", encoding="utf-8")
    assert ledger.main(["summary", "--change", "1", "--unit", "slice", "--round", "1",
                        "--head", "abc", "--clean", "true", "--ledger-only", "false",
                        "--text-file", str(text_file), "--history-file", str(history)]) == 0
    capsys.readouterr()


@pytest.mark.parametrize("unit,settles", [("slice", True), ("change", False), ("feature", False)])
def test_closure_allows_deferred_only_for_slice_units(tmp_path, unit, settles):
    ledger = load_module()
    adapter = FakeAdapter()
    _post_one(ledger, adapter, tmp_path, unit=unit)
    key = f"{unit}/f001"
    ledger.command_reply(args(change="1", key=key, kind="deferred",
                              attr=[["gate", "feature"]], text="Defer."), adapter)
    _summarize(ledger, adapter, tmp_path, unit=unit)
    gate = args(change="1", unit=unit, phase="closure", head="abc", expected=None, round=1)
    if settles:
        assert ledger.command_gate(gate, adapter)["settled"]
    else:
        with pytest.raises(ledger.LedgerError, match="key is open"):
            ledger.command_gate(gate, adapter)


def test_retry_uses_current_routing_not_historical_seen(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "routing-cycle.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "routing-cycle.diff"
    diff.write_text("", encoding="utf-8")
    post = args(change="1", unit="slice", findings=str(findings), diff=str(diff), head="abc",
                hints=None, map=None, state=None)
    ledger.command_post(post, adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="carried", attr=[], text="Carry."), adapter)
    ledger.command_post(post, adapter)
    findings.write_text(json.dumps([finding(severity="medium")]), encoding="utf-8")
    ledger.command_post(post, adapter)
    before = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]["seq"]
    findings.write_text(json.dumps([finding(severity="high")]), encoding="utf-8")
    ledger.command_post(post, adapter)
    current = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    assert current["seq"] > before
    assert current["routing"]["severity"] == "high"
    assert current["finding"]["severity"] == "high"


def test_retry_uses_current_locator_not_historical_seen(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "locator-cycle.json"
    findings.write_text(json.dumps([finding(line=2)]), encoding="utf-8")
    diff = tmp_path / "locator-cycle.diff"
    diff.write_text("""diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -1,1 +1,2 @@
 same
+new
""", encoding="utf-8")
    post = args(change="1", unit="slice", findings=str(findings), diff=str(diff), head="abc",
                hints=None, map=None, state=None)
    ledger.command_post(post, adapter)
    ledger.command_reply(args(change="1", key="slice/f001", kind="carried", attr=[], text="Carry."), adapter)
    findings.write_text(json.dumps([finding(line=3)]), encoding="utf-8")
    diff.write_text("""diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -2,1 +2,2 @@
 same
+new
""", encoding="utf-8")
    ledger.command_post(post, adapter)
    before = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]["seq"]
    findings.write_text(json.dumps([finding(line=2)]), encoding="utf-8")
    diff.write_text("""diff --git a/src/new.py b/src/new.py
--- a/src/new.py
+++ b/src/new.py
@@ -1,1 +1,2 @@
 same
+new
""", encoding="utf-8")
    ledger.command_post(post, adapter)
    current = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    assert current["seq"] > before
    assert current["line"] == 2
    assert current["locator_current"]


@pytest.mark.parametrize("path,pattern", [
    ("README.md", "**/*.md"),
    ("plan/review/a.json", "plan/**/review/*.json"),
    ("plan/x/y/review/a.json", "plan/**/review/*.json"),
])
def test_double_star_matches_zero_or_more_path_segments(path, pattern):
    ledger = load_module()
    assert ledger.is_ledger_only(path, [pattern])


def test_transition_matrix_covers_every_outcome_pair():
    ledger = load_module()
    previous = {
        "none": None,
        "carried": {"kind": "carried", "attrs": {}},
        "dispute": {"kind": "dispute", "attrs": {}},
        "stands": {"kind": "verdict", "attrs": {"result": "stands"}},
        "withdrawn": {"kind": "verdict", "attrs": {"result": "withdrawn"}},
        "deferred": {"kind": "deferred", "attrs": {"gate": "feature"}},
        "fixed": {"kind": "fixed", "attrs": {}},
        "verified": {"kind": "verified", "attrs": {}},
        "pattern-disposition": {"kind": "disposition", "attrs": {"result": "pattern-debt"}},
        "product-disposition": {"kind": "disposition", "attrs": {"result": "product-debt"}},
    }
    transitions = {
        "dispute": ("dispute", {}),
        "withdraw": ("verdict", {"result": "withdrawn", "reason": "r"}),
        "stand": ("verdict", {"result": "stands", "reason": "r"}),
        "fixed": ("fixed", {"sha": "a", "path": "a", "line": 1, "side": "new"}),
        "verified": ("verified", {"sha": "a", "path": "a", "line": 1, "side": "new"}),
        "carried": ("carried", {}),
        "deferred": ("deferred", {"gate": "feature"}),
        "pattern-disposition": ("disposition", {"result": "pattern-debt"}),
        "product-disposition": ("disposition", {"result": "product-debt", "home": "AGENTS.md"}),
    }
    allowed = {
        "none": {"dispute", "fixed", "verified", "carried", "deferred", "pattern-disposition"},
        "carried": {"dispute", "fixed", "verified", "carried", "deferred", "pattern-disposition"},
        "dispute": {"withdraw", "stand"},
        "stands": {"dispute", "fixed", "verified", "carried", "product-disposition"},
        "deferred": {"dispute", "fixed", "verified", "carried", "pattern-disposition"},
        "withdrawn": set(), "fixed": set(), "verified": set(),
        "pattern-disposition": set(), "product-disposition": set(),
    }
    for state, prior in previous.items():
        for name, (kind, attrs) in transitions.items():
            if name in allowed[state]:
                ledger.validate_transition(prior, kind, attrs)
            else:
                with pytest.raises((ledger.LedgerError, ledger.UsageError),
                                   match="illegal|requires|only become"):
                    ledger.validate_transition(prior, kind, attrs)
    with pytest.raises(ledger.LedgerError):
        ledger.validate_transition(previous["dispute"], "fixed", transitions["fixed"][1])
    with pytest.raises(ledger.LedgerError):
        ledger.validate_transition(previous["stands"], "deferred", transitions["deferred"][1])


@pytest.mark.parametrize("item,diff_text,expected_old", [
    (finding(file="docs/a b.md", line=1, side="context"), """diff --git a/docs/a b.md b/docs/a b.md
--- a/docs/a b.md\t2026-01-01 00:00:00 +0000
+++ b/docs/a b.md\t2026-01-01 00:00:00 +0000
@@ -1,1 +1,1 @@
 same
""", "docs/a b.md"),
    (finding(file="docs/café.md", line=1, side="context"), """diff --git "a/docs/caf\\303\\251.md" "b/docs/caf\\303\\251.md"
--- "a/docs/caf\\303\\251.md"
+++ "b/docs/caf\\303\\251.md"
@@ -1,1 +1,1 @@
 same
""", "docs/café.md"),
    (finding(file="docs/new é.md", line=1, side="old"), """diff --git "a/docs/old \\303\\251.md" "b/docs/new \\303\\251.md"
similarity index 80%
rename from "docs/old \\303\\251.md"
rename to "docs/new \\303\\251.md"
--- "a/docs/old \\303\\251.md"
+++ "b/docs/new \\303\\251.md"
@@ -1,1 +1,1 @@
-old
+new
""", "docs/old é.md"),
])
def test_complex_git_paths_complete_post_to_closure(tmp_path, item, diff_text, expected_old):
    ledger = load_module()
    adapter = FakeAdapter()
    adapter.diff = diff_text
    findings = tmp_path / "complex-path.json"
    findings.write_text(json.dumps([item], ensure_ascii=False), encoding="utf-8")
    diff = tmp_path / "complex-path.diff"
    diff.write_text(diff_text, encoding="utf-8")
    posted = ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                                      head="abc", hints=None, map=None, state=None), adapter)
    assert posted["anchored"] == 1
    state = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    assert state["finding"] == item
    assert state["old_path"] == expected_old
    assert state["locator_current"]
    assert ledger.command_gate(args(change="1", unit="slice", phase="progress", head="abc",
                                    expected=str(findings), round=None), adapter)["ok"]
    ledger.command_reply(args(change="1", key="slice/f001", kind="verified", attr=[], sha="abc",
                              path=item["file"], line=str(item["line"]), side=item["side"],
                              text="Verified."), adapter)
    ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), adapter)
    _summarize(ledger, adapter, tmp_path)
    assert ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                    expected=None, round=1), adapter)["settled"]


def test_diff_parser_preserves_dev_null_add_and_delete_paths():
    ledger = load_module()
    added = ledger.parse_diff("""diff --git a/new file.md b/new file.md
--- /dev/null
+++ b/new file.md
@@ -0,0 +1,1 @@
+new
""")
    assert ("new file.md", 1, "new") in added
    deleted = ledger.parse_diff("""diff --git a/old file.md b/old file.md
--- a/old file.md
+++ /dev/null
@@ -1,1 +0,0 @@
-old
""")
    assert ("old file.md", 1, "old") in deleted


@pytest.mark.parametrize(("item", "removed", "added"), [
    (finding(file="src/prefix.txt", line=1, side="old"), "-- x", "new"),
    (finding(file="src/prefix.txt", line=1, side="new"), "old", "++ x"),
])
def test_hunk_lines_that_resemble_file_headers_complete_post_to_closure(
        tmp_path, item, removed, added):
    ledger = load_module()
    adapter = FakeAdapter()
    diff_text = ("diff --git a/src/prefix.txt b/src/prefix.txt\n"
                 "--- a/src/prefix.txt\n"
                 "+++ b/src/prefix.txt\n"
                 "@@ -1 +1 @@\n"
                 f"-{removed}\n"
                 f"+{added}\n")
    adapter.diff = diff_text
    findings = tmp_path / "prefix-findings.json"
    findings.write_text(json.dumps([item]), encoding="utf-8")
    diff = tmp_path / "prefix.diff"
    diff.write_text(diff_text, encoding="utf-8")
    posted = ledger.command_post(
        args(change="1", unit="slice", findings=str(findings), diff=str(diff),
             head="abc", hints=None, map=None, state=None), adapter)
    assert posted["anchored"] == 1
    state = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    assert state["file"] == "src/prefix.txt"
    assert state["locator_current"]
    assert ledger.command_gate(args(change="1", unit="slice", phase="progress", head="abc",
                                    expected=str(findings), round=None), adapter)["ok"]
    ledger.command_reply(args(change="1", key="slice/f001", kind="verified", attr=[], sha="abc",
                              path=item["file"], line=str(item["line"]), side=item["side"],
                              text="Verified."), adapter)
    ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), adapter)
    _summarize(ledger, adapter, tmp_path)
    assert ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                    expected=None, round=1), adapter)["settled"]


def test_leading_space_rename_completes_old_side_post_to_closure(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    diff_text = ("diff --git a/ old.txt b/ new.txt\n"
                 "similarity index 50%\n"
                 "rename from  old.txt\n"
                 "rename to  new.txt\n"
                 "--- a/ old.txt\n"
                 "+++ b/ new.txt\n"
                 "@@ -1 +1 @@\n"
                 "-old\n"
                 "+new\n")
    adapter.diff = diff_text
    item = finding(file=" new.txt", line=1, side="old")
    findings = tmp_path / "leading-space.json"
    findings.write_text(json.dumps([item]), encoding="utf-8")
    diff = tmp_path / "leading-space.diff"
    diff.write_text(diff_text, encoding="utf-8")

    posted = ledger.command_post(
        args(change="1", unit="slice", findings=str(findings), diff=str(diff),
             head="abc", hints=None, map=None, state=None), adapter)
    assert posted["anchored"] == 1
    state = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    assert state["file"] == " old.txt"
    assert state["old_path"] == " old.txt"
    assert state["new_path"] == " new.txt"
    assert state["locator_current"]
    assert ledger.command_gate(args(change="1", unit="slice", phase="progress", head="abc",
                                    expected=str(findings), round=None), adapter)["ok"]
    ledger.command_reply(args(change="1", key="slice/f001", kind="verified", attr=[], sha="abc",
                              path=" old.txt", line="1", side="old", text="Verified."), adapter)
    ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), adapter)
    _summarize(ledger, adapter, tmp_path)
    assert ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                    expected=None, round=1), adapter)["settled"]


def test_supplied_quoted_utf8_probe_completes_post_to_closure(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    diff_text = ('diff --git "a/q\\303\\251.md" "b/q\\303\\251.md"\n'
                 'new file mode 100644\n--- /dev/null\n+++ "b/q\\303\\251.md"\n'
                 '@@ -0,0 +1 @@\n+z\n')
    adapter.diff = diff_text
    item = finding(file="qé.md", line=1, side="new")
    findings = tmp_path / "quoted-probe.json"
    findings.write_text(json.dumps([item], ensure_ascii=False), encoding="utf-8")
    diff = tmp_path / "quoted-probe.diff"
    diff.write_text(diff_text, encoding="utf-8")
    posted = ledger.command_post(args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                                      head="abc", hints=None, map=None, state=None), adapter)
    assert posted["anchored"] == 1
    state = ledger.reconstruct_state(adapter, "1")["units"]["slice"]["keys"]["slice/f001"]
    assert state["file"] == "qé.md"
    assert state["new_path"] == "qé.md"
    assert state["locator_current"]
    assert ledger.command_gate(args(change="1", unit="slice", phase="progress", head="abc",
                                    expected=str(findings), round=None), adapter)["ok"]
    ledger.command_reply(args(change="1", key="slice/f001", kind="verified", attr=[], sha="abc",
                              path="qé.md", line="1", side="new", text="Verified."), adapter)
    ledger.command_resolve(args(change="1", key="slice/f001", reopen=False), adapter)
    _summarize(ledger, adapter, tmp_path)
    assert ledger.command_gate(args(change="1", unit="slice", phase="closure", head="abc",
                                    expected=None, round=1), adapter)["settled"]


def test_git_quoted_path_decodes_standard_c_escapes():
    ledger = load_module()
    decoded, tail = ledger._decode_git_quoted_path(r'"a\t\n\"\\\a\b\f\r\v" tail')
    assert decoded == "a\t\n\"\\\a\b\f\r\v"
    assert tail == " tail"


def test_git_quoted_path_encodes_unescaped_unicode_before_decoding():
    ledger = load_module()
    decoded, tail = ledger._decode_git_quoted_path('"qé\\"x.md" rest')
    assert decoded == 'qé"x.md'
    assert tail == " rest"


def test_command_post_rejects_invalid_utf8_path_before_adapter_write(tmp_path):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "invalid-utf8.diff"
    diff.write_text('diff --git "a/bad-\\377" "b/bad-\\377"\n', encoding="utf-8")

    with pytest.raises(ledger.UsageError, match="valid UTF-8"):
        ledger.command_post(
            args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                 head="abc", hints=None, map=None, state=None), adapter)

    assert not [verb for verb, _ in adapter.calls
                if verb in {"change-comment", "thread-reply", "thread-resolve"}]


@pytest.mark.parametrize(("header", "message"), [
    (r'diff --git "a/src\q.py" "b/src.py"', "unknown Git path escape"),
    ('diff --git "a/src\\', "unterminated Git path escape"),
    (r'diff --git "a/src\400.py" "b/src.py"', "out of byte range"),
    ('diff --git "a/src.py" "b/src.py" garbage', "trailing diff header text"),
])
def test_command_post_rejects_malformed_git_paths_before_adapter_write(
        tmp_path, header, message):
    ledger = load_module()
    adapter = FakeAdapter()
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([finding()]), encoding="utf-8")
    diff = tmp_path / "malformed.diff"
    diff.write_text(header + "\n", encoding="utf-8")

    with pytest.raises(ledger.UsageError, match=message):
        ledger.command_post(
            args(change="1", unit="slice", findings=str(findings), diff=str(diff),
                 head="abc", hints=None, map=None, state=None), adapter)

    assert not [verb for verb, _ in adapter.calls
                if verb in {"change-comment", "thread-reply", "thread-resolve"}]

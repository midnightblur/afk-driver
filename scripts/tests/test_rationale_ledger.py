"""Change rationale: pending entries, the batch receipt, and the resolver.

Real git repositories in temp directories, a bare repository as the remote, and
a fake forge that answers the adapter verbs. Nothing reaches a real forge.
"""
import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parents[2] / "skills" / "afk" / "review" / "scripts" / "forge_ledger.py"


def load_module():
    spec = importlib.util.spec_from_file_location("forge_ledger_rationale", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ledger = load_module()


def git(cwd, *arguments):
    return subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=t@example.test",
         "-c", "commit.gpgsign=false", *arguments],
        cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


TAIL = "".join(f"// tail {n}" + chr(10) for n in range(12))


class Forge:
    """A fake forge over a bare remote: changes, comments, and the verbs the ledger calls."""

    def __init__(self, repo, remote, user="bot"):
        self.repo, self.remote, self.user = repo, remote, user
        self.changes = {}
        self.calls = []
        self.offline = False
        self.degraded = False
        self.create_error = None
        self.truncate = False
        self.auth_offline = False
        self.view_error = None
        self.counter = 0

    def next(self):
        self.counter += 1
        return str(self.counter)

    def open_change(self, branch, state="opened"):
        change = {"id": self.next(), "branch": branch, "state": state, "notes": [], "threads": []}
        self.changes[change["id"]] = change
        return change

    def find(self, ref):
        for change in self.changes.values():
            if ref in (change["id"], change["branch"]):
                return change
        raise ledger.MissingChange(f"no change {ref}")

    def head(self, change):
        return git(self.remote, "rev-parse", f"refs/heads/{change['branch']}")

    def note(self, author, body, number):
        return {"id": number, "author": author, "body": body, "url": f"https://f/n{number}",
                "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}

    def call(self, verb, payload, mode="read"):
        self.calls.append((verb, payload))
        if self.offline and verb != "auth-status":
            raise ledger.LedgerError("network is down")
        if verb == "auth-status":
            if self.auth_offline:
                raise ledger.LedgerError("network is down")
            return {"user": self.user}
        if verb == "change-view":
            if self.view_error:
                raise ledger.LedgerError(self.view_error)
            change = self.find(payload["id"])
            return {"id": change["id"], "url": f"https://f/c{change['id']}", "state": change["state"],
                    "head_sha": self.head(change), "base_sha": "b", "head_ref": "r",
                    "blob_base": "", "cross_fork": False}
        if verb == "change-diff":
            change = self.find(payload["id"])
            return {"diff": git(self.repo, "diff", "main", self.head(change))}
        if verb == "note-list":
            change = self.find(payload["id"])
            notes = change["notes"]
            return {"notes": notes[:-1] if self.truncate else notes, "count": len(notes)}
        if verb == "thread-list":
            change = self.find(payload["id"])
            return {"threads": change["threads"], "count": len(change["threads"])}
        if verb == "change-create-draft":
            if self.create_error:
                raise ledger.LedgerError(self.create_error)
            change = self.open_change(payload["source"])
            return {"id": change["id"], "url": f"https://f/c{change['id']}", "draft": True}
        if verb == "change-comment":
            change = self.find(payload["id"])
            number = self.next()
            if payload.get("line") is not None or payload.get("old_line") is not None:
                if self.degraded:
                    return {"ok": False, "cleaned": True, "inline": False,
                            "reason": "position degraded to a plain note"}
                assert payload.get("require_inline") is True
                thread = {"id": "t" + number, "resolved": False, "url": f"https://f/t{number}",
                          "notes": [self.note(self.user, payload["text"], number)],
                          "path": payload.get("new_path") or payload.get("file"),
                          "line": payload.get("line")}
                change["threads"].append(thread)
                return {"ok": True, "inline": True, "thread": thread["id"], "comment": number,
                        "url": thread["url"]}
            change["notes"].append(self.note(self.user, payload["text"], number))
            return {"ok": True, "inline": False, "thread": "", "comment": number,
                    "url": f"https://f/n{number}"}
        if verb == "commit-changes":
            found = []
            for change in self.changes.values():
                probe = subprocess.run(
                    ["git", "merge-base", "--is-ancestor", payload["sha"], self.head(change)],
                    cwd=self.repo, capture_output=True)
                if probe.returncode == 0:
                    found.append({"id": change["id"], "url": f"https://f/c{change['id']}",
                                  "state": change["state"], "draft": False,
                                  "source": change["branch"], "target": "main", "author": "a"})
            return {"changes": found, "count": len(found)}
        raise AssertionError(verb)

    def verbs(self, name):
        return [payload for verb, payload in self.calls if verb == name]


@pytest.fixture
def world(tmp_path, monkeypatch):
    repo, remote = tmp_path / "repo", tmp_path / "remote.git"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    (repo / "src").mkdir()
    (repo / "src" / "App.java").write_text(
        "class App {\n  int a;\n  int b;\n}\n" + TAIL, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    git(repo, "push", "-q", "origin", "main")
    git(repo, "checkout", "-q", "-b", "topic")
    (repo / "src" / "App.java").write_text(
        "class App {\n  int a;\n  int price;\n  int b;\n}\n" + TAIL, encoding="utf-8")
    git(repo, "commit", "-qam", "add price")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("AFK_RATIONALE_CACHE", str(tmp_path / "cache"))
    return SimpleNamespace(repo=repo, remote=remote, forge=Forge(repo, remote), tmp=tmp_path)


def push(world, branch="topic"):
    git(world.repo, "push", "-q", "origin", branch)


def add(world, line=3, text="Price is kept in cents because of the ledger export."):
    return ledger.command_rationale_add(SimpleNamespace(
        path="src/App.java", line=line, side=None, text=text, text_file=None, line_text=None))


def post(world, **overrides):
    values = {"change": None, "head": None, "title": None, "target": "main", "trust": [], "reject": []}
    values.update(overrides)
    return ledger.command_rationale_post(SimpleNamespace(**values), world.forge)


def verify(world, **overrides):
    values = {"change": None, "clear": False, "trust": [], "reject": []}
    values.update(overrides)
    return ledger.command_rationale_verify(SimpleNamespace(**values), world.forge)


def read(world, line=3, **overrides):
    values = {"path": "src/App.java", "line": line, "head": None, "side": None, "offline": False,
              "no_cache": False, "batch_file": None, "trust": [], "reject": []}
    values.update(overrides)
    return ledger.command_rationale_read(SimpleNamespace(**values), world.forge)


# ---- pending entries ---------------------------------------------------------

def test_add_writes_a_deterministic_pending_entry_under_the_git_dir(world):
    first = add(world)
    second = add(world)
    assert first["op"] == second["op"]
    entry = json.loads(Path(first["pending"]).read_text(encoding="utf-8"))
    assert entry["path"] == "src/App.java" and entry["line"] == 3 and entry["side"] == "new"
    assert Path(first["pending"]).is_relative_to(world.repo / ".git" / "afk" / "rationale")
    assert ledger.load_pending(world.repo)[0]["op"] == first["op"]


def test_add_refuses_text_that_carries_a_marker(world):
    with pytest.raises(ledger.UsageError):
        add(world, text="see <!-- afk:rationale v1 op=x -->")
    with pytest.raises(ledger.UsageError):
        add(world, text="   ")


def test_add_refuses_a_line_it_cannot_read(world):
    with pytest.raises(ledger.UsageError):
        add(world, line=99)


# ---- the write transaction ---------------------------------------------------

def test_post_reports_the_exact_push_blocker_and_opens_no_draft(world):
    add(world)
    result = post(world)
    assert result["ok"] is False and result["blocker"] == "push"
    assert "topic" in result["reason"]
    assert world.forge.verbs("change-create-draft") == []


def test_post_opens_a_draft_for_the_pushed_branch_and_writes_receipt(world):
    op = add(world)["op"]
    push(world)
    result = post(world)
    assert result["ok"] is True, result
    assert result["created_draft"] is True
    change = world.forge.changes[result["change"]]
    assert change["branch"] == "topic"
    assert len(change["threads"]) == 1
    body = change["threads"][0]["notes"][0]["body"]
    assert "Price is kept in cents" in body
    marker = ledger.parse_rationale_entry(body)[0][0]
    assert marker["op"] == op and marker["line"] == 3 and marker["path"] == "src/App.java"
    assert marker["head"] == git(world.repo, "rev-parse", "HEAD")
    assert result["receipt"]["batch"]
    assert any("afk:rationale-receipt" in n["body"] for n in change["notes"])
    assert verify(world)["durable"] is True


def test_post_uses_a_writable_change_and_creates_no_draft(world):
    add(world)
    push(world)
    change = world.forge.open_change("topic")
    result = post(world)
    assert result["ok"] is True and result["change"] == change["id"]
    assert result["created_draft"] is False
    assert world.forge.verbs("change-create-draft") == []


def test_post_opens_a_new_draft_when_the_branch_change_is_merged(world):
    add(world)
    push(world)
    world.forge.open_change("topic", state="merged")
    result = post(world)
    assert result["ok"] is True and result["created_draft"] is True


def test_post_reports_a_draft_creation_failure_verbatim(world):
    add(world)
    push(world)
    world.forge.create_error = "403 forbidden: no permission to create a change"
    result = post(world)
    assert result["ok"] is False and result["blocker"] == "draft-create"
    assert "403 forbidden" in result["reason"]
    assert result["durable"] is False


def test_post_refuses_when_the_pushed_head_is_not_the_local_head(world):
    add(world)
    push(world)
    world.forge.open_change("topic")
    (world.repo / "extra.txt").write_text("x\n", encoding="utf-8")
    git(world.repo, "add", "-A")
    git(world.repo, "commit", "-qm", "unpushed")
    result = post(world)
    assert result["ok"] is False and result["blocker"] == "head-mismatch"


def test_post_is_idempotent_and_reuses_the_receipt(world):
    add(world)
    push(world)
    first = post(world)
    second = post(world)
    assert second["ok"] is True
    assert second["posted"] == [] and len(second["skipped"]) == 1
    assert second["receipt"]["reused"] is True
    change = world.forge.changes[first["change"]]
    assert len(change["threads"]) == 1
    assert sum("afk:rationale-receipt" in n["body"] for n in change["notes"]) == 1


def test_post_writes_no_receipt_when_a_comment_degrades(world):
    add(world)
    push(world)
    world.forge.open_change("topic")
    world.forge.degraded = True
    result = post(world)
    assert result["ok"] is False and result["receipt"] is None
    assert result["failed"][0]["reason"]
    change = next(iter(world.forge.changes.values()))
    assert change["notes"] == []
    assert verify(world)["ok"] is False


def test_post_fails_a_target_outside_the_diff(world):
    add(world, line=13, text="The tail is fixed by the loader.")
    push(world)
    world.forge.open_change("topic")
    result = post(world)
    assert result["ok"] is False
    assert "not in the change diff" in result["failed"][0]["reason"]


def test_post_relocates_a_line_that_moved_when_its_context_is_unique(world):
    add(world)
    (world.repo / "src" / "App.java").write_text(
        "class App {\n  int a;\n  int z;\n  int price;\n  int b;\n}\n", encoding="utf-8")
    git(world.repo, "commit", "-qam", "shift")
    push(world)
    result = post(world)
    assert result["ok"] is True, result
    change = world.forge.changes[result["change"]]
    marker = ledger.parse_rationale_entry(change["threads"][0]["notes"][0]["body"])[0][0]
    assert marker["line"] == 4


def test_verify_passes_with_nothing_pending(world):
    assert verify(world)["durable"] is True


def test_verify_fails_when_a_comment_has_no_receipt(world):
    op = add(world)["op"]
    push(world)
    change = world.forge.open_change("topic")
    entry = ledger.load_pending(world.repo)[0]
    marker = ledger.make_rationale_marker(op, git(world.repo, "rev-parse", "HEAD"),
                                          "src/App.java", 3, "new", entry["context"])
    world.forge.call("change-comment", {"id": change["id"], "text": "why\n\n" + marker,
                                        "line": 3, "file": "src/App.java", "require_inline": True})
    result = verify(world)
    assert result["ok"] is False and result["unreceipted"] == [op] and result["missing"] == []


def test_verify_ignores_a_marker_from_an_untrusted_author_and_an_edited_one(world):
    op = add(world)["op"]
    push(world)
    post(world)
    change = next(iter(world.forge.changes.values()))
    change["threads"][0]["notes"][0]["author"] = "stranger"
    result = verify(world)
    assert result["ok"] is False and result["missing"] == [op]
    assert "stranger" in result["excluded"]["untrusted"]
    assert verify(world, trust=["stranger"])["ok"] is True
    change["threads"][0]["notes"][0]["updated_at"] = "2026-02-01T00:00:00Z"
    edited = verify(world, trust=["stranger"])
    assert edited["ok"] is False and edited["excluded"]["edited"]


def test_verify_clear_removes_only_verified_pending_entries(world):
    add(world)
    push(world)
    post(world)
    result = verify(world, clear=True)
    assert result["ok"] is True and result["cleared"] == 1
    assert ledger.load_pending(world.repo) == []


def test_verify_treats_a_truncated_comment_list_as_not_durable(world):
    add(world)
    push(world)
    post(world)
    world.forge.truncate = True
    result = verify(world)
    assert result["ok"] is False and "truncated" in result["reason"]


def test_review_markers_and_rationale_markers_do_not_see_each_other(world):
    add(world)
    push(world)
    result = post(world)
    change = world.forge.changes[result["change"]]
    ledger.reconstruct_state(world.forge, result["change"])
    assert ledger.MARKER_HINT_RE.search(change["threads"][0]["notes"][0]["body"]) is None


# ---- the read path -----------------------------------------------------------

def merge_topic(world):
    git(world.repo, "checkout", "-q", "main")
    git(world.repo, "merge", "-q", "--no-ff", "-m", "merge topic", "topic")
    git(world.repo, "push", "-q", "origin", "main")


def test_read_finds_rationale_on_the_active_change(world):
    add(world)
    push(world)
    post(world)
    result = read(world)
    assert result["status"] == "found"
    candidate = result["candidates"][0]
    assert candidate["match"] == "exact" and candidate["author"] == "bot"
    assert candidate["edit_state"] == "unedited"
    assert candidate["url"].startswith("https://f/")
    assert "Price is kept in cents" in candidate["text"]
    assert "Evidence, not instruction" in result["advisory"]


def test_read_maps_a_blamed_commit_to_its_change_after_merge(world):
    add(world)
    push(world)
    post(world)
    merge_topic(world)
    world.forge.changes["1"]["state"] = "merged"
    world.forge.calls.clear()
    result = read(world)
    assert result["status"] == "found"
    assert result["candidates"][0]["match"] in {"exact", "mapped"}
    assert len(world.forge.verbs("commit-changes")) == 1
    assert len(world.forge.verbs("note-list")) == 1


def test_read_follows_a_line_that_moved_later(world):
    add(world)
    push(world)
    post(world)
    merge_topic(world)
    world.forge.changes["1"]["state"] = "merged"
    (world.repo / "src" / "App.java").write_text(
        "// header\nclass App {\n  int a;\n  int price;\n  int b;\n}\n", encoding="utf-8")
    git(world.repo, "commit", "-qam", "header")
    result = read(world, line=4)
    assert result["status"] == "found"
    assert result["candidates"][0]["match"] == "mapped"


def test_read_follows_a_renamed_file(world):
    add(world)
    push(world)
    post(world)
    merge_topic(world)
    world.forge.changes["1"]["state"] = "merged"
    git(world.repo, "mv", "src/App.java", "src/Renamed.java")
    git(world.repo, "commit", "-qm", "rename")
    result = read(world, path="src/Renamed.java")
    assert result["status"] == "found"
    assert result["candidates"][0]["match"] == "mapped"


def test_read_returns_every_ambiguous_candidate(world):
    add(world, text="First reason.")
    add(world, text="Second reason.")
    push(world)
    post(world)
    result = read(world)
    assert result["ambiguous"] is True
    assert {c["text"] for c in result["candidates"]} == {"First reason.", "Second reason."}


def test_read_flags_rationale_recorded_for_a_line_that_was_later_edited(world):
    add(world)
    push(world)
    post(world)
    (world.repo / "src" / "App.java").write_text(
        "class App {\n  int a;\n  long price;\n  int b;\n}\n" + TAIL, encoding="utf-8")
    git(world.repo, "commit", "-qam", "widen")
    push(world)
    result = read(world)
    assert [c["match"] for c in result["candidates"]] == ["stale"]


def test_read_with_no_rationale_says_none(world):
    push(world)
    world.forge.open_change("topic")
    assert read(world)["status"] == "none"


def test_read_excludes_a_rejected_author_and_reports_the_count(world):
    add(world)
    push(world)
    post(world)
    world.forge.changes["1"]["threads"][0]["notes"][0]["author"] = "stranger"
    result = read(world, reject=["stranger"])
    assert result["candidates"] == [] and result["excluded"]["rejected"] == 1
    assert read(world, no_cache=True)["candidates"][0]["author_class"] == "other"


def test_read_offline_returns_unverified_with_the_cached_age_and_head(world):
    add(world)
    push(world)
    post(world)
    merge_topic(world)
    world.forge.changes["1"]["state"] = "merged"
    assert read(world)["status"] == "found"
    world.forge.offline = True
    result = read(world)
    assert result["status"].startswith("unverified(")
    assert "offline" in result["status"]
    candidate = result["candidates"][0]
    assert candidate["source"] == "cache" and "age_s" in candidate and candidate["fetched_head"]


def test_read_offline_without_a_cache_is_unverified_not_none(world):
    add(world)
    push(world)
    post(world)
    merge_topic(world)
    world.forge.offline = True
    result = read(world, no_cache=True)
    assert result["status"].startswith("unverified(") and result["candidates"] == []


def test_read_marks_a_truncated_comment_list_unverified(world):
    add(world)
    push(world)
    post(world)
    world.forge.truncate = True
    result = read(world)
    assert result["status"].startswith("unverified(") and "truncated" in result["status"]


def test_an_online_read_refetches_the_change_instead_of_trusting_the_cache(world):
    push(world)
    world.forge.open_change("topic")
    assert read(world)["status"] == "none"
    add(world)
    post(world)
    world.forge.calls.clear()
    again = read(world)
    assert again["status"] == "found"
    assert len(world.forge.verbs("note-list")) == 1
    assert again["candidates"][0]["source"] == "live"


def test_read_surfaces_pending_rationale_that_is_not_yet_posted(world):
    add(world, text="Not posted yet.")
    result = read(world)
    assert result["pending"][0]["text"] == "Not posted yet."
    assert result["candidates"] == []


def test_the_cache_lives_outside_the_repository(world):
    add(world)
    push(world)
    post(world)
    merge_topic(world)
    read(world)
    assert (world.tmp / "cache").exists()
    assert git(world.repo, "status", "--porcelain") == ""


# ---- the command line, end to end, through the adapter seam -------------------

STUB_FORGE = '''
import json, os, subprocess, sys
state_path = os.environ["FAKE_FORGE_STATE"]
try:
    state = json.load(open(state_path))
except OSError:
    state = {"next": 1, "changes": {}}
verb, payload = sys.argv[1], json.loads(sys.stdin.read() or "{}")
def out(value):
    json.dump(state, open(state_path, "w"))
    print(json.dumps(value))
def find(ref):
    for change in state["changes"].values():
        if ref in (change["id"], change["branch"]):
            return change
    print(json.dumps({"error": True, "reason": "no change " + str(ref)}))
    sys.exit(0)
def head(change):
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
def ident():
    state["next"] += 1
    return str(state["next"])
if verb == "auth-status":
    out({"user": "bot"})
elif verb == "change-view":
    change = find(payload["id"])
    out({"id": change["id"], "url": "https://f/c", "state": "opened", "head_sha": head(change),
         "base_sha": "b", "head_ref": "r", "blob_base": "", "cross_fork": False})
elif verb == "change-diff":
    out({"diff": subprocess.run(["git", "diff", "main", "HEAD"], capture_output=True, text=True).stdout})
elif verb in ("note-list", "thread-list"):
    change = find(payload["id"])
    key = "notes" if verb == "note-list" else "threads"
    out({key: change[key], "count": len(change[key])})
elif verb == "change-create-draft":
    change = {"id": ident(), "branch": payload["source"], "notes": [], "threads": []}
    state["changes"][change["id"]] = change
    out({"id": change["id"], "url": "https://f/c", "draft": True})
elif verb == "change-comment":
    change = find(payload["id"])
    number = ident()
    note = {"id": number, "author": "bot", "body": payload["text"], "url": "https://f/n" + number,
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z"}
    if payload.get("line") is not None:
        change["threads"].append({"id": "t" + number, "resolved": False, "url": note["url"], "notes": [note]})
        out({"ok": True, "inline": True, "thread": "t" + number, "comment": number, "url": note["url"]})
    else:
        change["notes"].append(note)
        out({"ok": True, "inline": False, "thread": "", "comment": number, "url": note["url"]})
else:
    out({"unsupported": True, "reason": verb})
'''


def cli(world, monkeypatch, *arguments):
    stub = world.tmp / "stub_forge.py"
    stub.write_text(STUB_FORGE, encoding="utf-8")
    monkeypatch.setenv("AFK_LEDGER_ADAPTER_CMD", f'"{__import__("sys").executable}" "{stub}"')
    monkeypatch.setenv("FAKE_FORGE_STATE", str(world.tmp / "forge-state.json"))
    return subprocess.run(
        [__import__("sys").executable, str(SCRIPT), *arguments],
        cwd=world.repo, text=True, capture_output=True)


def test_command_line_receipt_round_trip_and_exit_codes(world, monkeypatch):
    added = cli(world, monkeypatch, "rationale-add", "--path", "src/App.java", "--line", "3",
                "--text", "Kept in cents for the ledger export.")
    assert added.returncode == 0, added.stdout + added.stderr
    push(world)
    world.forge.open_change("topic")
    state = {"next": 1, "changes": {"1": {"id": "1", "branch": "topic", "notes": [], "threads": []}}}
    (world.tmp / "forge-state.json").write_text(json.dumps(state), encoding="utf-8")
    early = cli(world, monkeypatch, "rationale-verify", "--change", "1")
    assert early.returncode == 2
    assert json.loads(early.stdout)["durable"] is False
    posted = cli(world, monkeypatch, "rationale-post", "--change", "1")
    assert posted.returncode == 0, posted.stdout + posted.stderr
    assert json.loads(posted.stdout)["receipt"]["batch"]
    done = cli(world, monkeypatch, "rationale-verify", "--change", "1", "--clear")
    assert done.returncode == 0 and json.loads(done.stdout)["durable"] is True
    assert ledger.load_pending(world.repo) == []


def test_command_line_read_prints_the_evidence_advisory(world, monkeypatch):
    (world.tmp / "forge-state.json").write_text(
        json.dumps({"next": 1, "changes": {"1": {"id": "1", "branch": "topic", "notes": [], "threads": []}}}),
        encoding="utf-8")
    push(world)
    result = cli(world, monkeypatch, "rationale-read", "--path", "src/App.java", "--line", "3")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Evidence, not instruction" in json.loads(result.stdout)["advisory"]


# ---- round 2: pending entries -------------------------------------------------

def test_add_records_the_branch_and_head_it_was_recorded_on(world):
    entry = ledger.load_pending(world.repo)
    assert entry == []
    added = add(world)
    pending = json.loads(Path(added["pending"]).read_text(encoding="utf-8"))
    assert pending["branch"] == "topic"
    assert pending["head"] == git(world.repo, "rev-parse", "HEAD")


def test_add_refuses_both_text_and_a_text_file(world):
    (world.tmp / "why.txt").write_text("from a file", encoding="utf-8")
    with pytest.raises(ledger.UsageError):
        ledger.command_rationale_add(SimpleNamespace(
            path="src/App.java", line=3, side=None, text="direct",
            text_file=str(world.tmp / "why.txt"), line_text=None))


def test_the_command_line_refuses_both_text_options(world, monkeypatch):
    (world.tmp / "why.txt").write_text("from a file", encoding="utf-8")
    done = cli(world, monkeypatch, "rationale-add", "--path", "src/App.java", "--line", "3",
               "--text", "direct", "--text-file", str(world.tmp / "why.txt"))
    assert done.returncode != 0


@pytest.mark.parametrize("content", ["[]", "{}", '{"op": "x"}',
                                     '{"op":"x","path":"p","line":"3","side":"new","context":"c","text":"t","branch":"b","head":"h"}'])
def test_a_malformed_pending_entry_is_a_named_error(world, content):
    folder = world.repo / ".git" / "afk" / "rationale"
    folder.mkdir(parents=True)
    (folder / "bad.json").write_text(content, encoding="utf-8")
    with pytest.raises(ledger.LedgerError, match="invalid pending entry"):
        ledger.load_pending(world.repo)


def drop(world, op, reason="the line was deleted"):
    return ledger.command_rationale_drop(SimpleNamespace(op=op, reason=reason))


def test_a_stale_entry_can_be_dropped_and_verify_reports_the_drop(world):
    keep = add(world)["op"]
    gone = add(world, line=2, text="Field a is reserved.")["op"]
    (world.repo / "src" / "App.java").write_text(
        "class App {\n  int price;\n  int b;\n}\n" + TAIL, encoding="utf-8")
    git(world.repo, "commit", "-qam", "delete a")
    push(world)
    first = post(world)
    assert first["ok"] is False and first["failed"][0]["op"] == gone
    assert verify(world)["ok"] is False
    dropped = drop(world, gone)
    assert dropped["ok"] is True and dropped["op"] == gone
    second = post(world)
    assert second["ok"] is True, second
    done = verify(world)
    assert done["ok"] is True and done["durable"] is True
    assert done["dropped"] == [{"op": gone, "reason": "the line was deleted"}]
    assert keep not in [d["op"] for d in done["dropped"]]
    cleared = verify(world, clear=True)
    assert cleared["ok"] is True
    assert ledger.load_pending(world.repo) == []
    assert verify(world)["dropped"] == []


def test_drop_needs_a_known_op_and_a_reason(world):
    op = add(world)["op"]
    with pytest.raises(ledger.UsageError):
        drop(world, "nope")
    with pytest.raises(ledger.UsageError):
        drop(world, op, reason="  ")


def test_an_entry_recorded_on_another_branch_is_not_posted_here(world):
    add(world)
    push(world)
    git(world.repo, "checkout", "-q", "-b", "other")
    push(world, "other")
    world.forge.open_change("other")
    result = post(world)
    assert result["ok"] is True and result["pending"] == 0
    assert result["other_branches"] == 1
    other = next(c for c in world.forge.changes.values() if c["branch"] == "other")
    assert other["threads"] == [] and other["notes"] == []
    assert verify(world)["durable"] is True
    assert len(ledger.load_pending(world.repo)) == 1
    git(world.repo, "checkout", "-q", "topic")
    assert verify(world)["durable"] is False


def test_a_local_branch_that_tracks_another_name_uses_the_tracked_branch(world):
    git(world.repo, "checkout", "-q", "-b", "work")
    git(world.repo, "push", "-q", "-u", "origin", "work:topic")
    add(world)
    result = post(world)
    assert result["ok"] is True, result
    assert world.forge.changes[result["change"]]["branch"] == "topic"


# ---- round 2: the receipt is validated ---------------------------------------

def forge_change(world, result):
    return world.forge.changes[result["change"]]


def rewrite_receipt(change, **fields):
    note = next(n for n in change["notes"] if "afk:rationale-receipt" in n["body"])
    for name, value in fields.items():
        note["body"] = ledger.re.sub(rf"\b{name}=\S+", f"{name}={value}", note["body"])


@pytest.mark.parametrize("field,value", [("batch", "0000000000000000"), ("head", "deadbeef"),
                                         ("count", "2"), ("ops", "aaaa")])
def test_verify_rejects_a_receipt_that_does_not_match(world, field, value):
    add(world)
    push(world)
    result = post(world)
    assert verify(world)["durable"] is True
    rewrite_receipt(forge_change(world, result), **{field: value})
    bad = verify(world)
    assert bad["ok"] is False and bad["durable"] is False


def test_post_does_not_reuse_a_receipt_that_does_not_match(world):
    add(world)
    push(world)
    result = post(world)
    rewrite_receipt(forge_change(world, result), batch="0000000000000000")
    again = post(world)
    assert again["receipt"]["reused"] is False
    assert verify(world)["durable"] is True


# ---- round 2: a forge failure is not a missing change --------------------------

def test_a_forge_failure_on_the_change_lookup_blocks_instead_of_opening_a_draft(world):
    add(world)
    push(world)
    world.forge.view_error = "connection timed out"
    result = post(world)
    assert result["ok"] is False and result["blocker"] == "forge-unavailable"
    assert "timed out" in result["reason"]
    assert world.forge.verbs("change-create-draft") == []
    assert verify(world)["blocker"] == "forge-unavailable"


def test_the_adapter_names_a_missing_change(world, monkeypatch):
    stub = world.tmp / "missing.py"
    stub.write_text(
        'import json, sys\nprint(json.dumps({"error": True, "missing": True, "reason": "no change"}))\n',
        encoding="utf-8")
    monkeypatch.setenv("AFK_LEDGER_ADAPTER_CMD", f'"{__import__("sys").executable}" "{stub}"')
    with pytest.raises(ledger.MissingChange):
        ledger.Adapter().call("change-view", {"id": "topic"})


def test_the_adapter_call_has_a_timeout(world, monkeypatch):
    stub = world.tmp / "slow.py"
    stub.write_text("import time\ntime.sleep(20)\n", encoding="utf-8")
    monkeypatch.setenv("AFK_LEDGER_ADAPTER_CMD", f'"{__import__("sys").executable}" "{stub}"')
    monkeypatch.setenv("AFK_LEDGER_ADAPTER_TIMEOUT", "1")
    with pytest.raises(ledger.LedgerError, match="timed out"):
        ledger.Adapter().call("auth-status", {})


# ---- round 2: the read path labels every author ---------------------------------

def test_read_returns_a_teammates_note_labeled_other(world):
    add(world)
    push(world)
    post(world)
    world.forge.changes["1"]["threads"][0]["notes"][0]["author"] = "teammate"
    result = read(world)
    assert result["status"] == "found"
    candidate = result["candidates"][0]
    assert candidate["author"] == "teammate" and candidate["author_class"] == "other"
    assert candidate["edit_state"] == "unedited"


def test_read_labels_self_and_trusted_authors(world):
    add(world, text="Mine.")
    add(world, text="Theirs.")
    push(world)
    result = post(world)
    threads = world.forge.changes[result["change"]]["threads"]
    threads[1]["notes"][0]["author"] = "lead"
    labels = {c["text"]: c["author_class"] for c in read(world, trust=["lead"])["candidates"]}
    assert set(labels.values()) == {"self", "trusted"}


def test_read_returns_an_edited_note_labeled_edited(world):
    add(world)
    push(world)
    post(world)
    world.forge.changes["1"]["threads"][0]["notes"][0]["updated_at"] = "2026-02-01T00:00:00Z"
    candidate = read(world)["candidates"][0]
    assert candidate["edit_state"] == "edited" and candidate["author_class"] == "self"


def test_read_ranks_trusted_unedited_notes_first_and_excludes_only_rejected(world):
    add(world, text="Mine.")
    add(world, text="Theirs.")
    add(world, text="Blocked.")
    push(world)
    result = post(world)
    threads = world.forge.changes[result["change"]]["threads"]
    ordered = sorted(threads, key=lambda t: t["notes"][0]["body"])
    for note, author in zip((t["notes"][0] for t in ordered), ("stranger", "teammate", "bot")):
        note["author"] = author
    ordered[1]["notes"][0]["updated_at"] = "2026-02-01T00:00:00Z"
    found = read(world, reject=["stranger"])
    assert [c["author"] for c in found["candidates"]] == ["bot", "teammate"]
    assert found["excluded"]["rejected"] == 1


def test_a_plain_note_marker_is_recovery_evidence_not_rationale(world):
    add(world)
    push(world)
    result = post(world)
    change = forge_change(world, result)
    body = change["threads"][0]["notes"][0]["body"]
    change["threads"].clear()
    world.forge.call("change-comment", {"id": change["id"], "text": body})
    found = read(world)
    assert found["candidates"] == []
    assert found["excluded"]["plain"]
    assert verify(world)["ok"] is False


# ---- round 2: the resolver ------------------------------------------------------

def test_read_walks_back_to_the_change_that_explained_an_edited_line(world):
    add(world)
    push(world)
    post(world)
    merge_topic(world)
    world.forge.changes["1"]["state"] = "merged"
    (world.repo / "src" / "App.java").write_text(
        "class App {\n  int a;\n  long price;\n  int b;\n}\n" + TAIL, encoding="utf-8")
    git(world.repo, "commit", "-qam", "widen")
    result = read(world)
    assert result["status"] == "found"
    assert [c["match"] for c in result["candidates"]] == ["stale"]
    assert result["candidates"][0]["change"]["id"] == "1"


def test_read_offline_by_request_is_unverified_even_with_a_full_cache(world):
    add(world)
    push(world)
    post(world)
    merge_topic(world)
    world.forge.changes["1"]["state"] = "merged"
    assert read(world)["status"] == "found"
    world.forge.calls.clear()
    result = read(world, offline=True)
    assert result["status"].startswith("unverified(") and "offline" in result["status"]
    assert result["candidates"][0]["source"] == "cache"
    assert world.forge.calls == []


def test_read_keeps_the_cached_identity_when_authentication_is_offline(world):
    add(world)
    push(world)
    post(world)
    merge_topic(world)
    world.forge.changes["1"]["state"] = "merged"
    assert read(world)["candidates"][0]["author_class"] == "self"
    world.forge.offline = True
    world.forge.auth_offline = True
    result = read(world)
    assert result["status"].startswith("unverified(")
    assert result["candidates"][0]["author_class"] == "self"
    assert result["identity"]["source"] == "cache"


def test_a_failed_commit_changes_lookup_is_not_cached_as_none(world):
    add(world)
    push(world)
    post(world)
    merge_topic(world)
    world.forge.changes["1"]["state"] = "merged"
    real = world.forge.call

    def flaky(verb, payload, mode="read"):
        if verb == "commit-changes":
            raise ledger.LedgerError("gh exited 1")
        return real(verb, payload, mode)
    world.forge.call = flaky
    assert read(world)["status"].startswith("unverified(")
    world.forge.call = real
    assert read(world)["status"] == "found"


def test_read_batches_targets_by_commit_and_change(world):
    add(world)
    push(world)
    world.forge.open_change("topic")
    post(world)
    world.forge.calls.clear()
    batch = world.tmp / "targets.json"
    batch.write_text(json.dumps([{"path": "src/App.java", "line": n} for n in (2, 3, 4)]),
                     encoding="utf-8")
    result = read(world, batch_file=str(batch), path=None, line=None)
    assert [r["line"] for r in result["results"]] == [2, 3, 4]
    assert len(world.forge.verbs("commit-changes")) == 2
    assert len(world.forge.verbs("note-list")) == 1
    assert result["results"][1]["status"] == "found"


def test_read_refuses_a_side_that_is_not_new_or_old(world):
    with pytest.raises(ledger.UsageError):
        read(world, side="sideways")


def test_the_command_line_restricts_the_side(world, monkeypatch):
    done = cli(world, monkeypatch, "rationale-read", "--path", "src/App.java", "--line", "3",
               "--side", "sideways")
    assert done.returncode != 0


def test_a_cache_path_inside_the_worktree_is_refused(world, monkeypatch):
    monkeypatch.setenv("AFK_RATIONALE_CACHE", str(world.repo / ".rc"))
    with pytest.raises(ledger.LedgerError, match="inside the repository"):
        ledger.cache_root(world.repo)
    monkeypatch.setenv("AFK_RATIONALE_CACHE", str(world.repo / ".git" / "rc"))
    with pytest.raises(ledger.LedgerError, match="inside the repository"):
        ledger.cache_root(world.repo)


def test_a_cache_write_purges_entries_older_than_the_retention(world):
    root = world.tmp / "purge-cache"
    old = root / "commits" / "old.json"
    old.parent.mkdir(parents=True)
    old.write_text("{}", encoding="utf-8")
    long_ago = __import__("time").time() - ledger.CACHE_RETENTION - 60
    __import__("os").utime(old, (long_ago, long_ago))
    ledger._cache_write(root, "commits/new.json", {"ids": []})
    assert not old.exists() and (root / "commits" / "new.json").exists()


# ---- round 3 ---------------------------------------------------------------------

def test_the_cache_is_namespaced_by_remote_and_forge(world, monkeypatch):
    first = ledger.cache_root(world.repo)
    git(world.repo, "remote", "set-url", "origin", str(world.tmp / "elsewhere.git"))
    second = ledger.cache_root(world.repo)
    monkeypatch.setenv("AFK_CFG_FORGE", "gitlab")
    third = ledger.cache_root(world.repo)
    assert len({first, second, third}) == 3


def test_trusted_unedited_candidates_rank_before_a_better_match_from_others(world):
    base = {"op": "x", "change": {"id": "1"}}
    other_exact = {**base, "match": "exact", "author_class": "other", "edit_state": "unedited", "op": "a"}
    trusted_mapped = {**base, "match": "mapped", "author_class": "trusted", "edit_state": "unedited", "op": "b"}
    self_edited = {**base, "match": "exact", "author_class": "self", "edit_state": "edited", "op": "c"}
    self_stale = {**base, "match": "stale", "author_class": "self", "edit_state": "unedited", "op": "d"}
    ranked = ledger.sort_candidates([other_exact, self_edited, self_stale, trusted_mapped])
    assert [c["op"] for c in ranked] == ["b", "d", "a", "c"]


def test_an_unsafe_xdg_cache_home_is_refused(world, monkeypatch):
    monkeypatch.delenv("AFK_RATIONALE_CACHE")
    monkeypatch.setenv("XDG_CACHE_HOME", str(world.repo / ".xdg-probe"))
    with pytest.raises(ledger.LedgerError, match="inside the repository"):
        ledger.cache_root(world.repo)
    monkeypatch.setenv("XDG_CACHE_HOME", str(world.repo / ".git" / "xdg"))
    with pytest.raises(ledger.LedgerError, match="inside the repository"):
        ledger.cache_root(world.repo)


def test_batch_input_and_a_direct_target_are_exclusive(world, monkeypatch):
    batch = world.tmp / "targets.json"
    batch.write_text(json.dumps([{"path": "src/App.java", "line": 3}]), encoding="utf-8")
    with pytest.raises(ledger.UsageError):
        read(world, batch_file=str(batch))
    done = cli(world, monkeypatch, "rationale-read", "--batch-file", str(batch), "--path",
               "src/App.java", "--line", "3")
    assert done.returncode != 0

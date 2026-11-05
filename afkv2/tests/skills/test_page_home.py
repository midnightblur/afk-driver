"""The page home commands and the notices in present (SDD §3 rows "start", "track" and "present", §7 the start
and track flows; requirement ADR-0002 the home rule, ADR-0003 the git state and the secret scan), through the real
engine in a throwaway repository. Only the page host is a stand-in."""

import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
HOST_OPEN = PLUGIN / "tests" / "engine" / "fixtures" / "host-open.txt"
for _folder in (SKILLS / "use-lavish" / "scripts", SKILLS / "grill" / "scripts", PLUGIN / "scripts", PLUGIN / "engine"):
    sys.path.insert(0, str(_folder))

import engine  # noqa: E402
import grill_start  # noqa: E402
import launcher  # noqa: E402
import page_home  # noqa: E402
import page_round  # noqa: E402
import round_document as rd  # noqa: E402
from grill_common import Refusal  # noqa: E402

TICKET = "PROJ-7"
TOKEN = "gh" + "p_" + "Made0Up" * 5  # a made-up value of a secret shape, never whole in this file


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    assert done.returncode == 0, f"git {args}: {done.stderr}"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway repository `shop` with a spec folder; the data folder; the current folder at the root; the page
    host answers `opened`; each engine verb runs in this process."""
    root = tmp_path / "shop"
    (root / ".afkv2").mkdir(parents=True)
    git(root, "init", "-q")
    for key, value in (("user.name", "t"), ("user.email", "t@t.test"), ("commit.gpgsign", "false")):
        git(root, "config", key, value)
    (root / ".afkv2" / "config.json").write_text(json.dumps({"spec_folder": "specs"}), "utf-8")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.chdir(root)
    monkeypatch.setattr(launcher, "run", lambda argv: (0, HOST_OPEN.read_text("utf-8")))
    monkeypatch.setattr(page_round, "run_command", _in_process)
    return root


def _in_process(script, args, timeout):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        engine.main([str(arg) for arg in args])
    answer = json.loads(out.getvalue())
    if not answer.get("ok"):
        raise Refusal(answer["error"]["code"], answer["error"]["reason"])
    return answer


def data_pages(tmp_path):
    return tmp_path / "local" / "afkv2" / "pages" / "shop"


def build(answer, tmp_path, *flags, topic="Cache plan"):
    """Round 1 of the started page, written by the round builder's command."""
    round_file = tmp_path / "round.json"
    round_file.write_text(json.dumps({"banner": {"settled": [], "unlocks": [], "parked": []}, "short_title": "Cache",
                                      "step": topic, "items": [{"id": "i-a", "kind": "confirm",
                                                                "body": {"type": "text", "props": {"text": "x"}}}]}),
                          "utf-8")
    built = rd.main(["build", "--doc", answer["doc"], "--session", answer["session"], "--round-input", str(round_file),
                     *flags])
    assert built["ok"], built
    return Path(answer["doc"])


# --- start: the home rule


def test_start_with_a_ticket_and_shareable_content_homes_the_page_in_the_ticket_spec_folder(repo):
    answer = page_home.start_page("Cache plan", TICKET)
    doc = Path(answer["doc"])
    assert answer["home"] == "spec" and doc.parent == (repo / "specs" / TICKET / "pages").resolve()
    assert doc.name == f"use-lavish-{answer['session']}.json"
    assert answer["raw_file"] == doc.with_name(f"use-lavish-{answer['session']}.raw.txt").as_posix()


@pytest.mark.parametrize("ticket, private", [(None, False), (None, True), (TICKET, True)])
def test_start_with_no_ticket_or_private_homes_the_page_in_the_data_folder(repo, tmp_path, ticket, private):
    answer = page_home.start_page("Cache plan", ticket, private)
    assert answer["home"] == "data" and Path(answer["doc"]).parent == data_pages(tmp_path).resolve()


@pytest.mark.parametrize("topic", [None, "", "   "])
def test_start_with_no_topic_is_refused(repo, topic):
    with pytest.raises(Refusal) as refused:
        page_home.start_page(topic, TICKET)
    assert refused.value.code == "no-topic"


def test_the_start_command_answers_one_json_object(repo, capsys):
    assert page_home.serve(page_home.main, ["start", "--ticket", TICKET]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "no-topic"
    assert page_home.serve(page_home.main, ["start", "--topic", "Cache plan", "--private"]) == 0
    assert json.loads(capsys.readouterr().out)["home"] == "data"


def test_each_start_is_a_new_session(repo):
    first = page_home.start_page("Cache plan", TICKET)
    Path(first["doc"]).parent.mkdir(parents=True, exist_ok=True)
    Path(first["doc"]).write_text("{}", "utf-8")
    second = page_home.start_page("Cache plan", TICKET)
    assert first["session"] != second["session"] and first["doc"] != second["doc"]


def test_the_page_home_names_a_ticket_folder_as_the_grill_does():
    assert page_home.ticket_slug("ACME / 12") == grill_start.ticket_slug("ACME / 12")


def test_the_repository_name_of_a_linked_worktree_is_its_main_checkout(tmp_path):
    main = tmp_path / "shop"
    (main / ".git" / "worktrees" / "feature").mkdir(parents=True)
    linked = tmp_path / "shop-worktrees" / "feature"
    linked.mkdir(parents=True)
    (linked / ".git").write_text(f"gitdir: {main / '.git' / 'worktrees' / 'feature'}\n", "utf-8")
    assert page_home.repository_name(linked) == "shop" and page_home.repository_name(main) == "shop"


# --- present: the notices in the answer, through the real engine


@pytest.mark.parametrize("ticket, flags, state", [(TICKET, (), "untracked"), (None, (), "outside"),
                                                  (TICKET, ("--private",), "outside")])
def test_a_started_page_builds_and_presents_with_its_git_state(repo, tmp_path, ticket, flags, state):
    answer = page_home.start_page("Cache plan", ticket, bool(flags))
    doc = build(answer, tmp_path, *flags, *(("--ticket", ticket) if ticket else ()))
    page = json.loads(doc.read_text("utf-8"))["session"]
    assert page["skill"] == "use-lavish" and page["step"] == "Cache plan" and page["private"] is bool(flags)
    shown = page_round.present(str(doc))
    assert shown["ok"] and shown["git_state"] == state and shown["secrets"] == []


def test_present_names_each_file_with_a_secret_and_never_refuses(repo, tmp_path):
    doc = build(page_home.start_page("Cache plan", TICKET), tmp_path, "--ticket", TICKET)
    log = repo / "specs" / TICKET / "LOG.md"
    log.write_text(f"a copied note\n{TOKEN}\n", "utf-8")
    shown = page_round.present(str(doc), [str(log)])
    assert shown["ok"] and shown["git_state"] == "untracked"
    assert shown["secrets"] == [{"file": f"specs/{TICKET}/LOG.md", "line": 2, "shape": "github-token"}]
    assert TOKEN not in json.dumps(shown)
    assert page_round.main(["present", "--doc", str(doc), "--scan", str(log)])["secrets"] == shown["secrets"]


def test_present_keeps_the_count_past_the_cap_and_the_files_it_cut(repo, tmp_path):
    """Review f16: the page says the present answer counts the hits past the cap, so present answers that count."""
    doc = build(page_home.start_page("Cache plan", TICKET), tmp_path, "--ticket", TICKET)
    log = repo / "specs" / TICKET / "LOG.md"
    log.write_text(f"{TOKEN}\n" * 23, "utf-8")
    shown = page_round.present(str(doc), [str(log)])
    assert len(shown["secrets"]) == 20 and shown["secrets_more"] == 3 and shown["scan_cut"] == []


def test_present_answers_the_diagram_counts(repo, tmp_path, monkeypatch):
    import diagrams
    monkeypatch.setattr(diagrams, "find_renderer", lambda: None)
    doc = build(page_home.start_page("Cache plan", TICKET), tmp_path, "--ticket", TICKET)
    page = json.loads(doc.read_text("utf-8"))
    page["rounds"][0]["items"][0]["body"] = {"type": "diagram", "props": {"caption": "The flow", "text": "flowchart LR; a --> b"}}
    doc.write_text(json.dumps(page), "utf-8")
    shown = page_round.present(str(doc))
    assert shown["diagrams"] == {"rendered": 0, "cached": 0, "as_text": 1}


def test_a_committed_page_presents_as_committed(repo, tmp_path):
    doc = build(page_home.start_page("Cache plan", TICKET), tmp_path, "--ticket", TICKET)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "page")
    assert page_round.present(str(doc))["git_state"] == "committed"


# --- track: into the ticket's spec folder


def test_track_moves_the_page_and_its_side_files_into_the_ticket_spec_folder(repo, tmp_path):
    doc = build(page_home.start_page("Cache plan"), tmp_path)
    page_round.present(str(doc))
    assert doc.with_suffix(".html").is_file()
    answer = page_home.track_page(str(doc), TICKET)
    target = (repo / "specs" / TICKET / "pages" / doc.name).resolve()
    assert Path(answer["doc"]) == target and target.is_file() and not doc.exists()
    assert sorted(Path(path).name for path in answer["moved"]) == sorted(
        [doc.name, doc.with_suffix(".html").name, doc.with_suffix(".shown.txt").name])
    assert json.loads(target.read_text("utf-8"))["session"]["ticket"] == TICKET
    assert page_round.present(str(target))["git_state"] == "untracked"


def test_a_second_track_moves_what_is_left(repo, tmp_path):
    doc = build(page_home.start_page("Cache plan"), tmp_path)
    first = page_home.track_page(str(doc), TICKET)
    left = doc.with_name(doc.stem + ".raw.txt")
    left.write_text("an answer", "utf-8")
    second = page_home.track_page(str(doc), TICKET)
    assert second["doc"] == first["doc"] and [Path(path).name for path in second["moved"]] == [left.name]
    assert not left.exists() and (Path(first["doc"]).parent / left.name).is_file()
    assert page_home.track_page(first["doc"], TICKET)["moved"] == []


def test_a_track_that_stopped_after_the_copy_finishes_on_a_second_run(repo, tmp_path):
    """Review f4: the target holds the page, the source is still there with a side file."""
    doc = build(page_home.start_page("Cache plan"), tmp_path)
    target = repo / "specs" / TICKET / "pages" / doc.name
    target.parent.mkdir(parents=True)
    target.write_bytes(doc.read_bytes())
    doc.with_suffix(".shown.txt").write_text("1\n", "utf-8")
    answer = page_home.track_page(str(doc), TICKET)
    assert not doc.exists() and not doc.with_suffix(".shown.txt").exists()
    assert sorted(Path(path).name for path in answer["moved"]) == sorted([doc.name, doc.with_suffix(".shown.txt").name])


def test_a_second_track_keeps_the_rounds_written_to_the_source_after_a_halfway_move(repo, tmp_path):
    """Review f15: the source got a round after the first track stopped; the second track writes it over the target."""
    doc = build(page_home.start_page("Cache plan"), tmp_path)
    source = json.loads(doc.read_text("utf-8"))
    target = repo / "specs" / TICKET / "pages" / doc.name
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({**source, "rounds": []}), "utf-8")
    page_home.track_page(str(doc), TICKET)
    assert json.loads(target.read_text("utf-8"))["rounds"] == source["rounds"] and not doc.exists()


def test_track_refuses_a_different_page_at_the_target(repo, tmp_path):
    doc = build(page_home.start_page("Cache plan"), tmp_path)
    target = repo / "specs" / TICKET / "pages" / doc.name
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"session": {"id": "another"}}), "utf-8")
    with pytest.raises(Refusal) as refused:
        page_home.track_page(str(doc), TICKET)
    assert refused.value.code == "exists" and doc.is_file()


def test_a_move_that_fails_is_refused_with_what_moved(repo, tmp_path, monkeypatch):
    """Review f3: a move across drives or onto a locked file answers, and names what moved."""
    doc = build(page_home.start_page("Cache plan"), tmp_path)
    page_round.present(str(doc))
    real, calls = page_home.shutil.move, []

    def move(source, target):
        calls.append(source)
        if len(calls) == 2:
            raise OSError("the drive said no")
        return real(source, target)

    monkeypatch.setattr(page_home.shutil, "move", move)
    with pytest.raises(Refusal) as refused:
        page_home.track_page(str(doc), TICKET)
    assert refused.value.code == "move-failed" and "the drive said no" in refused.value.reason
    assert Path(calls[0]).name in refused.value.reason and doc.is_file()
    monkeypatch.setattr(page_home.shutil, "move", real)
    assert Path(page_home.track_page(str(doc), TICKET)["doc"]).is_file() and not doc.exists()


@pytest.mark.parametrize("ticket", ["..", ".", "!!", "/"])
def test_a_ticket_that_names_no_folder_of_its_own_is_refused(repo, ticket):
    """Review f5: the ticket's folder must sit inside the spec folder."""
    with pytest.raises(Refusal) as refused:
        page_home.start_page("Cache plan", ticket)
    assert refused.value.code == "bad-ticket"


def test_start_answers_private_and_the_engine_refuses_a_private_page_in_the_spec_folder(repo, tmp_path):
    """Review f7: the private choice reaches the agent, and a private page never lives in the repository."""
    assert page_home.start_page("Cache plan", TICKET, True)["private"] is True
    assert page_home.start_page("Cache plan", TICKET)["private"] is False
    doc = build(page_home.start_page("Cache plan", TICKET), tmp_path, "--ticket", TICKET, "--private")
    with pytest.raises(Refusal) as refused:
        page_round.present(str(doc))
    assert refused.value.code == "bad-location"


def test_track_with_no_ticket_is_refused(repo, tmp_path):
    doc = build(page_home.start_page("Cache plan"), tmp_path)
    for ticket in (None, ""):
        with pytest.raises(Refusal) as refused:
            page_home.track_page(str(doc), ticket)
        assert refused.value.code == "needs-ticket" and doc.is_file()


def test_track_of_a_private_page_is_refused(repo, tmp_path):
    doc = build(page_home.start_page("Cache plan", TICKET, True), tmp_path, "--ticket", TICKET, "--private")
    with pytest.raises(Refusal) as refused:
        page_home.track_page(str(doc), TICKET)
    assert refused.value.code == "private" and doc.is_file()

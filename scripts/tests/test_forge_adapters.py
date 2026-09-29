"""What each forge adapter answers, with a mock command-line tool on PATH.

Nothing here reaches a forge. A stub `gh` / `glab` on PATH answers whatever the
case needs, so two contract points can be pinned offline:

- A paginated read arrives as one JSON document per page. Every page is read.
- `ci-wait` prints its result object on stdout for EVERY terminal status —
  success, failure, budget exhausted, unreadable — because a caller routes on
  the object, and the exit code alone does not carry a reason.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
KINDS = ("gitlab", "github")


def _bash():
    spec = importlib.util.spec_from_file_location(
        "afk_run_hook_for_forge", PLUGIN_ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


BASH = _bash()
pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")

TOOL = {"gitlab": "glab", "github": "gh"}


def stub(tmp_path: Path, kind: str, body: str) -> dict[str, str]:
    """A directory holding a stub CLI, and the environment that finds it."""
    binaries = tmp_path / "bin"
    binaries.mkdir(exist_ok=True)
    script = binaries / TOOL[kind]
    script.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    environ = dict(os.environ)
    environ["PATH"] = str(binaries) + os.pathsep + environ["PATH"]
    environ["AFK_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    return environ


RUNNER = "#!/bin/sh\nexec bash \"$AFK_TEST_SCRIPT\" \"$AFK_TEST_VERB\" \"$AFK_TEST_PAYLOAD\"\n"


def forge(kind: str, environ: dict, verb: str, payload: str = "{}", *, cwd: Path,
          via_stdin: bool = False):
    """Run one verb of one adapter.

    The payload goes through the environment, not argv: a JSON string handed
    from a native Windows process to Git Bash is re-parsed by the shell's
    runtime, which strips the quotes, and the adapter would read an unreadable
    payload and silently use its defaults.
    """
    runner = cwd / "run-forge.sh"
    runner.write_text(RUNNER, encoding="utf-8")
    environ = dict(environ)
    environ["AFK_TEST_SCRIPT"] = str(PLUGIN_ROOT / "adapters" / "forge" / kind / "forge.sh")
    environ["AFK_TEST_VERB"] = verb
    environ["AFK_TEST_PAYLOAD"] = payload
    if via_stdin:
        return subprocess.run(
            [str(BASH), str(PLUGIN_ROOT / "adapters" / "forge" / kind / "forge.sh"), verb],
            input=payload, capture_output=True, text=True, timeout=180,
            env=environ, cwd=str(cwd),
        )
    return subprocess.run(
        [str(BASH), str(runner)], capture_output=True, text=True, timeout=180,
        env=environ, cwd=str(cwd), stdin=subprocess.DEVNULL,
    )


@pytest.mark.parametrize("kind", (*KINDS, "none"))
def test_manifests_expose_note_list_but_not_note_update(kind):
    manifest = json.loads(
        (PLUGIN_ROOT / "adapters" / "forge" / kind / "adapter.json").read_text(encoding="utf-8")
    )
    assert "note-list" in manifest["operations"]
    assert "note-update" not in manifest["operations"]


@pytest.mark.parametrize("kind", KINDS)
def test_payload_can_arrive_on_stdin(tmp_path, kind):
    body = 'case "$1 $2" in\n  "mr view"|"pr view") echo \'{"number":7,"iid":7}\' ;;\n  *) echo "{}" ;;\nesac\n'
    environ = stub(tmp_path, kind, body)
    done = forge(kind, environ, "change-view", '{"id":"7"}', cwd=tmp_path, via_stdin=True)
    assert json.loads(done.stdout)["id"] == "7"


# ---- a paginated read ------------------------------------------------------

GITLAB_PAGES = """
case "$1 $2" in
  "mr view") echo '{"iid":7,"draft":true}' ;;
  "api graphql") echo '{"data":{"project":{"mergeRequest":{"notes":{"nodes":[{"id":"gid://gitlab/DiffNote/1","lastEditedAt":null},{"id":"gid://gitlab/DiffNote/2","lastEditedAt":null}]}}}}}' ;;
  "api projects/:id") echo '{"path_with_namespace":"acme/widget"}' ;;
  "api --paginate"*)
    echo '[{"id":"a","notes":[{"id":1,"body":"one","author":{"username":"x"}}]}]'
    echo '[{"id":"b","notes":[{"id":2,"body":"two","author":{"username":"y"}}]}]' ;;
  *) echo '{}' ;;
esac
"""

GITHUB_PAGES = """
case "$1 $2" in
  "repo view") echo 'acme/widget' ;;
  "pr view") echo '7' ;;
  "api graphql") echo '{"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[{"id":"T1","isResolved":false,"comments":{"nodes":[{"databaseId":1,"lastEditedAt":null}]}},{"id":"T2","isResolved":true,"comments":{"nodes":[{"databaseId":2,"lastEditedAt":null}]}}]}}}}}' ;;
  "api --paginate"*)
    echo '[{"id":1,"body":"one","path":"a.txt","user":{"login":"x"}}]'
    echo '[{"id":2,"body":"two","path":"b.txt","user":{"login":"y"}}]' ;;
  *) echo '{}' ;;
esac
"""


@pytest.mark.parametrize("kind,body", [("gitlab", GITLAB_PAGES), ("github", GITHUB_PAGES)])
def test_thread_list_reads_every_page(tmp_path, kind, body):
    environ = stub(tmp_path, kind, body)
    done = forge(kind, environ, "thread-list", '{"id":"7"}', cwd=tmp_path)
    answer = json.loads(done.stdout)
    assert "error" not in answer, done.stdout
    assert answer["count"] == 2, done.stdout


NOTE_PAGES = {
    "gitlab": """
case "$1 $2" in
  "mr view") echo '{"iid":7}' ;;
  "api graphql") echo '{"data":{"project":{"mergeRequest":{"notes":{"nodes":[{"id":"gid://gitlab/Note/1","lastEditedAt":"2025-02-03T00:00:00Z"},{"id":"gid://gitlab/Note/2","lastEditedAt":null},{"id":"gid://gitlab/Note/3","lastEditedAt":null}]}}}}}' ;;
  "api projects/:id") echo '{"path_with_namespace":"acme/widget"}' ;;
  "api --paginate"*)
    echo '[{"id":2,"body":"later","author":{"username":"b"},"created_at":"2025-02-02","updated_at":"2025-02-02","system":false}]'
    echo '[{"id":1,"body":"first","author":{"username":"a"},"created_at":"2025-02-01","updated_at":"2025-02-01","system":false},{"id":3,"body":"system","system":true}]' ;;
  *) echo '{}' ;;
esac
""",
    "github": """
case "$1 $2" in
  "repo view") echo 'acme/widget' ;;
  "pr view") echo '7' ;;
  "api graphql") echo '{"data":{"repository":{"pullRequest":{"comments":{"nodes":[{"databaseId":2,"lastEditedAt":null},{"databaseId":1,"lastEditedAt":"2025-02-03T00:00:00Z"}]}}}}}' ;;
  "api --paginate"*)
    echo '[{"id":2,"body":"later","user":{"login":"b"},"created_at":"2025-02-02","updated_at":"2025-02-02"}]'
    echo '[{"id":1,"body":"first","user":{"login":"a"},"created_at":"2025-02-01","updated_at":"2025-02-01"}]' ;;
  *) echo '{}' ;;
esac
""",
}


@pytest.mark.parametrize("kind", KINDS)
def test_note_list_is_paginated_normalized_and_oldest_first(tmp_path, kind):
    environ = stub(tmp_path, kind, NOTE_PAGES[kind])
    done = forge(kind, environ, "note-list", '{"id":"7"}', cwd=tmp_path)
    answer = json.loads(done.stdout)
    assert answer == {
        "notes": [
            {"id": "1", "author": "a", "body": "first", "created_at": "2025-02-01",
             "updated_at": "2025-02-01", "edited": True},
            {"id": "2", "author": "b", "body": "later", "created_at": "2025-02-02",
             "updated_at": "2025-02-02", "edited": False},
        ],
        "count": 2,
    }


CHANGE_META = {
    "github": """
case "$1 $2" in
  "pr view") echo '{"number":7,"url":"https://github.example/acme/widget/pull/7","headRefOid":"head7","baseRefOid":"base7","headRefName":"topic","baseRefName":"main","isCrossRepository":true,"headRepository":{"nameWithOwner":"fork/widget"}}' ;;
  *) echo '{}' ;;
esac
""",
    "gitlab": """
case "$1 $2" in
  "mr view") echo '{"iid":7,"web_url":"https://gitlab.example/acme/widget/-/merge_requests/7","sha":"head7","diff_refs":{"base_sha":"base7","head_sha":"head7"},"source_branch":"topic","target_branch":"main","source_project_id":8,"target_project_id":9,"source_project":{"web_url":"https://gitlab.example/fork/widget"}}' ;;
  *) echo '{}' ;;
esac
""",
}


@pytest.mark.parametrize("kind", KINDS)
def test_change_view_carries_immutable_refs_and_blob_source(tmp_path, kind):
    environ = stub(tmp_path, kind, CHANGE_META[kind])
    done = forge(kind, environ, "change-view", '{"id":"7"}', cwd=tmp_path)
    answer = json.loads(done.stdout)
    assert answer["head_sha"] == "head7"
    assert answer["base_sha"] == "base7"
    assert answer["head_ref"] == ("pull/7/head" if kind == "github" else "merge-requests/7/head")
    assert answer["cross_fork"] is True
    assert answer["blob_base"] == (
        "https://github.com/fork/widget/blob" if kind == "github"
        else "https://gitlab.example/fork/widget/-/blob"
    )


@pytest.mark.parametrize("kind", KINDS)
def test_change_fetch_carries_immutable_refs_and_blob_source(tmp_path, kind):
    body = CHANGE_META[kind].replace(
        '  *) echo \'{}\' ;;',
        '  "mr diff"|"pr diff") echo \'diff body\' ;;\n  *) echo \'{}\' ;;',
    )
    out_dir = tmp_path / "fetch"
    answer = json.loads(forge(
        kind, stub(tmp_path, kind, body), "change-fetch",
        json.dumps({"id": "7", "out_dir": str(out_dir)}), cwd=tmp_path,
    ).stdout)
    assert answer["head_sha"] == "head7"
    assert answer["base_sha"] == "base7"
    assert answer["head_ref"] == ("pull/7/head" if kind == "github" else "merge-requests/7/head")
    assert answer["cross_fork"] is True
    assert answer["blob_base"] == (
        "https://github.com/fork/widget/blob" if kind == "github"
        else "https://gitlab.example/fork/widget/-/blob"
    )
    assert Path(answer["files"]["metadata"]).exists()
    assert Path(answer["files"]["diff"]).exists()


def test_gitlab_change_view_resolves_the_source_project_blob_prefix(tmp_path):
    body = """
case "$1 $2" in
  "mr view") echo '{"iid":7,"sha":"head7","diff_refs":{"base_sha":"base7"},"source_project_id":8,"target_project_id":9}' ;;
  "api projects/8") echo '{"web_url":"https://gitlab.example/fork/widget"}' ;;
  *) echo '{}' ;;
esac
"""
    answer = json.loads(forge("gitlab", stub(tmp_path, "gitlab", body), "change-view", '{"id":"7"}', cwd=tmp_path).stdout)
    assert answer["blob_base"] == "https://gitlab.example/fork/widget/-/blob"


def test_github_change_comment_maps_old_side_and_returns_ids(tmp_path):
    body = """
case "$1 $2" in
  "pr view") echo '{"number":7,"headRefOid":"head7"}' ;;
  "repo view") echo 'acme/widget' ;;
  "api -X") printf '%s\n' "$*" > "$AFK_ARGS"; echo '{"id":41,"html_url":"https://github.example/c/41"}' ;;
  *) echo '{}' ;;
esac
"""
    environ = stub(tmp_path, "github", body)
    args = tmp_path / "args"
    environ["AFK_ARGS"] = str(args)
    done = forge(
        "github", environ, "change-comment",
        '{"id":"7","text":"x","old_path":"before.txt","new_path":"after.txt","old_line":8,"side":"old"}',
        cwd=tmp_path,
    )
    answer = json.loads(done.stdout)
    assert answer == {"ok": True, "inline": True, "thread": "41", "comment": "41", "url": "https://github.example/c/41"}
    sent = args.read_text(encoding="utf-8")
    assert "path=before.txt" in sent and "line=8" in sent and "side=LEFT" in sent


@pytest.mark.parametrize("side", ["new", "context"])
def test_github_change_comment_maps_new_and_context_to_right(tmp_path, side):
    body = """
case "$1 $2" in
  "pr view") echo '{"number":7,"headRefOid":"head7"}' ;;
  "repo view") echo 'acme/widget' ;;
  "api -X") printf '%s\n' "$*" > "$AFK_ARGS"; echo '{"id":41,"html_url":"u"}' ;;
  *) echo '{}' ;;
esac
"""
    environ = stub(tmp_path, "github", body)
    args = tmp_path / "args"
    environ["AFK_ARGS"] = str(args)
    payload = json.dumps({"id": "7", "text": "x", "old_path": "before.txt", "new_path": "after.txt",
                          "line": 9, "old_line": 8, "side": side})
    answer = json.loads(forge("github", environ, "change-comment", payload, cwd=tmp_path).stdout)
    assert answer["ok"] is True
    sent = args.read_text(encoding="utf-8")
    assert "path=after.txt" in sent and "line=9" in sent and "side=RIGHT" in sent


def test_github_plain_comment_uses_issue_comment_api(tmp_path):
    body = """
case "$1 $2" in
  "pr view") echo '7' ;;
  "repo view") echo 'acme/widget' ;;
  "api -X") printf '%s\n' "$*" > "$AFK_ARGS"; echo '{"id":42,"html_url":"https://github.example/n/42"}' ;;
  *) echo '{}' ;;
esac
"""
    environ = stub(tmp_path, "github", body)
    args = tmp_path / "args"
    environ["AFK_ARGS"] = str(args)
    done = forge("github", environ, "change-comment", '{"id":"7","text":"plain"}', cwd=tmp_path)
    assert json.loads(done.stdout) == {"ok": True, "inline": False, "thread": "", "comment": "42", "url": "https://github.example/n/42"}
    assert "repos/acme/widget/issues/7/comments" in args.read_text(encoding="utf-8")


def test_gitlab_context_comment_sends_both_lines_and_paths(tmp_path):
    body = """
case "$1 $2" in
  "mr view") echo '{"iid":7,"diff_refs":{"base_sha":"base","start_sha":"start","head_sha":"head"}}' ;;
  "api -X")
    while [ "$#" -gt 0 ]; do
      if [ "$1" = "--input" ]; then shift; cp "$1" "$AFK_BODY"; fi
      shift
    done
    echo '{"id":"discussion-1","notes":[{"id":51,"type":"DiffNote","web_url":"https://gitlab.example/n/51"}]}' ;;
  *) echo '{}' ;;
esac
"""
    environ = stub(tmp_path, "gitlab", body)
    sent = tmp_path / "body.json"
    environ["AFK_BODY"] = str(sent)
    done = forge(
        "gitlab", environ, "change-comment",
        '{"id":"7","text":"x","old_path":"before.txt","new_path":"after.txt","line":9,"old_line":8,"side":"context"}',
        cwd=tmp_path,
    )
    assert json.loads(done.stdout) == {"ok": True, "inline": True, "thread": "discussion-1", "comment": "51", "url": "https://gitlab.example/n/51"}
    position = json.loads(sent.read_text(encoding="utf-8"))["position"]
    assert position["old_path"] == "before.txt" and position["new_path"] == "after.txt"
    assert position["old_line"] == 8 and position["new_line"] == 9


@pytest.mark.parametrize("side,present,absent", [
    ("new", "new_line", "old_line"),
    ("old", "old_line", "new_line"),
])
def test_gitlab_change_comment_maps_each_one_sided_line(tmp_path, side, present, absent):
    body = """
case "$1 $2" in
  "mr view") echo '{"iid":7,"diff_refs":{"base_sha":"base","start_sha":"start","head_sha":"head"}}' ;;
  "api -X")
    while [ "$#" -gt 0 ]; do
      if [ "$1" = "--input" ]; then shift; cp "$1" "$AFK_BODY"; fi
      shift
    done
    echo '{"id":"d","notes":[{"id":51,"type":"DiffNote"}]}' ;;
  *) echo '{}' ;;
esac
"""
    environ = stub(tmp_path, "gitlab", body)
    sent = tmp_path / "body.json"
    environ["AFK_BODY"] = str(sent)
    payload = json.dumps({"id": "7", "text": "x", "old_path": "before.txt", "new_path": "after.txt",
                          "line": 9, "old_line": 8, "side": side})
    assert json.loads(forge("gitlab", environ, "change-comment", payload, cwd=tmp_path).stdout)["ok"] is True
    position = json.loads(sent.read_text(encoding="utf-8"))["position"]
    assert present in position and absent not in position


def test_gitlab_required_inline_degradation_is_deleted(tmp_path):
    body = """
case "$1 $2" in
  "mr view") echo '{"iid":7,"diff_refs":{"base_sha":"base","start_sha":"start","head_sha":"head"}}' ;;
  "api -X")
    if [ "$3" = "POST" ]; then echo '{"id":"discussion-1","notes":[{"id":52,"type":null}]}' ;
    else printf '%s\n' "$*" > "$AFK_DELETE"; echo '{}' ; fi ;;
  *) echo '{}' ;;
esac
"""
    environ = stub(tmp_path, "gitlab", body)
    deleted = tmp_path / "delete"
    environ["AFK_DELETE"] = str(deleted)
    done = forge(
        "gitlab", environ, "change-comment",
        '{"id":"7","text":"x","file":"a.txt","line":9,"require_inline":true}', cwd=tmp_path,
    )
    answer = json.loads(done.stdout)
    assert answer["ok"] is False and answer["cleaned"] is True
    assert answer["comment"] == "" and answer["url"] == ""
    assert "/notes/52" in deleted.read_text(encoding="utf-8")


def test_gitlab_required_inline_cleanup_failure_reports_orphan_note(tmp_path):
    body = """
case "$1 $2" in
  "mr view") echo '{"iid":7,"diff_refs":{"base_sha":"base","start_sha":"start","head_sha":"head"}}' ;;
  "api -X")
    if [ "$3" = "POST" ]; then echo '{"id":"discussion-1","notes":[{"id":53,"type":null}]}' ;
    else exit 1; fi ;;
  *) echo '{}' ;;
esac
"""
    done = forge(
        "gitlab", stub(tmp_path, "gitlab", body), "change-comment",
        '{"id":"7","text":"x","file":"a.txt","line":9,"require_inline":true}', cwd=tmp_path,
    )
    assert json.loads(done.stdout) == {
        "error": True, "note": "53", "reason": "the position degraded to a plain note and cleanup failed"
    }


def test_gitlab_degraded_position_reports_a_written_plain_note(tmp_path):
    body = """
case "$1 $2" in
  "mr view") echo '{"iid":7,"diff_refs":{"base_sha":"base","start_sha":"start","head_sha":"head"}}' ;;
  "api -X") echo '{"id":"discussion-1","notes":[{"id":54,"type":null,"web_url":"https://gitlab.example/n/54"}]}' ;;
  *) echo '{}' ;;
esac
"""
    done = forge(
        "gitlab", stub(tmp_path, "gitlab", body), "change-comment",
        '{"id":"7","text":"x","file":"a.txt","line":9}', cwd=tmp_path,
    )
    answer = json.loads(done.stdout)
    assert answer["ok"] is True and answer["inline"] is False
    assert answer["thread"] == "" and answer["comment"] == "54" and "reason" in answer


def test_gitlab_plain_comment_builds_a_canonical_note_url(tmp_path):
    body = """
case "$1 $2" in
  "mr view") echo '{"iid":7,"web_url":"https://gitlab.example/acme/widget/-/merge_requests/7"}' ;;
  "api -X") echo '{"id":55,"body":"x"}' ;;
  *) echo '{}' ;;
esac
"""
    answer = json.loads(forge(
        "gitlab", stub(tmp_path, "gitlab", body), "change-comment", '{"id":"7","text":"x"}', cwd=tmp_path,
    ).stdout)
    assert answer == {"ok": True, "inline": False, "thread": "", "comment": "55",
                      "url": "https://gitlab.example/acme/widget/-/merge_requests/7#note_55"}


def test_gitlab_thread_list_exposes_locator_url_and_note_times(tmp_path):
    body = """
case "$1 $2" in
  "mr view") echo '{"iid":7}' ;;
  "api graphql") echo '{"data":{"project":{"mergeRequest":{"notes":{"nodes":[{"id":"gid://gitlab/DiffNote/61","lastEditedAt":null}]}}}}}' ;;
  "api projects/:id") echo '{"path_with_namespace":"acme/widget"}' ;;
  "api --paginate"*) echo '[{"id":"d1","notes":[{"id":61,"type":"DiffNote","resolved":false,"body":"x","created_at":"2025-03-01","updated_at":"2025-03-02","web_url":"https://gitlab.example/n/61","author":{"username":"a"},"position":{"old_path":"old.txt","new_path":"new.txt","old_line":4,"new_line":5}}]}]' ;;
  *) echo '{}' ;;
esac
"""
    answer = json.loads(forge("gitlab", stub(tmp_path, "gitlab", body), "thread-list", '{"id":"7"}', cwd=tmp_path).stdout)
    thread = answer["threads"][0]
    assert {k: thread[k] for k in ("side", "line", "old_line", "old_path", "new_path", "url")} == {
        "side": "context", "line": 5, "old_line": 4, "old_path": "old.txt", "new_path": "new.txt",
        "url": "https://gitlab.example/n/61",
    }
    assert thread["notes"][0]["created_at"] == "2025-03-01"
    assert thread["notes"][0]["updated_at"] == "2025-03-02"
    assert thread["notes"][0]["edited"] is False


GITHUB_THREADS = """
case "$1 $2" in
  "repo view") echo 'acme/widget' ;;
  "pr view") echo '7' ;;
  "api --paginate"*) echo '[{"id":71,"body":"root","path":"a.txt","line":5,"original_line":4,"side":"RIGHT","created_at":"2025-03-01","updated_at":"2025-03-02","html_url":"https://github.example/c/71","user":{"login":"a"}}]' ;;
  "api graphql")
    case "$*" in
      *resolveReviewThread*) printf '%s\n' "$*" > "$AFK_MUTATION"; echo '{"data":{"resolveReviewThread":{"thread":{"id":"RT1","isResolved":true}}}}' ;;
      *) echo '{"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[{"id":"RT1","isResolved":true,"comments":{"nodes":[{"databaseId":71,"lastEditedAt":null}]}}]}}}}}' ;;
    esac ;;
  *) echo '{}' ;;
esac
"""


def test_github_thread_list_joins_graphql_resolution(tmp_path):
    environ = stub(tmp_path, "github", GITHUB_THREADS)
    environ["AFK_MUTATION"] = str(tmp_path / "mutation")
    answer = json.loads(forge("github", environ, "thread-list", '{"id":"7"}', cwd=tmp_path).stdout)
    thread = answer["threads"][0]
    assert thread["id"] == "71" and thread["resolved"] is True
    assert thread["side"] == "new" and thread["line"] == 5
    assert thread["new_path"] == "a.txt" and thread["url"] == "https://github.example/c/71"
    assert thread["notes"][0]["created_at"] == "2025-03-01"


def test_github_thread_list_uses_all_graphql_pages(tmp_path):
    body = """
case "$1 $2" in
  "repo view") echo 'acme/widget' ;;
  "pr view") echo '7' ;;
  "api --paginate"*)
    echo '[{"id":71,"body":"one","path":"a.txt","line":5,"side":"RIGHT","user":{"login":"a"}},{"id":72,"body":"two","path":"b.txt","line":6,"side":"RIGHT","user":{"login":"b"}}]' ;;
  "api graphql")
    echo '{"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[{"id":"RT1","isResolved":false,"comments":{"nodes":[{"databaseId":71,"lastEditedAt":null}]}}]}}}}}'
    echo '{"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[{"id":"RT2","isResolved":true,"comments":{"nodes":[{"databaseId":72,"lastEditedAt":null}]}}]}}}}}' ;;
  *) echo '{}' ;;
esac
"""
    answer = json.loads(forge(
        "github", stub(tmp_path, "github", body), "thread-list", '{"id":"7"}', cwd=tmp_path,
    ).stdout)
    assert [(thread["id"], thread["resolved"]) for thread in answer["threads"]] == [
        ("71", False), ("72", True),
    ]


@pytest.mark.parametrize(
    "comment,expected",
    [
        ({"line": 5, "original_line": 4, "side": "RIGHT"}, {"line": 5, "old_line": None}),
        ({"line": 5, "original_line": 4, "side": "LEFT"}, {"line": None, "old_line": 5}),
        ({"line": None, "original_line": 4, "side": "LEFT"}, {"line": None, "old_line": 4}),
    ],
)
def test_github_thread_list_normalizes_lines_by_side(tmp_path, comment, expected):
    root = {"id": 71, "body": "root", "path": "a.txt", "user": {"login": "a"}, **comment}
    body = f"""
case "$1 $2" in
  "repo view") echo 'acme/widget' ;;
  "pr view") echo '7' ;;
  "api --paginate"*) echo '{json.dumps([root])}' ;;
  "api graphql") echo '{{"data":{{"repository":{{"pullRequest":{{"reviewThreads":{{"nodes":[{{"id":"RT1","isResolved":false,"comments":{{"nodes":[{{"databaseId":71,"lastEditedAt":null}}]}}}}]}}}}}}}}}}' ;;
  *) echo '{{}}' ;;
esac
"""
    thread = json.loads(forge(
        "github", stub(tmp_path, "github", body), "thread-list", '{"id":"7"}', cwd=tmp_path,
    ).stdout)["threads"][0]
    assert {"line": thread["line"], "old_line": thread["old_line"]} == expected


@pytest.mark.parametrize("resolved,current", [(True, False), (False, True)])
def test_github_thread_resolve_maps_rest_root_to_graphql_node(tmp_path, resolved, current):
    body = GITHUB_THREADS.replace('"isResolved":true', f'"isResolved":{str(current).lower()}')
    environ = stub(tmp_path, "github", body)
    mutation = tmp_path / "mutation"
    environ["AFK_MUTATION"] = str(mutation)
    payload = json.dumps({"id": "7", "thread": "71", "resolved": resolved})
    done = forge("github", environ, "thread-resolve", payload, cwd=tmp_path)
    assert json.loads(done.stdout) == {"ok": True, "thread": "71", "resolved": resolved}
    assert "threadId=RT1" in mutation.read_text(encoding="utf-8")


@pytest.mark.parametrize("resolved", [True, False])
def test_github_thread_resolve_skips_mutation_in_target_state(tmp_path, resolved):
    body = GITHUB_THREADS.replace('"isResolved":true', f'"isResolved":{str(resolved).lower()}')
    mutation = tmp_path / "mutation"
    environ = stub(tmp_path, "github", body)
    environ["AFK_MUTATION"] = str(mutation)
    payload = json.dumps({"id": "7", "thread": "71", "resolved": resolved})
    answer = json.loads(forge("github", environ, "thread-resolve", payload, cwd=tmp_path).stdout)
    assert answer == {"ok": True, "thread": "71", "resolved": resolved}
    assert not mutation.exists()


@pytest.mark.parametrize("resolved", [True, False])
def test_gitlab_thread_resolve_preserves_boolean_state(tmp_path, resolved):
    body = """
case "$1 $2" in
  "mr view") echo '{"iid":7}' ;;
  "api -X") printf '%s\n' "$*" > "$AFK_ARGS"; echo '{}' ;;
  *) echo '{}' ;;
esac
"""
    args = tmp_path / "args"
    environ = stub(tmp_path, "gitlab", body)
    environ["AFK_ARGS"] = str(args)
    payload = json.dumps({"id": "7", "thread": "d1", "resolved": resolved})
    answer = json.loads(forge("gitlab", environ, "thread-resolve", payload, cwd=tmp_path).stdout)
    assert answer == {"ok": True, "thread": "d1", "resolved": resolved}
    assert f"resolved={str(resolved).lower()}" in args.read_text(encoding="utf-8")


def test_github_thread_resolve_rejects_an_unmapped_root(tmp_path):
    environ = stub(tmp_path, "github", GITHUB_THREADS)
    environ["AFK_MUTATION"] = str(tmp_path / "mutation")
    done = forge("github", environ, "thread-resolve", '{"id":"7","thread":"999"}', cwd=tmp_path)
    answer = json.loads(done.stdout)
    assert answer["error"] is True and "map" in answer["reason"]


# ---- ci-wait puts its answer on stdout, whatever the status ----------------

def ci_stub(kind: str, status: str) -> str:
    if kind == "gitlab":
        return (
            'case "$1 $2" in\n'
            f'  "mr view") echo \'{{"iid":7,"head_pipeline":{{"status":"{status}"}}}}\' ;;\n'
            '  *) echo "{}" ;;\n'
            "esac\n"
        )
    return (
        'case "$1 $2" in\n'
        f'  "pr view") echo \'{{"number":7,"statusCheckRollup":[{{"conclusion":"{status}"}}]}}\' ;;\n'
        '  *) echo "{}" ;;\n'
        "esac\n"
    )


@pytest.mark.parametrize("kind", KINDS)
def test_ci_wait_reports_budget_exhausted_on_stdout(tmp_path, kind):
    environ = stub(tmp_path, kind, ci_stub(kind, "running"))
    done = forge(kind, environ, "ci-wait", '{"id":"7","budget":0}', cwd=tmp_path)
    assert done.returncode == 2
    answer = json.loads(done.stdout)
    assert answer["status"] == "running" and "budget" in answer["reason"]
    assert done.stderr.strip() != ""


@pytest.mark.parametrize("kind", KINDS)
def test_ci_wait_reports_an_unreadable_pipeline_on_stdout(tmp_path, kind):
    environ = stub(tmp_path, kind, 'echo ""\n')
    done = forge(kind, environ, "ci-wait", '{"id":"7","budget":30,"interval":1}', cwd=tmp_path)
    assert done.returncode == 3
    answer = json.loads(done.stdout)
    assert answer["status"] == "unreadable"


def test_ci_wait_reports_success_on_stdout(tmp_path):
    environ = stub(tmp_path, "gitlab", ci_stub("gitlab", "success"))
    done = forge("gitlab", environ, "ci-wait", '{"id":"7","budget":30,"interval":1}', cwd=tmp_path)
    assert done.returncode == 0
    assert json.loads(done.stdout)["status"] == "success"


def test_ci_wait_reports_failure_on_stdout(tmp_path):
    environ = stub(tmp_path, "gitlab", ci_stub("gitlab", "failed"))
    done = forge("gitlab", environ, "ci-wait", '{"id":"7","budget":30,"interval":1}', cwd=tmp_path)
    assert done.returncode == 1
    assert json.loads(done.stdout)["status"] == "failed"


# ---- change-create-draft threads the assignee through -----------------------

# The stub records the argv `mr create` / `pr create` was called with, so the
# test reads exactly what the adapter asked the CLI for. A URL on stdout keeps
# the adapter's own success parse happy.
CREATE_STUB = {
    "gitlab": (
        'case "$1 $2" in\n'
        '  "mr create") printf "%s\\n" "$*" > "$AFK_ARGS"; '
        'echo "https://gitlab.example/x/y/-/merge_requests/7" ;;\n'
        '  *) echo "{}" ;;\n'
        "esac\n"
    ),
    "github": (
        'case "$1 $2" in\n'
        '  "pr create") printf "%s\\n" "$*" > "$AFK_ARGS"; '
        'echo "https://github.com/x/y/pull/7" ;;\n'
        '  *) echo "{}" ;;\n'
        "esac\n"
    ),
}


@pytest.mark.parametrize("kind", KINDS)
def test_change_create_draft_passes_the_assignee_when_set(tmp_path, kind):
    environ = stub(tmp_path, kind, CREATE_STUB[kind])
    args_file = tmp_path / "create-args.txt"
    environ["AFK_ARGS"] = str(args_file)
    done = forge(
        kind, environ, "change-create-draft",
        '{"title":"t","target":"main","source":"b","body":"x","assignee":"octocat"}',
        cwd=tmp_path,
    )
    answer = json.loads(done.stdout)
    assert "error" not in answer, done.stdout
    assert answer["draft"] is True
    assert "--assignee octocat" in args_file.read_text(encoding="utf-8")


@pytest.mark.parametrize("kind", KINDS)
def test_change_create_draft_omits_the_assignee_when_unset(tmp_path, kind):
    """An unset assignee changes nothing: no `--assignee` reaches the CLI."""
    environ = stub(tmp_path, kind, CREATE_STUB[kind])
    args_file = tmp_path / "create-args.txt"
    environ["AFK_ARGS"] = str(args_file)
    done = forge(
        kind, environ, "change-create-draft",
        '{"title":"t","target":"main","source":"b","body":"x"}',
        cwd=tmp_path,
    )
    answer = json.loads(done.stdout)
    assert "error" not in answer, done.stdout
    assert "--assignee" not in args_file.read_text(encoding="utf-8")


# ---- the family's own exits still hold -------------------------------------

@pytest.mark.parametrize("kind", KINDS)
def test_an_unknown_verb_is_unsupported(tmp_path, kind):
    environ = stub(tmp_path, kind, 'echo "{}"\n')
    done = forge(kind, environ, "no-such-verb", "{}", cwd=tmp_path)
    assert done.returncode == 3
    assert json.loads(done.stdout)["unsupported"] is True


def test_none_reports_note_list_as_unsupported(tmp_path):
    done = subprocess.run(
        [str(BASH), str(PLUGIN_ROOT / "adapters" / "forge" / "none" / "forge.sh"), "note-list"],
        input='{"id":"7"}', capture_output=True, text=True, cwd=str(tmp_path), timeout=30,
    )
    assert done.returncode == 3
    assert json.loads(done.stdout)["unsupported"] is True


# ---- commit-changes: the changes that carry a commit ------------------------

COMMIT_CHANGES = {
    "gitlab": """
case "$1 $2" in
  "api --paginate"*)
    echo '[{"iid":9,"web_url":"https://gitlab.example/acme/widget/-/merge_requests/9","state":"merged","draft":false,"source_branch":"topic","target_branch":"main","author":{"username":"a"}}]'
    echo '[{"iid":4,"web_url":"https://gitlab.example/acme/widget/-/merge_requests/4","state":"opened","draft":true,"source_branch":"other","target_branch":"main","author":{"username":"b"}}]' ;;
  *) echo '{}' ;;
esac
""",
    "github": """
case "$1 $2" in
  "repo view") echo 'acme/widget' ;;
  "api --paginate"*)
    echo '[{"number":9,"html_url":"https://github.example/acme/widget/pull/9","state":"closed","merged_at":"2025-01-01T00:00:00Z","draft":false,"head":{"ref":"topic"},"base":{"ref":"main"},"user":{"login":"a"}}]'
    echo '[{"number":4,"html_url":"https://github.example/acme/widget/pull/4","state":"open","merged_at":null,"draft":true,"head":{"ref":"other"},"base":{"ref":"main"},"user":{"login":"b"}}]' ;;
  *) echo '{}' ;;
esac
""",
}


@pytest.mark.parametrize("kind", KINDS)
def test_commit_changes_lists_every_page_in_the_common_shape(tmp_path, kind):
    environ = stub(tmp_path, kind, COMMIT_CHANGES[kind])
    done = forge(kind, environ, "commit-changes", '{"sha":"abc123"}', cwd=tmp_path)
    answer = json.loads(done.stdout)
    assert answer["count"] == 2, done.stdout
    by_id = {change["id"]: change for change in answer["changes"]}
    assert by_id["9"]["state"] == "merged"
    assert by_id["9"]["source"] == "topic" and by_id["9"]["target"] == "main"
    assert by_id["9"]["author"] == "a"
    assert by_id["9"]["url"].endswith("/9")
    assert by_id["4"]["state"] == "opened" and by_id["4"]["draft"] is True


@pytest.mark.parametrize("kind", KINDS)
def test_commit_changes_needs_a_sha(tmp_path, kind):
    environ = stub(tmp_path, kind, "echo '[]'\n")
    answer = json.loads(forge(kind, environ, "commit-changes", "{}", cwd=tmp_path).stdout)
    assert answer.get("error") is True


@pytest.mark.parametrize("kind", KINDS)
def test_commit_changes_reports_an_unreadable_answer_as_an_error(tmp_path, kind):
    environ = stub(tmp_path, kind, "echo 'not json'\n")
    answer = json.loads(forge(kind, environ, "commit-changes", '{"sha":"abc"}', cwd=tmp_path).stdout)
    assert answer.get("error") is True


def test_none_forge_answers_commit_changes_as_unsupported(tmp_path):
    done = subprocess.run(
        [str(BASH), str(PLUGIN_ROOT / "adapters" / "forge" / "none" / "forge.sh"), "commit-changes"],
        capture_output=True, text=True, cwd=str(tmp_path), stdin=subprocess.DEVNULL)
    assert done.returncode == 3
    assert json.loads(done.stdout)["unsupported"] is True


@pytest.mark.parametrize("kind", (*KINDS, "none"))
def test_manifests_declare_commit_changes(kind):
    manifest = json.loads(
        (PLUGIN_ROOT / "adapters" / "forge" / kind / "adapter.json").read_text(encoding="utf-8"))
    assert "commit-changes" in manifest["operations"]


# ---- commit-changes: exact endpoint, failure propagation, bounded time -----------

ENDPOINT = {"gitlab": "commits/abc123/merge_requests", "github": "commits/abc123/pulls"}


@pytest.mark.parametrize("kind", KINDS)
def test_commit_changes_calls_the_endpoint_of_the_requested_commit(tmp_path, kind):
    log = tmp_path / "args.log"
    environ = stub(tmp_path, kind, f'echo "$@" >> "{log.as_posix()}"\n' + COMMIT_CHANGES[kind])
    forge(kind, environ, "commit-changes", '{"sha":"abc123"}', cwd=tmp_path)
    paged = [row for row in log.read_text(encoding="utf-8").splitlines() if "--paginate" in row]
    assert len(paged) == 1 and ENDPOINT[kind] in paged[0], paged
    assert "per_page=100" in paged[0]


FAILING_PAGE = {
    "gitlab": "echo '[{\"iid\":9,\"state\":\"merged\"}]'\nexit 1\n",
    "github": "echo '[{\"number\":9,\"state\":\"closed\"}]'\nexit 1\n",
}


@pytest.mark.parametrize("kind", KINDS)
def test_commit_changes_reports_a_failing_cli_as_an_error_not_an_empty_answer(tmp_path, kind):
    environ = stub(tmp_path, kind, FAILING_PAGE[kind])
    answer = json.loads(forge(kind, environ, "commit-changes", '{"sha":"abc123"}', cwd=tmp_path).stdout)
    assert answer.get("error") is True and "changes" not in answer


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("body", ['{"message":"404 Not Found"}', '[{"title":"no id"}]', '[7]'])
def test_commit_changes_rejects_an_answer_that_is_not_a_list_of_changes(tmp_path, kind, body):
    environ = stub(tmp_path, kind, f"echo '{body}'\n")
    answer = json.loads(forge(kind, environ, "commit-changes", '{"sha":"abc123"}', cwd=tmp_path).stdout)
    assert answer.get("error") is True and "changes" not in answer


@pytest.mark.parametrize("kind,message", [("github", 'no pull requests found for branch "x"'),
                                          ("gitlab", "404 Not Found")])
def test_change_view_names_a_change_the_forge_says_is_missing(tmp_path, kind, message):
    environ = stub(tmp_path, kind, f"echo '{message}' >&2\nexit 1\n")
    answer = json.loads(forge(kind, environ, "change-view", '{"id":"x"}', cwd=tmp_path).stdout)
    assert answer["error"] is True and answer["missing"] is True


@pytest.mark.parametrize("kind", KINDS)
def test_change_view_does_not_call_a_timeout_a_missing_change(tmp_path, kind):
    environ = stub(tmp_path, kind, "echo 'dial tcp: i/o timeout' >&2\nexit 1\n")
    answer = json.loads(forge(kind, environ, "change-view", '{"id":"x"}', cwd=tmp_path).stdout)
    assert answer["error"] is True and answer["missing"] is False
    assert "timeout" in answer["reason"]


def _has_gnu_timeout():
    probe = subprocess.run([str(BASH), "-c", "timeout --version | grep -q GNU"], capture_output=True)
    return probe.returncode == 0


@pytest.mark.skipif(not _has_gnu_timeout(), reason="GNU timeout is not installed")
@pytest.mark.parametrize("kind", KINDS)
def test_a_stalled_forge_cli_is_stopped_at_the_time_limit(tmp_path, kind):
    import time
    environ = stub(tmp_path, kind, "sleep 30\n")
    environ["AFK_FORGE_TIMEOUT"] = "1"
    started = time.time()
    answer = json.loads(forge(kind, environ, "commit-changes", '{"sha":"abc123"}', cwd=tmp_path).stdout)
    assert time.time() - started < 20
    assert answer.get("error") is True


# ---- the forge's own edit flag ---------------------------------------------

def failing_graphql(body: str) -> str:
    """The same stub, but its GraphQL call exits non-zero."""
    return body.replace('case "$1 $2" in\n', 'case "$1 $2" in\n  "api graphql") exit 1 ;;\n', 1)


@pytest.mark.parametrize("kind", KINDS)
def test_note_list_fails_when_the_graphql_call_fails(tmp_path, kind):
    body = failing_graphql(NOTE_PAGES[kind])
    answer = json.loads(forge(kind, stub(tmp_path, kind, body), "note-list", '{"id":"7"}', cwd=tmp_path).stdout)
    assert answer["error"] is True and "notes" not in answer


@pytest.mark.parametrize("kind,node", [
    ("github", '{"databaseId":2,"lastEditedAt":null},'),
    ("gitlab", '{"id":"gid://gitlab/Note/2","lastEditedAt":null},'),
])
def test_note_list_fails_when_a_note_has_no_graphql_edit_state(tmp_path, kind, node):
    assert node in NOTE_PAGES[kind]
    body = NOTE_PAGES[kind].replace(node, "")
    answer = json.loads(forge(kind, stub(tmp_path, kind, body), "note-list", '{"id":"7"}', cwd=tmp_path).stdout)
    assert answer["error"] is True and "notes" not in answer


@pytest.mark.parametrize("kind", KINDS)
def test_note_list_fails_when_graphql_omits_lastEditedAt(tmp_path, kind):
    body = NOTE_PAGES[kind].replace(',"lastEditedAt":null', "").replace(
        ',"lastEditedAt":"2025-02-03T00:00:00Z"', "")
    answer = json.loads(forge(kind, stub(tmp_path, kind, body), "note-list", '{"id":"7"}', cwd=tmp_path).stdout)
    assert answer["error"] is True and "notes" not in answer


@pytest.mark.parametrize("kind,body,old", [
    ("gitlab", GITLAB_PAGES, 'DiffNote/1","lastEditedAt":null'),
    ("github", GITHUB_PAGES, '{"databaseId":1,"lastEditedAt":null'),
])
def test_thread_list_carries_the_forge_edit_flag_per_note(tmp_path, kind, body, old):
    assert old in body
    edited = body.replace(old, old.replace("null", '"2025-01-01T00:00:00Z"'))
    answer = json.loads(forge(kind, stub(tmp_path, kind, edited), "thread-list", '{"id":"7"}', cwd=tmp_path).stdout)
    flags = sorted((t["notes"][0]["id"], t["notes"][0]["edited"]) for t in answer["threads"])
    assert flags == [(1, True), (2, False)]


@pytest.mark.parametrize("kind,body", [("gitlab", GITLAB_PAGES), ("github", GITHUB_PAGES)])
def test_thread_list_fails_when_the_graphql_call_fails(tmp_path, kind, body):
    answer = json.loads(forge(kind, stub(tmp_path, kind, failing_graphql(body)), "thread-list",
                              '{"id":"7"}', cwd=tmp_path).stdout)
    assert answer["error"] is True and "threads" not in answer


@pytest.mark.parametrize("kind,body", [("gitlab", GITLAB_PAGES), ("github", GITHUB_PAGES)])
def test_thread_list_fails_when_graphql_omits_lastEditedAt(tmp_path, kind, body):
    answer = json.loads(forge(kind, stub(tmp_path, kind, body.replace(',"lastEditedAt":null', "")),
                              "thread-list", '{"id":"7"}', cwd=tmp_path).stdout)
    assert answer["error"] is True and "threads" not in answer

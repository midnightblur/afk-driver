"""Engine notices (SDD §5 rows "Secret scan" and "Git state", §9b row "git", §10 rows "Secret scan" and "Git
calls"; requirement ADR-0003): the git state of a page in a throwaway repository, and the secret scan with
harmless made-up values, its time and its skip rules."""

import ast
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
for folder in (PLUGIN / "scripts", ENGINE_DIR):
    sys.path.insert(0, str(folder))

import notices  # noqa: E402

# Made-up values of each shape, built at run time so that this file holds none of them whole.
SAMPLES = {
    "private-key": "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
    "github-token": "gh" + "p_" + "Made0Up" * 5,
    "github-fine-grained-token": "github" + "_pat_" + "Made0Up" * 4,
    "gitlab-token": "gl" + "pat-" + "Made0Up" * 4,
    "slack-token": "xo" + "xb-" + "1234-made-up-0",
    "aws-access-key": "AK" + "IA" + "MADE0UP0MADE0UP0",
    "api-key": "s" + "k-" + "Made0Up" * 4,
    "web-token": "ey" + "J" + "madeupmadeup" + ".madeupmadeup" + ".madeup",
    "bearer-token": "Authorization: Bear" + "er made0up0made0up",
    "web-address-password": "https://someone:" + "made0up" + "@example.invalid/path",
}


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
    assert done.returncode == 0, f"git {args}: {done.stderr}"


@pytest.fixture
def repo(tmp_path):
    """A throwaway repository: committed.json and changed.json committed, ignored/ ignored by git."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    for key, value in (("user.name", "t"), ("user.email", "t@t.test"), ("commit.gpgsign", "false")):
        git(root, "config", key, value)
    (root / ".gitignore").write_text("ignored/\n", "utf-8")
    for name in ("committed.json", "changed.json"):
        (root / name).write_text("{}\n", "utf-8")
    git(root, "add", ".")
    git(root, "commit", "-qm", "seed")
    (root / "changed.json").write_text('{"x": 1}\n', "utf-8")
    (root / "ignored").mkdir()
    return root


def page_in(root, name, text="{}\n"):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, "utf-8")
    return path


@pytest.mark.parametrize("name, state", [
    ("committed.json", "committed"),
    ("changed.json", "committed"),
    ("new.json", "untracked"),
    ("ignored/page.json", "ignored"),
])
def test_a_page_in_the_repository_reads_its_git_state(repo, name, state):
    path = repo / name if (repo / name).exists() else page_in(repo, name)
    assert notices.page_notices(path, start=repo)["git_state"] == state


def test_a_page_added_to_the_index_but_not_committed_reads_untracked(repo):
    path = page_in(repo, "added.json")
    git(repo, "add", "added.json")
    assert notices.page_notices(path, start=repo)["git_state"] == "untracked"


def test_a_page_outside_the_repository_reads_outside_with_no_git_call(repo, tmp_path, monkeypatch):
    calls = count_git(monkeypatch)
    path = page_in(tmp_path / "elsewhere", "page.json")
    assert notices.page_notices(path, start=repo)["git_state"] == "outside"
    assert notices.page_notices(path, start=tmp_path / "elsewhere")["git_state"] == "outside"
    assert calls == []


def count_git(monkeypatch):
    calls, real = [], subprocess.run

    def run(argv, **kwargs):
        calls.append(argv)
        return real(argv, **kwargs)

    monkeypatch.setattr(notices.subprocess, "run", run)
    return calls


def test_one_show_makes_one_git_call_for_the_page_and_the_scanned_files(repo, monkeypatch):
    calls = count_git(monkeypatch)
    page = page_in(repo, "new.json")
    log = page_in(repo, "LOG.md", "words\n")
    answer = notices.page_notices(page, [log, repo / "committed.json"], start=repo)
    assert answer["git_state"] == "untracked" and len(calls) == 1
    assert calls[0][-3:] == ["new.json", "LOG.md", "committed.json"]


def test_git_missing_reads_unknown_and_scans_nothing(repo, monkeypatch):
    monkeypatch.setattr(notices, "GIT", "afkv2-no-such-git-program")
    page = page_in(repo, "new.json", SAMPLES["github-token"])
    answer = notices.page_notices(page, start=repo)
    assert answer["git_state"] == "unknown" and answer["secrets"] == [] and answer["git_reason"]


def test_a_git_failure_reads_unknown(tmp_path):
    root = tmp_path / "not-a-repo"
    (root / ".git").mkdir(parents=True)
    page = page_in(root, "page.json", SAMPLES["github-token"])
    answer = notices.page_notices(page, start=root)
    assert answer["git_state"] == "unknown" and answer["secrets"] == [] and "exit" in answer["git_reason"]


def test_a_git_timeout_of_10_s_reads_unknown(repo, monkeypatch):
    seen = {}

    def run(argv, **kwargs):
        seen.update(kwargs)
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    monkeypatch.setattr(notices.subprocess, "run", run)
    answer = notices.page_notices(page_in(repo, "new.json"), start=repo)
    assert answer["git_state"] == "unknown" and seen["timeout"] == 10 and "10 s" in answer["git_reason"]


# --- the secret scan


def test_the_scan_has_the_10_shapes_of_the_v1_redactor():
    assert sorted(notices.SHAPES) == sorted(SAMPLES)


@pytest.mark.parametrize("shape", sorted(SAMPLES))
def test_each_shape_is_found_by_file_line_and_shape_and_the_value_never_shows(repo, shape):
    page = page_in(repo, "specs/pages/new.json", f"line one\nline two holds {SAMPLES[shape]} here\n")
    answer = notices.page_notices(page, start=repo)
    assert answer["secrets"] == [{"file": "specs/pages/new.json", "line": 2, "shape": shape}]
    assert SAMPLES[shape] not in json.dumps(answer)


@pytest.mark.parametrize("words", [
    "a risk-assessment-for-the-next-quarter note", "Bearer authentication with tokens", "task-made-up-made-up-made-up",
    "https://example.invalid/path:with@sign", "plain prose with no value",
])
def test_ordinary_words_are_no_secret(repo, words):
    assert notices.page_notices(page_in(repo, "new.json", words), start=repo)["secrets"] == []


def test_a_committed_page_and_an_untracked_scan_file_are_scanned(repo):
    (repo / "committed.json").write_text(SAMPLES["aws-access-key"], "utf-8")
    log = page_in(repo, "LOG.md", f"\n\n{SAMPLES['slack-token']}\n")
    answer = notices.page_notices(repo / "committed.json", [log], start=repo)
    assert answer["git_state"] == "committed"
    assert answer["secrets"] == [{"file": "committed.json", "line": 1, "shape": "aws-access-key"},
                                 {"file": "LOG.md", "line": 3, "shape": "slack-token"}]


def test_a_page_ignored_by_git_or_outside_the_repository_is_not_scanned(repo, tmp_path):
    ignored = page_in(repo, "ignored/page.json", SAMPLES["github-token"])
    outside = page_in(tmp_path / "elsewhere", "page.json", SAMPLES["github-token"])
    assert notices.page_notices(ignored, start=repo)["secrets"] == []
    assert notices.page_notices(outside, start=repo)["secrets"] == []


def test_a_scan_file_ignored_outside_or_missing_is_not_scanned(repo, tmp_path):
    page = page_in(repo, "new.json")
    files = [page_in(repo, "ignored/LOG.md", SAMPLES["api-key"]), page_in(tmp_path / "elsewhere", "LOG.md", SAMPLES["api-key"]),
             repo / "no-such-file.md"]
    assert notices.page_notices(page, files, start=repo)["secrets"] == []


def test_the_scan_takes_60_ms_at_most_for_2_mb(tmp_path):
    line = "plain words of a page, a quote of a note and some JSON {\"id\": \"i-a\", \"text\": \"x\"}\n"
    files = []
    for k in range(4):
        path = tmp_path / f"file-{k}.txt"
        path.write_text(line * (2 * 1024 * 1024 // 4 // len(line)) + SAMPLES["github-token"], "utf-8")
        files.append(path)
    best = None
    for _ in range(3):
        began = time.perf_counter()
        hits = notices.scan_files([(path, path.name) for path in files])
        spent = time.perf_counter() - began
        best = spent if best is None else min(best, spent)
    assert len(hits) == 4 and best <= 0.060, f"{best * 1000:.1f} ms"


def test_the_notices_module_calls_no_model_and_no_network():
    tree = ast.parse((ENGINE_DIR / "notices.py").read_text("utf-8"))
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert imported <= {"__future__", "bisect", "os", "re", "subprocess", "pathlib"}, imported

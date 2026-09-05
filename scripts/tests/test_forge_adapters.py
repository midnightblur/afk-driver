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


def forge(kind: str, environ: dict, verb: str, payload: str = "{}", *, cwd: Path):
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
    return subprocess.run(
        [str(BASH), str(runner)], capture_output=True, text=True, timeout=180,
        env=environ, cwd=str(cwd), stdin=subprocess.DEVNULL,
    )


# ---- a paginated read ------------------------------------------------------

GITLAB_PAGES = """
case "$1 $2" in
  "mr view") echo '{"iid":7,"draft":true}' ;;
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


# ---- the family's own exits still hold -------------------------------------

@pytest.mark.parametrize("kind", KINDS)
def test_an_unknown_verb_is_unsupported(tmp_path, kind):
    environ = stub(tmp_path, kind, 'echo "{}"\n')
    done = forge(kind, environ, "no-such-verb", "{}", cwd=tmp_path)
    assert done.returncode == 3
    assert json.loads(done.stdout)["unsupported"] is True

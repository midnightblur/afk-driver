"""`developer_values.configure` writes one repository's answers without changing another's.

Drives the H6 prompts with scripted answers against two repositories that share
one machine file, the way `setup_secrets.py` calls it.
"""
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "afk" / "setup" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import developer_values as dv  # noqa: E402


class Prompts:
    """Scripted answers: `ask` pops the next answer ("" keeps the pre-fill); `yes` pops a bool."""

    def __init__(self, asks=(), yeses=()):
        self.asks, self.yeses, self.seen = list(asks), list(yeses), []

    def ask(self, prompt, current=None):
        self.seen.append(prompt)
        answer = self.asks.pop(0)
        return answer or current

    def yes(self, prompt, default_yes=True):
        self.seen.append(prompt)
        return self.yeses.pop(0) if self.yeses else default_yes


def run(tmp_path, name, prompts, *, tracker="none", forge="none", resolve=None):
    repo = tmp_path / name
    (repo / ".git").mkdir(parents=True, exist_ok=True)
    machine = tmp_path / "home" / ".afk" / "config.yaml"
    shared = repo / ".git" / "afk" / "config.yaml"
    noop = lambda *_: None
    written = dv.configure(
        repo=repo, machine=machine, shared=shared,
        tracker_kind=tracker, forge_kind=forge, account_id=None,
        ask=prompts.ask, yes=prompts.yes, ok=noop, skip=noop, warn=noop,
        resolve=resolve or (lambda key: str(tmp_path / "wt") if key == "worktreeBasePath" else None),
        forge_user=lambda kind: None,
    )
    return machine, shared, written


def test_a_repository_without_a_forge_keeps_the_machine_reviewer(tmp_path):
    # Repository A writes reviewer and assignee to the machine file.
    (tmp_path / "wt").mkdir()
    machine, _, _ = run(tmp_path, "a", Prompts(asks=["rev", "me"], yeses=[False]), forge="github")
    before = dv.read_block(machine)
    assert before == {"mrReviewer": "rev", "mrAssignee": "me"}

    # Repository B selects no forge and accepts the machine file.
    run(tmp_path, "b", Prompts(yeses=[False]))
    assert dv.read_block(machine) == before


def test_the_default_target_is_shared_by_the_repositorys_worktrees(tmp_path):
    (tmp_path / "wt").mkdir()
    machine, shared, written = run(tmp_path, "a", Prompts(asks=["rev", "me"]), forge="gitlab")
    assert written == [shared]
    assert dv.read_block(shared) == {"mrReviewer": "rev", "mrAssignee": "me"}
    assert not machine.exists()


def test_a_machine_answer_is_offered_again_and_none_overrides_it(tmp_path):
    (tmp_path / "wt").mkdir()
    machine = tmp_path / "home" / ".afk" / "config.yaml"
    dv.write_block(machine, {"mrReviewer": "rev", "mrAssignee": "me"})
    inherited = dv.read_block(machine)
    resolve = lambda key: inherited.get(key) or (str(tmp_path / "wt") if key == "worktreeBasePath" else None)

    _, shared, _ = run(tmp_path, "a", Prompts(asks=["", "none"]), forge="github", resolve=resolve)
    assert dv.read_block(shared) == {"mrReviewer": "rev", "mrAssignee": "none"}
    assert dv.read_block(machine) == inherited


def test_a_worktree_location_never_goes_to_the_machine_file(tmp_path):
    machine = tmp_path / "home" / ".afk" / "config.yaml"
    dv.write_block(machine, {"worktreeBasePath": str(tmp_path / "everyone")})
    (tmp_path / "mine").mkdir()
    resolve = lambda key: str(tmp_path / "everyone") if key == "worktreeBasePath" else None

    _, shared, written = run(tmp_path, "a", Prompts(asks=[str(tmp_path / "mine")], yeses=[False]),
                             resolve=resolve)
    assert written == [machine, shared]
    assert dv.read_block(shared)["worktreeBasePath"] == str(tmp_path / "mine").replace("\\", "/")
    assert dv.read_block(machine)["worktreeBasePath"] == str(tmp_path / "everyone")


@pytest.mark.parametrize("existing", ["overlay", "shared"])
def test_an_existing_narrower_block_is_kept_without_asking_for_a_target(tmp_path, existing):
    (tmp_path / "wt").mkdir()
    repo = tmp_path / "a"
    path = (repo / ".afk" / "config.local.yaml") if existing == "overlay" else (repo / ".git" / "afk" / "config.yaml")
    dv.write_block(path, {"mrReviewer": "old"})
    prompts = Prompts(asks=["new", "me"])
    _, _, written = run(tmp_path, "a", prompts, forge="github")
    assert written == [path]
    assert dv.read_block(path) == {"mrReviewer": "new", "mrAssignee": "me"}
    assert not any("No writes them" in p for p in prompts.seen)

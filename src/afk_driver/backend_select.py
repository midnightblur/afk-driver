"""Composition-root factory: pick the (tracker, scm) pair for a cwd.

Single dispatch point per SDD §3 ("single dispatch point at composition
root") and §8 module table row "backend_select". The runner depends only
on the two Protocols (`IssueTracker`, `Scm`); this module is the one
place that imports concretes (`JiraClient`, `GitLabClient`,
`GitHubIssuesClient`, `GitHubPrClient`) and binds them to a `Backend`
record.

Resolution precedence (high → low):

1. `config.backend_select.force_backend` — explicit override wins over
   everything else. Honoured per SDD §5 feature-flags table.
2. `config.github.mode == "all-repos"` — short-circuits cwd inspection
   and returns the GitHub backend regardless of `git remote` (ADR-0003).
3. `git -C {cwd} remote get-url origin` host inspection:
   * `github.com` → GitHub backend (`GitHubIssuesClient` +
     `GitHubPrClient`);
   * substring `config.backend_select.gitlab_host` → Jira + GitLab
     backend (`JiraClient` + `GitLabClient`);
   * anything else → `BackendResolutionError`.
4. Missing `origin` remote (or any `git` failure) → `BackendResolutionError`
   with a clear message — auto-detect cannot proceed.

The Jira-backend branch leaves `JiraClient` un-constructed because the
runner builds it from env-var credentials at a later layer; for now the
factory returns a placeholder shape that the cli layer will swap in.
That decision keeps this module free of secret-handling code (SDD §5
"Secrets"). The runner ring is responsible for materialising the actual
`JiraClient` instance once it has resolved the auth env vars.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from afk_driver.config import DriverConfig
from afk_driver.github_issues_client import GitHubIssuesClient
from afk_driver.github_pr_client import GitHubPrClient
from afk_driver.gitlab_client import GitLabClient
from afk_driver.scm_protocol import Scm
from afk_driver.tracker_protocol import IssueTracker


# ---------------------------------------------------------------------------
# Public value types
# ---------------------------------------------------------------------------

_KNOWN_BACKENDS: tuple[str, ...] = ("github", "jira")


class BackendResolutionError(RuntimeError):
    """Raised when the backend cannot be picked.

    Causes (each surfaced in the message):

    * `force_backend` is set to an unknown name;
    * cwd has no `origin` remote (or `git` failed);
    * cwd's `origin` host matches neither GitHub nor the configured
      GitLab host.

    The caller (cli layer pre-flight) is expected to surface this to the
    user as a halt, not retry — auto-detect has no safe default.
    """


@dataclass(frozen=True)
class RepoCoords:
    """Backend-agnostic locator for the repo a run is bound to.

    Mirrors SDD §9 Strategy classDiagram row `Backend.repo_coords`. Field
    semantics vary by backend:

    * `backend = "github"`: `owner` and `repo` parsed from the origin
      URL; `host = "github.com"`.
    * `backend = "jira"`: `owner` = GitLab namespace, `repo` = GitLab
      project slug, `host` = configured GitLab host. Empty strings are
      valid when the runner does not need the values (e.g. Jira-only
      pre-flight in `all-repos` mode is not allowed, so the GitHub branch
      always fills `owner`/`repo`).
    """

    backend: str
    host: str = ""
    owner: str = ""
    repo: str = ""


@dataclass(frozen=True)
class Backend:
    """The bound `(tracker, scm, repo_coords)` triple returned by `resolve`.

    `tracker` is `None` for the Jira branch in this SubTask — the runner
    layer composes it from env-var credentials. `scm` is fully bound on
    both branches because no secrets are needed (both `gh` and `glab` use
    their own auth subsystems). Once the runner-side refactor lands the
    `Optional` will tighten to required.
    """

    tracker: Optional[IssueTracker]
    scm: Scm
    repo_coords: RepoCoords


# ---------------------------------------------------------------------------
# Git-remote probe (injectable for tests)
# ---------------------------------------------------------------------------

# Type alias for the injectable origin-URL reader. Takes a cwd and returns
# the `origin` remote URL, or raises if no `origin` remote exists. Tests
# pass a stub so they do not need a real on-disk git repo.
OriginUrlReader = Callable[[Path], str]


def _default_origin_reader(cwd: Path) -> str:
    """Default `OriginUrlReader` — shells out to `git -C cwd remote get-url origin`.

    Returns stdout trimmed of trailing whitespace. Raises
    `BackendResolutionError` if git exits non-zero (no origin remote, not
    a git repo, etc.) — the message keeps the git stderr verbatim so the
    user can act on it.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise BackendResolutionError(
            f"cannot read git origin in {cwd!s}: {exc!s}"
        ) from exc
    if proc.returncode != 0:
        raise BackendResolutionError(
            f"git remote get-url origin failed in {cwd!s}: "
            f"{(proc.stderr or '').strip() or proc.stdout.strip()}"
        )
    return proc.stdout.strip()


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------


def _parse_github_url(url: str) -> Optional[tuple[str, str]]:
    """If `url` is a github.com remote, return `(owner, repo)`; else None.

    Accepts the three forms `gh remote add` ships:

    * `https://github.com/{owner}/{repo}(.git)?`
    * `ssh://git@github.com/{owner}/{repo}(.git)?`
    * `git@github.com:{owner}/{repo}(.git)?`

    Returns the parsed pair or `None` if the URL is not github.com.
    """
    u = url.strip()
    if not u:
        return None
    # SSH "scp" form: git@github.com:owner/repo(.git)?
    if u.startswith("git@github.com:"):
        tail = u[len("git@github.com:") :]
        return _split_owner_repo(tail)
    # https / ssh url forms
    for prefix in ("https://github.com/", "http://github.com/", "ssh://git@github.com/"):
        if u.startswith(prefix):
            tail = u[len(prefix) :]
            return _split_owner_repo(tail)
    # Fallback: any URL whose host segment is github.com
    if "github.com" in u:
        # Best-effort split; tolerate trailing path segments.
        after = u.split("github.com", 1)[1].lstrip("/:")
        parsed = _split_owner_repo(after)
        if parsed is not None:
            return parsed
    return None


def _split_owner_repo(tail: str) -> Optional[tuple[str, str]]:
    """Split a `owner/repo(.git)?(/...)?` tail into `(owner, repo)`."""
    s = tail.strip().lstrip("/")
    if not s:
        return None
    parts = s.split("/")
    if len(parts) < 2:
        return None
    owner = parts[0]
    repo = parts[1]
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]
    if not owner or not repo:
        return None
    return owner, repo


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def resolve(
    cwd: Path,
    config: DriverConfig,
    *,
    origin_reader: OriginUrlReader = _default_origin_reader,
) -> Backend:
    """Pick the backend for `cwd` per SDD §3 precedence rules.

    Tests inject `origin_reader` to avoid touching a real git repo. The
    default reader shells out to `git remote get-url origin`.
    """
    force = (config.backend_select.force_backend or "").strip().lower()
    if force:
        if force not in _KNOWN_BACKENDS:
            raise BackendResolutionError(
                f"force_backend={force!r} is not one of {_KNOWN_BACKENDS}"
            )
        if force == "github":
            return _make_github_backend(cwd, config, origin_reader, probe_remote=True)
        return _make_jira_backend(cwd, config, origin_reader, probe_remote=True)

    mode = (config.github.mode or "cwd").strip().lower()
    if mode == "all-repos":
        # ADR-0003: queue discovery is via `gh search`; cwd is irrelevant.
        return Backend(
            tracker=GitHubIssuesClient(),
            scm=GitHubPrClient(),
            repo_coords=RepoCoords(backend="github", host="github.com"),
        )

    # mode == "cwd" → inspect origin remote
    url = origin_reader(Path(cwd))
    parsed = _parse_github_url(url)
    if parsed is not None:
        owner, repo = parsed
        return Backend(
            tracker=GitHubIssuesClient(),
            scm=GitHubPrClient(),
            repo_coords=RepoCoords(
                backend="github", host="github.com", owner=owner, repo=repo
            ),
        )

    gitlab_host = (config.backend_select.gitlab_host or "").strip()
    if gitlab_host and gitlab_host in url:
        # Jira tracker is materialised at the runner layer (env-var
        # credentials). Scm is fully bound here — `glab` handles its own
        # auth. See module docstring for the staged-binding rationale.
        return Backend(
            tracker=None,
            scm=GitLabClient(),
            repo_coords=RepoCoords(backend="jira", host=gitlab_host),
        )

    raise BackendResolutionError(
        f"could not auto-detect backend for origin URL {url!r} "
        f"(expected github.com or substring {gitlab_host!r})"
    )


def _make_github_backend(
    cwd: Path,
    config: DriverConfig,
    origin_reader: OriginUrlReader,
    *,
    probe_remote: bool,
) -> Backend:
    """Build the GitHub `Backend`, optionally parsing repo coords from `origin`.

    When `probe_remote` is True we try to read the origin URL to enrich
    `repo_coords`; failures fall back to a coords record with empty
    `owner`/`repo` rather than raising — the runner can still operate
    when invoked outside a git worktree (e.g. `mode = "all-repos"` under
    a forced backend).
    """
    coords = RepoCoords(backend="github", host="github.com")
    if probe_remote:
        try:
            url = origin_reader(Path(cwd))
            parsed = _parse_github_url(url)
            if parsed is not None:
                owner, repo = parsed
                coords = RepoCoords(
                    backend="github", host="github.com", owner=owner, repo=repo
                )
        except BackendResolutionError:
            # Forced github backend tolerates a missing origin — the user
            # has explicitly told us which backend to use.
            pass
    return Backend(
        tracker=GitHubIssuesClient(), scm=GitHubPrClient(), repo_coords=coords
    )


def _make_jira_backend(
    cwd: Path,
    config: DriverConfig,
    origin_reader: OriginUrlReader,
    *,
    probe_remote: bool,
) -> Backend:
    """Build the Jira+GitLab `Backend`. Tracker is deferred to runner."""
    gitlab_host = (config.backend_select.gitlab_host or "").strip()
    return Backend(
        tracker=None,
        scm=GitLabClient(),
        repo_coords=RepoCoords(backend="jira", host=gitlab_host),
    )

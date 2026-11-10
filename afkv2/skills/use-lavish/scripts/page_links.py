"""The URL templates the page links references with (`session.links`), from the repository, at build time.

The forge templates come from the `origin` remote; the issue template from `tracker.repo` when the tracker
is GitHub issues; the ticket template from the tracker port's Jira base URL. The Jira projects it links are the
projects of the session tickets, the earlier page's projects, the config's `tracker.project` and `tracker.projects`,
and the round input's `ticket_projects`. The titles are the round input's `ticket_titles` over the earlier page's
titles. Nothing here reads the network.
A source that is missing leaves its kinds out; with no source the answer is None and the page links nothing.
"""

from __future__ import annotations

import re
import subprocess
import sys
import urllib.parse

from grill_common import PLUGIN_ROOT, Refusal, run_command

CONFIG_READER = PLUGIN_ROOT / "scripts" / "afkv2_config.py"
TIMEOUT_S = 60
FORGE_FORMS = {"github": {"issue": "/issues/{id}", "change": "/pull/{id}", "commit": "/commit/{id}"},
               "gitlab": {"issue": "/-/issues/{id}", "change": "/-/merge_requests/{id}", "commit": "/-/commit/{id}"}}
JIRA_KEY = re.compile(r"([A-Z][A-Z0-9_]+)-\d+")
PROJECT_KEY = re.compile(r"[A-Z][A-Z0-9_]+")
REFERENCE_KEY = re.compile(r"[A-Z][A-Z0-9_]+-\d+|[#!]\d+")
TITLE_LIMIT = 300


def _origin() -> str | None:
    try:
        done = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True, timeout=TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else None


def web_url(remote: str) -> str | None:
    """The web address of a remote: https, ssh or scp form, without user, port or `.git`."""
    if "://" in remote:
        parts = urllib.parse.urlsplit(remote)
        host, path = parts.hostname, parts.path
    else:
        host, _, path = remote.rpartition("@")[2].partition(":")
    path = path.strip("/").removesuffix(".git")
    return f"https://{host}/{path}" if host and path else None


def _forge_kind(config: dict, url: str) -> str | None:
    labels = re.split(r"[./-]", urllib.parse.urlsplit(url).hostname or "")
    named = [kind for kind in FORGE_FORMS if kind in labels]
    kind = config.get("forge") or (named[0] if len(named) == 1 else None)
    return kind if kind in FORGE_FORMS else None


def _jira_base() -> str | None:
    """The base URL the tracker port reads its Jira credentials with; None when the port or the value is absent."""
    sys.path.insert(0, str(PLUGIN_ROOT / "ports"))
    try:
        from tracker import jira
        return (jira.resolve_creds_env().get("JIRA_BASE_URL") or "").rstrip("/") or None
    except Exception:  # an absent or broken port links no ticket; the build goes on
        return None
    finally:
        sys.path.remove(str(PLUGIN_ROOT / "ports"))


def projects_of(*keys: str) -> list[str]:
    return sorted({match.group(1) for key in keys if key for match in [JIRA_KEY.fullmatch(key)] if match})


def project_keys(where: str, value) -> list[str]:
    """A list of Jira project keys, such as `ABC`; refuse `bad-projects` for any other value."""
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(key, str) and PROJECT_KEY.fullmatch(key) for key in value):
        raise Refusal("bad-projects", f"{where} is a list of Jira project keys, such as [\"ABC\"]: {value!r}")
    return value


def reference_titles(where: str, value) -> dict:
    """A map of reference to title, such as `{"ABC-12": "Fix the login", "#4": "Add a flag"}`, each title on one
    line. Refuse `bad-titles` for a key that is no ticket key, `#N` or `!N`, or a title that is no text of
    1 to 300 characters."""
    if value is None:
        return {}
    titles = {key: " ".join(title.split()) for key, title in value.items() if isinstance(title, str)} \
        if isinstance(value, dict) else None
    if titles is None or len(titles) != len(value) or not all(
            isinstance(key, str) and REFERENCE_KEY.fullmatch(key) and 0 < len(title) <= TITLE_LIMIT
            for key, title in titles.items()):
        raise Refusal("bad-titles", f"{where} maps a ticket key, #N or !N to a title of 1 to {TITLE_LIMIT} "
                                    f"characters, such as {{\"ABC-12\": \"Fix the login\"}}: {value!r}")
    return titles


def _config_projects(tracker: dict) -> list[str]:
    """The project keys of the config; a value that is no project key links nothing, and the build goes on."""
    listed = tracker.get("projects") if isinstance(tracker.get("projects"), list) else []
    return [key for key in [tracker.get("project"), *listed] if isinstance(key, str) and PROJECT_KEY.fullmatch(key)]


def links_for(ticket_keys: list[str], earlier: dict | None = None, projects: list[str] | None = None,
              titles: dict | None = None) -> dict | None:
    """`session.links` for this repository. `ticket_keys` are the session ticket and the tickets it links;
    `projects` are the round input's `ticket_projects`; `titles` are its `ticket_titles`, which replace an
    earlier title of the same key and keep the others."""
    try:
        config = run_command(CONFIG_READER, ["read"], TIMEOUT_S)
    except Refusal:
        return None
    links = {}
    remote = _origin()
    url = web_url(remote) if remote else None
    kind = _forge_kind(config, url) if url else None
    if kind:
        links.update({name: url + form for name, form in FORGE_FORMS[kind].items()})
    tracker = config.get("tracker") or {}
    if tracker.get("kind") == "github-issues" and tracker.get("repo"):
        host = urllib.parse.urlsplit(url).hostname if kind == "github" else "github.com"
        links["issue"] = f"https://{host}/{tracker['repo']}" + FORGE_FORMS["github"]["issue"]
    if tracker.get("kind") == "jira":
        base = _jira_base()
        found = sorted(set(projects_of(*ticket_keys)) | set((earlier or {}).get("projects") or [])
                       | set(_config_projects(tracker)) | set(projects or []))
        if base and found:
            links.update(ticket=f"{base}/browse/{{id}}", projects=found)
    held = {**((earlier or {}).get("titles") or {}), **(titles or {})}
    if links and held:
        links["titles"] = held
    return links or None

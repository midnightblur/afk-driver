"""The URL templates the page links references with (`session.links`), from the repository, at build time.

The forge templates come from the `origin` remote; the issue template from `tracker.repo` when the tracker
is GitHub issues; the ticket template from the tracker port's Jira base URL. Nothing here reads the network.
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


def links_for(ticket_keys: list[str], earlier: dict | None = None) -> dict | None:
    """`session.links` for this repository. `ticket_keys` are the session ticket and the tickets it links."""
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
        projects = sorted(set(projects_of(*ticket_keys)) | set((earlier or {}).get("projects") or []))
        if base and projects:
            links.update(ticket=f"{base}/browse/{{id}}", projects=projects)
    return links or None

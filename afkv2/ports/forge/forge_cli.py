"""The forge command: `forge_cli.py <verb> [json-payload]`, or the payload on stdin."""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from forge import github, gitlab  # noqa: E402
from tracker import envelope, settings, shell  # noqa: E402

KINDS = {"github": github, "gitlab": gitlab}
_EVERY_VERB = ("forge", "repo")
_FIELDS = {
    "auth-status": (),
    "change-view": ("id",),
    "change-diff": ("id",),
    "change-create-draft": ("title", "body", "target", "source", "reviewer", "assignee"),
    "change-update-body": ("id", "body"),
    "change-ready": ("id",),
    "change-comment": ("id", "text", "file", "old_path", "new_path", "side", "line", "old_line", "require_inline"),
    "note-list": ("id",),
    "thread-list": ("id",),
    "ci-status": ("id",),
    "ci-wait": ("id", "budget", "interval"),
}


def _host(url):
    """The host of an https, ssh or scp-form remote."""
    url = url.strip()
    if "://" in url:
        return urllib.parse.urlsplit(url).hostname or ""
    return url.rpartition("@")[2].partition(":")[0]


def _from_origin():
    try:
        done = shell.run_tool("git", ["remote", "get-url", "origin"])
    except envelope.Refusal:
        return None
    if done.returncode != 0:
        return None
    labels = re.split(r"[.-]", _host(done.stdout).lower())
    named = [kind for kind in KINDS if kind in labels]
    return named[0] if len(named) == 1 else None


def _kind(payload):
    kind = payload.get("forge") or settings.read_config().get("forge") or _from_origin()
    if kind is not None and not isinstance(kind, str):
        raise envelope.Refusal("bad-payload", "`forge` must be a word: github or gitlab")
    if kind not in KINDS:
        raise envelope.Refusal("no-forge", "no forge kind: pass `forge` in the payload (github or gitlab), "
                                           "or run where the `origin` remote names one")
    return kind


def _dispatch(verb):
    def run(payload):
        unknown = sorted(set(payload) - set(_EVERY_VERB) - set(_FIELDS[verb]))
        if unknown:
            raise envelope.Refusal("bad-payload", f"{verb} takes no {', '.join(unknown)}: nothing was written")
        return KINDS[_kind(payload)].VERBS[verb](payload)
    return run


VERBS = {verb: _dispatch(verb) for verb in github.VERBS}


def forge_main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) > 2:
        answer = envelope.fail("bad-payload", f"{args[0]} takes one JSON payload and no other argument: nothing was written")
        print(json.dumps(answer))
        return envelope.exit_code(answer)
    return envelope.serve(VERBS, args)


if __name__ == "__main__":
    sys.exit(forge_main())

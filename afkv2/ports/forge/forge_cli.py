"""The forge command: `forge_cli.py <verb> [json-payload]`, or the payload on stdin."""

from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from forge import github, gitlab  # noqa: E402
from tracker import envelope, settings, shell  # noqa: E402

KINDS = {"github": github, "gitlab": gitlab}


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
    return lambda payload: KINDS[_kind(payload)].VERBS[verb](payload)


VERBS = {verb: _dispatch(verb) for verb in github.VERBS}


def forge_main(argv=None):
    return envelope.serve(VERBS, sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(forge_main())

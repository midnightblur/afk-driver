#!/usr/bin/env python3
"""The project path inside a git remote URL, for the forge adapters.

    python project_from_remote.py <url>   ->   owner/name

Every remote form a forge accepts reduces to the same thing — the path after the
host, without a `.git` suffix:

    git@github.com:owner/name.git          -> owner/name
    https://gitlab.com/group/sub/name.git  -> group/sub/name
    ssh://git@host:2222/group/name         -> group/name

An input this cannot read prints nothing and exits 0: the caller then lets its
CLI derive the project from the checkout, which is the safe answer.
"""
import re
import sys


def project(url: str) -> str:
    url = url.strip()
    url = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", url)   # scheme
    url = re.sub(r"^[^/@]+@", "", url)                      # user@
    # What is left is `host/path`, or scp form `host:path`. Split on whichever
    # separator comes first, so a port in `host:2222/path` is not read as a path.
    slash, colon = url.find("/"), url.find(":")
    cut = min(x for x in (slash, colon) if x >= 0) if (slash >= 0 or colon >= 0) else -1
    if cut < 0:
        return ""
    path = url[cut + 1:]
    path = re.sub(r"^\d+/", "", path)                       # a port, scp form
    path = re.sub(r"\.git$", "", path).strip("/")
    return path if "/" in path else ""


if __name__ == "__main__":
    if len(sys.argv) > 1:
        answer = project(sys.argv[1])
        if answer:
            print(answer)

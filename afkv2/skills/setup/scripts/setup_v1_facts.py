"""The v1 names setup reads to take over from v1, in one place.

Setup only reads these names and matches them as full lines; it writes none
of them into a file of its own.
"""

PLUGIN_NAME = "afk"
MARKETPLACE = "afk-toolkit"

# Rule blocks in the user instruction files: one begin and one end line each.
BLOCK_NAMES = ("behaviors", "plain-language", "lavish-sessions", "investigation")


def block_begin(name: str) -> bytes:
    return f"<!-- afk:{name}:start -->".encode("ascii")


def block_end(name: str) -> bytes:
    return f"<!-- afk:{name}:end -->".encode("ascii")


# Git hook stubs: hook name -> the stub's full marker line.
STUB_LINES = {
    "pre-commit": b"# afk-precommit-gates (installed by afk-toolkit install-git-hooks.sh).",
    "reference-transaction": b"# afk-branch-name-gate (installed by afk-toolkit install-git-hooks.sh).",
}

CONFIG_PATH = (".afk", "config.yaml")

TRACKER_SERVER = "tracker"

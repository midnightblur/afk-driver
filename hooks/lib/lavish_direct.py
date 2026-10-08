"""The lavish rule of the protected-branch guard process: only the wrapper runs `lavish-axi`.

`refusal(command)` names why a shell command line must not run: `lavish-axi` in executable
position (bare, by path, behind `env`/`command`/`exec`/`npx`, or inside `bash -c` /
`pwsh -Command`), or a `LAVISH_AXI_HOST` assignment or export. Searches, mentions and
`lavish-axi --version` pass, and so does anything `shell_mutations` cannot read literally.
"""
from __future__ import annotations

import re

import shell_mutations
from shell_mutations import ASSIGN, Word, program_of, strip_prefixes

HOST = "LAVISH_AXI_HOST"
PROGRAM = re.compile(r"^lavish-axi(?:@[\w.-]+)?(?:\.(?:cmd|ps1|bat))?$")
RUNNERS = {"npx", "pnpx", "bunx"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
POWERSHELLS = {"pwsh", "powershell"}
DECLARE = {"export", "declare", "typeset", "local", "readonly", "setx"}
ENV_DRIVE = re.compile(r"^(?:\$env:|env:)" + HOST + r"(?:\s*=.*)?$", re.I)
MAX_DEPTH = 3


def wrapper_hint(plugin_root: str) -> str:
    return (f"run `afk-python \"{plugin_root}/scripts/lavish_show.py\" <same arguments>` instead: it injects "
            "the page runtime and refuses the operations LAVISH.md forbids")


def _version_probe(args: list[Word]) -> bool:
    return [w.text for w in args] == ["--version"]


def _runs_lavish(words: list[Word]) -> bool:
    prog = program_of(words[0])
    if PROGRAM.match(prog):
        return not _version_probe(words[1:])
    if prog in RUNNERS:
        rest = [w for w in words[1:] if not w.text.startswith("-")]
        return bool(rest) and not rest[0].opaque and PROGRAM.match(program_of(rest[0])) is not None \
            and not _version_probe(words[words.index(rest[0]) + 1:])
    return False


def _nested(words: list[Word]) -> tuple[str, bool] | None:
    """The script of `bash -c <script>` / `pwsh -Command <script>`, and whether it is PowerShell."""
    prog = program_of(words[0])
    for i, word in enumerate(words[1:-1], 1):
        flag = word.text.lower()
        if prog in SHELLS and re.fullmatch(r"-[a-z]*c[a-z]*", flag):
            return words[i + 1].text, False
        if prog in POWERSHELLS and flag in ("-c", "-command", "-com", "-comm", "-comma", "-comman"):
            return words[i + 1].text, True
    return None


def refusal(command: str, plugin_root: str, depth: int = 0) -> str | None:
    """Why this command line is refused, or None to leave the verdict to the rest of the guard."""
    for segment in shell_mutations.segments(command):
        words = segment.words
        if not words:
            continue
        program = strip_prefixes(words)
        prefix = words[:len(words) - len(program)]
        if any(ASSIGN.match(w.text) and w.text.split("=", 1)[0] == HOST for w in prefix) \
                or (ENV_DRIVE.match(words[0].text) and ("=" in words[0].text
                                                        or words[1:2] and words[1].text.startswith("="))) \
                or (program and program_of(program[0]) in DECLARE
                    and any(w.text.split("=", 1)[0] == HOST for w in program[1:])) \
                or (program and program_of(program[0]) in ("set-item", "si", "new-item", "ni")
                    and any(ENV_DRIVE.match(w.text) for w in program[1:])):
            return (f"lavish rule: refused to set {HOST}. It widens the lavish server bind beyond "
                    "loopback (LAVISH.md \"Fallback and forbidden operations\"). Leave it unset.")
        if not program:
            continue
        if _runs_lavish(program):
            return f"lavish rule: refused to run `lavish-axi` directly. Move: {wrapper_hint(plugin_root)}."
        inner = _nested(program)
        if inner and depth < MAX_DEPTH:
            found = refusal(inner[0], plugin_root, depth + 1)
            if found:
                return found
    return None

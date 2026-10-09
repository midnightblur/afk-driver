"""The lavish rule of the protected-branch guard process: only the wrapper runs `lavish-axi`.

`refusal(command)` names why a shell command line must not run: `lavish-axi` in executable
position (bare, by path, behind `env`/`command`/`exec`/`npx`, inside `bash -c` /
`pwsh -Command` or a double-quoted `$(…)`), or a `LAVISH_AXI_HOST` assignment or export.
Searches, mentions, comments and `lavish-axi --version` pass, and so does anything
`shell_mutations` cannot read literally. `runs` / `argv_runs` answer the run half alone,
for the native-contract source gate.
Known frontier: a literal `$(…)` inside escaped or concatenated quotes is refused as a run.
"""
from __future__ import annotations

import re

import shell_mutations
from shell_mutations import ASSIGN, Word, program_of, strip_prefixes

HOST = "LAVISH_AXI_HOST"
PROGRAM = re.compile(r"^lavish-axi(?:@[\w.-]+)?$")
RUNNERS = {"npx", "pnpx", "bunx"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
POWERSHELLS = {"pwsh", "powershell"}
DECLARE = {"export", "declare", "typeset", "local", "readonly", "setx"}
PRINT_ONLY = set("pfFn")  # print declarations, act on functions, or drop the export attribute
ENV_DRIVE = re.compile(r"^(?:\$env:|env:)" + HOST + r"(?:\s*=.*)?$", re.I)
SUBSTITUTION = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
MAX_DEPTH = 3


def wrapper_hint(plugin_root: str) -> str:
    return (f"run `afk-python \"{plugin_root}/scripts/lavish_show.py\" <same arguments>` instead: it injects "
            "the page runtime and refuses the operations LAVISH.md forbids")


def _version_probe(args: list[Word]) -> bool:
    return [w.text for w in args] == ["--version"]


def _runs_lavish(words: list[Word], bare: bool = True) -> bool:
    """Whether `words` start lavish-axi; with `bare` False, a call with no argument reads as a mention."""
    prog = program_of(words[0])
    args = words[1:]
    if prog in RUNNERS:
        rest = [w for w in words[1:] if not w.text.startswith("-")]
        if not rest or rest[0].opaque:
            return False
        prog, args = program_of(rest[0]), words[words.index(rest[0]) + 1:]
    return PROGRAM.match(prog) is not None and (bare or bool(args)) and not _version_probe(args)


def _nested(words: list[Word], program: list[Word]) -> list[str]:
    """Scripts a command runs: a double-quoted `$(…)` in any word, `bash -c` / `pwsh -Command`."""
    found = [m.group(1) or m.group(2) or "" for w in words if w.opaque for m in SUBSTITUTION.finditer(w.text)]
    prog = program_of(program[0]) if program else ""
    for i, word in enumerate(program[1:-1], 1):
        flag = word.text.lower()
        if prog in SHELLS and re.fullmatch(r"-[a-z]*c[a-z]*", flag)                 or prog in POWERSHELLS and flag in ("-c", "-command", "-com", "-comm", "-comma", "-comman"):
            found.append(program[i + 1].text)
            break
    return found


def _sets_host(words: list[Word], program: list[Word]) -> bool:
    prefix = words[:len(words) - len(program)]
    if any(ASSIGN.match(w.text) and w.text.split("=", 1)[0] == HOST for w in prefix):
        return True
    if ENV_DRIVE.match(words[0].text) and ("=" in words[0].text or words[1:2] and words[1].text.startswith("=")):
        return True
    if not program:
        return False
    prog, args = program_of(program[0]), [w.text for w in program[1:]]
    if prog in ("set-item", "si", "new-item", "ni"):
        return any(ENV_DRIVE.match(a) for a in args)
    if prog not in DECLARE:
        return False
    if any(a.startswith(HOST + "=") for a in args):
        return True
    options = "".join(a[1:] for a in args if a[:1] in "-+")
    return HOST in args and (prog == "setx" or not (set(options) & PRINT_ONLY or any(a[:1] == "+" for a in args)))


def argv_runs(words: list[Word], bare: bool = True, depth: int = 0) -> bool:
    """Whether one simple command (an argument vector) runs `lavish-axi`, here or in a nested script."""
    program = strip_prefixes(words, keywords=True)
    if program and _runs_lavish(program, bare):
        return True
    return depth < MAX_DEPTH and any(runs(inner, bare, depth + 1) for inner in _nested(words, program))


def runs(command: str, bare: bool = True, depth: int = 0) -> bool:
    """Whether a shell command line runs `lavish-axi` in executable position."""
    return any(segment.words and argv_runs(segment.words, bare, depth)
               for segment in shell_mutations.segments(command))


def refusal(command: str, plugin_root: str, depth: int = 0) -> str | None:
    """Why this command line is refused, or None to leave the verdict to the rest of the guard."""
    for segment in shell_mutations.segments(command):
        words = segment.words
        if not words:
            continue
        program = strip_prefixes(words, keywords=True)
        if _sets_host(words, program):
            return (f"lavish rule: refused to set {HOST}. It widens the lavish server bind beyond "
                    "loopback (LAVISH.md \"Fallback and forbidden operations\"). Leave it unset and "
                    f"{wrapper_hint(plugin_root)}.")
        if program and _runs_lavish(program):
            return f"lavish rule: refused to run `lavish-axi` directly. Move: {wrapper_hint(plugin_root)}."
        if depth < MAX_DEPTH:
            for inner in _nested(words, program):
                found = refusal(inner, plugin_root, depth + 1)
                if found:
                    return found
    return None

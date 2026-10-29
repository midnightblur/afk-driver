"""The worktree placement rule of the protected-branch guard, for an agent's shell command.

`refusal(command, cwd, ...)` names why the command must not run, or returns None:
- it sets `AFK_WORKTREE_FOLDER` or `AFK_ALLOW_PROTECTED` (an assignment in front of a
  command, `env`, `export`/`declare`-style words, `setx`, a PowerShell `env:` assignment,
  also inside `bash -c` / `pwsh -Command` / `$(…)` / `eval`); only the developer sets them;
- it is `git worktree add`, the destination of `git worktree move`, or a worktree creator
  call (`create-worktree --parent/--dir`) whose target placement (`scripts/placement.py`)
  does not put inside `<root>/<short name>` for a listed repository, also behind `then`/`do`/`!`.
  A target or git verb the guard cannot work out (a variable, an unknown folder, an unknown
  option) counts as outside.
Placement gives every verdict; this module only finds the target and the folder. A command
with no word naming a worktree makes no file read and starts no process.
Known frontier: git aliases from config files, scripts in files, `xargs`/`find -exec` runs.
"""
from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path

import shell_mutations
from lavish_direct import DECLARE, MAX_DEPTH, PRINT_ONLY, _nested
from shell_mutations import ASSIGN, KEYWORDS, Word, program_of, strip_prefixes

NAMES = ("AFK_WORKTREE_FOLDER", "AFK_ALLOW_PROTECTED")
CAUSES = {"AFK_WORKTREE_FOLDER": "it changes where the worktree creator puts a worktree",
          "AFK_ALLOW_PROTECTED": "it lifts the guard's rules for every command it reaches"}
HEAD = "refused to create a worktree outside the worktree root"
OWN_ROOT = Path(__file__).resolve().parents[2]  # the plugin this guard runs from
PROBE = "worktree"  # a plain name: its verdict says whether the repository is listed and its root sound
ADD_LONG = {"force": False, "detach": False, "checkout": False, "lock": False, "reason": True, "orphan": False,
            "quiet": False, "track": False, "guess-remote": False, "relative-paths": False}
ADD_SHORT = {"f": False, "d": False, "q": False, "b": True, "B": True}
MOVE_LONG = {"force": False, "relative-paths": False}
MOVE_SHORT = {"f": False}
CREATOR_VALUE = {"--branch", "--dir", "--base", "--repo", "--parent", "--name", "--session", "--idea-bin",
                 "--skip-build-gate", "--finish", "--m2-seed"}
SET_ENV = re.compile(r"setenvironmentvariable\s*\(\s*([^,)\s]*)")  # over the lowered, unquoted text
DRIVE_SETTERS = ("set-item", "si", "new-item", "ni", "set-content", "sc", "add-content", "ac")
UNQUOTE = re.compile(r"""[\\'"`]""")  # quote and escape characters, which hide no word from a text search
MARKS = re.compile(r"worktree|afk_allow_protected", re.I)  # every command the rule judges holds one


class Unknown(Exception):
    """The target cannot be worked out from the command's words."""


# ---------------------------------------------------------------- inline variables

def _env_drive(name: str) -> re.Pattern:
    return re.compile(r"^(?:\$\{env:" + name + r"\}|(?:\$env:|env:)" + name + r")(?:\s*\+?=.*)?$", re.I)


def _sets(words: list[Word], program: list[Word], name: str) -> bool:
    """`words` set `name` for what they run: the variable rule's forms (`lavish_direct._sets_host`)."""
    prefix = words[:len(words) - len(program)]
    if any(ASSIGN.match(w.text) and w.text.split("=", 1)[0] == name for w in prefix):
        return True
    drive = _env_drive(name)
    if drive.match(words[0].text) and ("=" in words[0].text or words[1:2] and words[1].text.startswith(("=", "+="))):
        return True
    if not program:
        return False
    prog, args = program_of(program[0]), [w.text.replace("\\", "") for w in program[1:]]  # Bash drops the escapes
    if prog in DRIVE_SETTERS:
        return any(drive.match(a) for a in args)
    if prog == "set":  # cmd's `set NAME=value`
        return any(a.upper().startswith(name + "=") for a in args)
    if prog not in DECLARE:
        return False
    if any(a.startswith(name + "=") for a in args):
        return True
    options = "".join(a[1:] for a in args if a[:1] in "-+")
    return name in args and (prog == "setx" or not (set(options) & PRINT_ONLY or any(a[:1] == "+" for a in args)))


def _variable_text(name: str) -> str:
    return (f"refused to set {name} in an agent command. Cause: {CAUSES[name]}, and only the "
            f"developer sets it. Move: run the command without {name}, or ask the developer.")


def _inner(words: list[Word], program: list[Word]) -> list[str]:
    """Scripts a command runs: the lavish rule's nested forms, and the joined arguments of `eval`."""
    found = _nested(words, program)
    if program and not program[0].opaque and program_of(program[0]) == "eval":
        found.append(" ".join(w.text for w in program[1:]))
    return found


def variable_refusal(command: str, powershell: bool = False, depth: int = 0) -> str | None:
    """Why an agent command must not set one of `NAMES`, or None."""
    flat = UNQUOTE.sub("", command).lower()
    for first in SET_ENV.findall(flat):  # the .NET call splits into several segments
        for name in NAMES:  # a name the call takes from a variable is one of the two when the command names it
            if first == name.lower() or (first[:1] in ("$", "(", "") and name.lower() in flat):
                return _variable_text(name)
    for segment in shell_mutations.segments(command, powershell):
        words = segment.words
        if not words:
            continue
        program = strip_prefixes(words, keywords=True)
        for name in NAMES:
            if _sets(words, program, name):
                return _variable_text(name)
        if depth < MAX_DEPTH:
            for inner in _inner(words, program):
                found = variable_refusal(inner, powershell, depth + 1)
                if found:
                    return found
    return None


# ---------------------------------------------------------------- worktree targets

def _bare(word: Word) -> str:
    """The word as Bash passes it on when its backslashes escape plain letters; the parser keeps them."""
    return word.text.replace("\\", "")


def _long(text: str, table: dict[str, bool]) -> tuple[str, bool]:
    """(option name, takes a value) for a `--name` word, git's unique-prefix abbreviation allowed."""
    name = text[2:].split("=", 1)[0]
    names = list(table) + [f"no-{n}" for n in table]
    found = [name] if name in names else [n for n in names if n.startswith(name)]
    if len(found) != 1:
        raise Unknown(text)
    chosen = found[0]
    return chosen, not chosen.startswith("no-") and table[chosen]


def _positionals(words: list[Word], long: dict[str, bool], short: dict[str, bool]) -> list[Word]:
    """The operands of a `git worktree` subcommand; options may come before or after them."""
    if any(w.opaque and w.split for w in words):
        raise Unknown("a word that can split into several")
    found: list[Word] = []
    i, options = 0, True
    while i < len(words):
        word = words[i]
        text = word.text if not _bare(word).startswith("-") else _bare(word)
        i += 1
        if options and word.opaque and (text.startswith("-") or not text):
            raise Unknown(text)  # an option the guard cannot read
        if not options or text == "-" or not text.startswith("-"):
            found.append(word)
        elif text in ("--", "--end-of-options"):
            options = False
        elif text.startswith("--"):
            _, value = _long(text, long)
            if value and "=" not in text:
                i += 1
            elif not value and "=" in text:
                raise Unknown(text)
        else:
            for j, letter in enumerate(text[1:], 1):
                if letter not in short:
                    raise Unknown(text)
                if short[letter]:
                    if j == len(text) - 1:
                        i += 1
                    break
    if i > len(words):
        raise Unknown("an option lacks its value")
    return found


def parse_worktree_add(words: list[Word]) -> Word | None:
    """The `<path>` word of `git worktree add <words>`; None when it creates nothing (no path, `-h`)."""
    if any(w.text in ("-h", "--help") and not w.opaque for w in words):
        return None
    found = _positionals(words, ADD_LONG, ADD_SHORT)
    return found[0] if found else None


def parse_worktree_move(words: list[Word]) -> tuple[Word, Word] | None:
    """(`<worktree>`, `<new-path>`) of `git worktree move <words>`; None when it moves nothing."""
    if any(w.text in ("-h", "--help") and not w.opaque for w in words):
        return None
    found = _positionals(words, MOVE_LONG, MOVE_SHORT)
    return (found[0], found[1]) if len(found) >= 2 else None


def _path(word: Word, folder: Path | None) -> Path:
    found = shell_mutations.resolve(word, folder)
    if found is None:
        raise Unknown(word.text)
    return found


def _environ(git_env: list, folder: Path | None, gitdir: Word | None, workdir: Word | None) -> dict:
    """The command's environment as git sees it, with every literal `GIT_DIR`-style setting applied."""
    environ = dict(os.environ)
    settings = [(name, word, folder) for name, word in git_env]
    settings += [("GIT_DIR", gitdir, folder)] if gitdir is not None else []
    settings += [("GIT_WORK_TREE", workdir, folder)] if workdir is not None else []
    for name, word, base in settings:
        if word is None:
            raise Unknown(f"${name}")
        environ[name] = str(_path(word, base))
    return environ


def _git_targets(segment, words: list[Word], spot: Path | None, git_env: list = ()) -> list[tuple]:
    """(target, folder, environ) per worktree a git segment makes; target None when unknown."""
    verb, folder, gitdir, workdir = shell_mutations.git_options(words, spot)
    aliased = any(re.match(r"^alias\.", w.text, re.I) and "worktree" in w.text.lower() for w in words[1:verb])
    if verb < len(words) and (words[verb].opaque or re.search(r"\s", words[verb].text)):
        return [(None, folder, None)]  # a verb the guard cannot read may be `worktree add`
    if verb >= len(words) or _bare(words[verb]) != "worktree":
        if aliased:
            return [(None, folder, None)]
        return []
    if verb + 1 >= len(words):
        return []
    sub, rest = words[verb + 1], words[verb + 2:]
    if sub.opaque:
        return [(None, folder, None)]
    if _bare(sub) not in ("add", "move"):
        return []
    try:
        environ = _environ(list(segment.git_env) + list(git_env), folder, gitdir, workdir)
        if _bare(sub) == "add":
            word = parse_worktree_add(rest)
            return [] if word is None else [(_path(word, folder), folder, environ)]
        pair = parse_worktree_move(rest)
        if pair is None:
            return []
        source, dest = pair
        target = _path(dest, folder)
        if target.is_dir():  # git moves into an existing folder under the source's own name
            try:
                target = target / _path(source, folder).name
            except Unknown:
                target = target / PROBE
        return [(target, folder, environ)]
    except Unknown:
        return [(None, folder, None)]


def _creator_targets(words: list[Word], spot: Path | None) -> list[tuple]:
    """(target or None, folder, None) of a `create-worktree` call that places by `--parent` or `--dir`."""
    given: dict[str, Word] = {}
    i = 1
    while i < len(words):
        flag = words[i]
        if flag.opaque:
            return [(None, spot, None)]
        if flag.text in CREATOR_VALUE:
            if i + 1 >= len(words):
                return []
            given[flag.text] = words[i + 1]
            i += 2
        else:
            i += 1  # a switch, or an unknown argument the creator refuses
    name = given.get("--name")
    if name is not None and (name.opaque or name.text):
        if name.opaque and ("--parent" in given or "--dir" in given):
            return [(None, spot, None)]
        return []  # the name path: the creator itself places it under the root
    dir_word = given.get("--dir")
    if dir_word is None:
        return []  # the creator refuses a call without --dir
    try:
        folder = _path(given["--repo"], spot) if "--repo" in given else spot
        if dir_word.opaque:
            raise Unknown(dir_word.text)
        if "--parent" in given:
            parent = _path(given["--parent"], spot)
            return [(parent / dir_word.text, folder, None)]
        return [("name", folder, dir_word.text)]
    except Unknown:
        return [(None, spot, None)]


def _program(segment, words: list[Word], effects: dict | None = None) -> list[Word]:
    """The program words after `then`/`do`/`!`-style control words, also when the program is opaque."""
    program = strip_prefixes(words, effects, keywords=True)
    if program:
        return program
    rest = list(words or segment.words)
    while rest and not rest[0].opaque and (ASSIGN.match(rest[0].text) or rest[0].text in KEYWORDS):
        rest.pop(0)
    return rest


def _targets(segment, words: list[Word], spot: Path | None) -> list[tuple]:
    effects: dict = {}
    program = _program(segment, words, effects)
    if not program:
        return []
    if effects.get("chdir"):  # an `env -C` behind a control word
        spot = shell_mutations.resolve(effects["chdir"], spot)
    if len(program) > 1 and not program[0].opaque and program_of(program[0]) in ("bash", "sh"):
        program = program[1:]
        while len(program) > 1 and program[0].text.startswith("-") and "c" not in program[0].text:
            program = program[1:]
    prog = {program_of(program[0]), program_of(Word(_bare(program[0]), program[0].opaque))}
    if "create-worktree" in prog:
        return _creator_targets(program, spot)
    if "git" in prog and not program[0].opaque:
        return _git_targets(segment, program, spot, effects.get("git_env", []))
    if program[0].opaque:
        texts = [_bare(w) for w in program[1:] if not w.opaque]
        if "worktree" in texts and {"add", "move"} & set(texts[texts.index("worktree") + 1:][:1]):
            return [(None, spot, None)]
    return []


def _mentions(command: str) -> bool:
    """The command names a worktree once quotes and escapes are dropped."""
    return "worktree" in UNQUOTE.sub("", command).lower()


def _placement():
    spec = importlib.util.spec_from_file_location("afk_placement_for_guard", OWN_ROOT / "scripts" / "placement.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verdict(placement, target, folder: Path, extra) -> str | None:
    """Placement's answer for one target, as the refusal text; None when the worktree may be made there."""
    try:
        if target == "name":
            verdict = placement.target_for(str(folder), extra)
        elif target is None:
            verdict = placement.target_for(str(folder), PROBE, environ=extra)
        else:
            verdict = placement.check_target(str(target), str(folder), environ=extra)
    except placement.PlacementError as problem:
        return f"{HEAD}. Cause: placement has no answer ({problem}). Move: run /afk:setup, or ask the developer."
    if verdict.state == placement.NOT_LISTED:
        return None
    if verdict.state == placement.REFUSED and verdict.rule != placement.OUTSIDE:
        return (f"{HEAD}. Cause: worktree root: {verdict.rule} {verdict.reason}. "
                "Move: run /afk:setup, or ask the developer.")
    if target is None:
        return (f"{HEAD}. Cause: the guard cannot work out this command's worktree target, so it may be outside "
                f"{verdict.folder}. Move: create it under {verdict.folder}, or ask the developer.")
    if verdict.state == placement.INSIDE:
        return None
    return f"{HEAD}. Cause: {verdict.reason}. Move: create it under {verdict.folder}, or ask the developer."


def worktree_refusal(command: str, cwd: Path, powershell: bool = False, toplevel=None, depth: int = 0) -> str | None:
    """Why an agent's worktree command must not run, or None. `toplevel` is passed to `shell_mutations.steps`."""
    if not _mentions(command):
        return None
    placement = None
    for segment, words, spot, here in shell_mutations.steps(command, cwd, powershell, toplevel):
        for target, folder, extra in _targets(segment, words, spot):
            placement = placement or _placement()
            found = _verdict(placement, target, folder or spot or cwd, extra)
            if found:
                return found
        if depth < MAX_DEPTH:
            for inner in _inner(segment.words, _program(segment, words)):
                found = worktree_refusal(inner, spot or cwd, powershell, toplevel, depth + 1)
                if found:
                    return found
    return None


def concerns(command: str) -> bool:
    """Whether the rule can refuse `command`: a text test that reads no file and starts no process."""
    return bool(MARKS.search(UNQUOTE.sub("", command)))


def refusal(command: str, cwd: Path, powershell: bool = False, toplevel=None) -> str | None:
    """The rule's refusal of an agent's shell command, or None to leave it to the rest of the guard."""
    if not concerns(command):
        return None
    try:
        return variable_refusal(command, powershell) or worktree_refusal(command, cwd, powershell, toplevel)
    except Exception as problem:  # a worktree command the guard cannot read is not let through
        if not _mentions(command):
            return None
        return f"{HEAD}. Cause: the guard could not read this command ({problem}). Move: ask the developer."

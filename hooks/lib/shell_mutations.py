"""The literal paths a shell command line changes, for protected_branch_guard.

`resources(command, cwd)` splits Bash and PowerShell text on control operators and
recognizes high-confidence mutation forms; anything it cannot resolve literally is skipped.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

NO_TARGET = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty", "nul", "$null"}
WRAPPERS = {"command", "exec", "nohup", "time", "env", "sudo", "builtin"}
SUDO_VALUE = {"-u", "-g", "-h", "-p", "-c", "-d", "-r", "-t", "-u"}
CD = {"cd", "chdir", "set-location", "sl", "pushd"}
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
GITBASH_DRIVE = re.compile(r"^/([A-Za-z])(?:/|$)")
GIT_ALWAYS = {"add", "am", "checkout", "cherry-pick", "commit", "merge", "mv", "pull", "rebase", "reset",
              "restore", "revert", "rm", "switch", "update-ref", "update-index"}
GIT_BRANCH_EDIT = set("dDmMfcC")
TAG_READ = {"-l", "--list", "-v", "--verify", "-n", "--contains", "--no-contains", "--merged", "--no-merged",
            "--points-at", "--sort", "--column"}
PS_TARGET = {"path", "literalpath", "filepath", "destination"}
PS_VALUE = {"value", "encoding", "itemtype", "name", "newname", "filter", "include", "exclude", "width",
            "stream", "credential", "erroraction", "errorvariable", "pipelinevariable"}
WRITE_ALL = {"rm", "rmdir", "unlink", "del", "erase", "rd", "remove-item", "ri", "touch", "mkdir", "md", "tee"}
WRITE_FIRST = {"set-content", "sc", "add-content", "ac", "out-file", "clear-content", "clc", "new-item", "ni",
               "rename-item", "rni", "ren"}
COPY = {"cp", "copy", "copy-item", "cpi"}
MOVE = {"mv", "move", "move-item", "mi"}
VALUE_OPTS = {"touch": {"t", "d", "r", "date", "reference"}, "mkdir": {"m", "mode"}, "md": {"m", "mode"},
              "cp": {"t", "target-directory", "suffix"}, "mv": {"t", "target-directory", "suffix"},
              "ln": {"t", "target-directory", "suffix"}}


class Word:
    __slots__ = ("text", "opaque")

    def __init__(self, text: str, opaque: bool):
        self.text, self.opaque = text, opaque


class Segment:
    def __init__(self):
        self.words: list[Word] = []
        self.redirects: list[Word] = []


def read_word(text: str, i: int) -> tuple[Word | None, int]:
    """One shell word from `i`: quotes and escapes resolved, `$`, backtick and globs mark it opaque."""
    chars: list[str] = []
    opaque = quoted = False
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n;&|()<>":
            break
        if c == "'":
            quoted = True
            end = text.find("'", i + 1)
            end = n if end < 0 else end
            chars.append(text[i + 1:end])
            i = end + 1
        elif c == '"':
            quoted = True
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n and text[i + 1] in '"\\$`':
                    i += 1
                elif text[i] in "$`":
                    opaque = True
                chars.append(text[i])
                i += 1
            i += 1
        elif c == "\\" and i + 1 < n and text[i + 1] in " \"'$;&|<>()":
            chars.append(text[i + 1])
            i += 2
        else:
            if c in "$`*?[%":
                opaque = True
            chars.append(c)
            i += 1
    if not chars and not quoted:
        return None, i
    return Word("".join(chars), opaque), i


def segments(text: str) -> list[Segment]:
    found: list[Segment] = []
    current = Segment()
    heredocs: list[str] = []
    i, n = 0, len(text)

    def close() -> None:
        nonlocal current
        if current.words or current.redirects:
            found.append(current)
        current = Segment()

    def skip_blank() -> None:
        nonlocal i
        while i < n and text[i] in " \t\r":
            i += 1

    while i < n:
        c = text[i]
        if c in " \t\r":
            i += 1
        elif c == "\n":
            close()
            i += 1
            while heredocs and i <= n:
                end = text.find("\n", i)
                line, i = (text[i:], n + 1) if end < 0 else (text[i:end], end + 1)
                if line.strip() == heredocs[0]:
                    heredocs.pop(0)
        elif c in ";|()":
            close()
            i += 2 if c == "|" and text[i + 1:i + 2] == "|" else 1
        elif c == "&" and text[i + 1:i + 2] == ">":
            i += 2 + (text[i + 2:i + 3] == ">")
            skip_blank()
            word, i = read_word(text, i)
            if word:
                current.redirects.append(word)
        elif c == "&":
            close()
            i += 2 if text[i + 1:i + 2] == "&" else 1
        elif c == ">":
            i += 1 + (text[i + 1:i + 2] == ">")
            dup = text[i:i + 1] == "&"
            i += text[i:i + 1] in ("&", "|")
            skip_blank()
            word, i = read_word(text, i)
            if word and not (dup and re.fullmatch(r"\d+|-", word.text)):
                current.redirects.append(word)
        elif c == "<" and text[i + 1:i + 3] == "<<":
            i += 3
        elif c == "<" and text[i + 1:i + 2] == "<":
            i += 2 + (text[i + 2:i + 3] == "-")
            skip_blank()
            word, i = read_word(text, i)
            if word:
                heredocs.append(word.text)
        elif c == "<":
            i += 1
            skip_blank()
            _, i = read_word(text, i)
        elif c in "{}" and (i + 1 >= n or text[i + 1] in " \t\r\n;"):
            close()
            i += 1
        else:
            word, i = read_word(text, i)
            if word is None:
                i += 1
            elif re.fullmatch(r"\d+", word.text) and text[i:i + 1] in (">", "<") and not word.opaque:
                continue
            else:
                current.words.append(word)
    close()
    return found


def resolve(word: Word, cwd: Path | None) -> Path | None:
    """The absolute path a literal word names, or None when it is opaque or relative to an unknown folder."""
    text = word.text
    if word.opaque or not text or text.lower() in NO_TARGET:
        return None
    if text.startswith("~"):
        text = os.path.expanduser(text)
    if os.name == "nt":
        drive = GITBASH_DRIVE.match(text)
        if drive:
            text = f"{drive.group(1)}:/" + text[drive.end():]
    rooted = text.startswith(("/", "\\")) or bool(re.match(r"^[A-Za-z]:[\\/]", text))
    if rooted:
        return Path(os.path.abspath(text))
    return Path(os.path.normpath(cwd / text)) if cwd is not None else None


def program_of(word: Word) -> str:
    name = re.split(r"[\\/]", word.text)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def strip_prefixes(words: list[Word]) -> list[Word]:
    """Drop `VAR=1`, `env`, `sudo`, `time` and similar wrappers; [] when the program is opaque."""
    words = list(words)
    while words:
        head = words[0]
        if head.opaque:
            return []
        if ASSIGN.match(head.text):
            words.pop(0)
        elif head.text.lower() in WRAPPERS:
            wrapper = head.text.lower()
            words.pop(0)
            while words and not words[0].opaque and (words[0].text.startswith("-") or ASSIGN.match(words[0].text)):
                option = words.pop(0).text
                if wrapper == "sudo" and option in SUDO_VALUE and words:
                    words.pop(0)
                if wrapper == "command" and option in ("-v", "-V"):
                    return []
        else:
            break
    return words


def option_name(text: str) -> str:
    return text.lstrip("-").split(":", 1)[0].lower()


def parse(words: list[Word], value_opts: set[str] = frozenset()) -> tuple[list[Word], list[Word], list[Word]]:
    """(positionals, target-parameter values, destination values) of a writer's arguments."""
    positional: list[Word] = []
    targets: list[Word] = []
    destination: list[Word] = []
    i = 0
    ended = False
    while i < len(words):
        word = words[i]
        i += 1
        text = word.text
        if ended or word.opaque and not text.startswith("-") or not text.startswith("-") or len(text) < 2:
            positional.append(word)
        elif text == "--":
            ended = True
        else:
            name = option_name(text)
            attached = None
            if "=" in name or ":" in text.split("-")[-1] and text.startswith("-") and ":" in text:
                attached = text.split("=", 1)[1] if "=" in text else text.split(":", 1)[1]
                name = name.split("=", 1)[0]
            takes_value = name in PS_TARGET or name in PS_VALUE or name in value_opts
            value = Word(attached, word.opaque) if attached is not None else (
                words[i] if takes_value and i < len(words) else None)
            if attached is None and takes_value and value is not None:
                i += 1
            if value is not None and (name in PS_TARGET or name in ("t", "target-directory")):
                (destination if name in ("destination", "t", "target-directory") else targets).append(value)
    return positional, targets, destination


def inplace_files(prog: str, words: list[Word]) -> list[Word]:
    """The files `sed -i` / `perl -i` edit, or [] when the command is not an in-place edit."""
    inplace = script = False
    positional: list[Word] = []
    i = 0
    while i < len(words):
        text = words[i].text
        i += 1
        if text == "--":
            positional.extend(words[i:])
            break
        if text.startswith("--") and prog == "sed":
            inplace = inplace or text.split("=")[0] == "--in-place"
            if text.split("=")[0] in ("--expression", "--file"):
                script = True
                i += "=" not in text
        elif text.startswith("-") and len(text) > 1:
            for pos, char in enumerate(text[1:], 1):
                if char == "i":
                    inplace = True
                    break
                if char in ("e", "f", "E") and not (prog == "sed" and char == "E"):
                    script = True
                    i += pos == len(text) - 1
                    break
        else:
            positional.append(words[i - 1])
    if not inplace:
        return []
    return positional if script else positional[1:]


def git_resources(words: list[Word], cwd: Path | None, syncs: list | None = None) -> list[Path]:
    i, workdir, gitdir = 1, None, None
    while i < len(words):
        text = words[i].text
        if text in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path") and i + 1 < len(words):
            value = words[i + 1]
            i += 2
            if text == "-C":
                cwd = resolve(value, cwd)
            elif text == "--git-dir":
                gitdir = value
            elif text == "--work-tree":
                workdir = value
        elif text.startswith("--git-dir=") or text.startswith("--work-tree="):
            value = Word(text.split("=", 1)[1], words[i].opaque)
            gitdir, workdir = (value, workdir) if text.startswith("--git-dir") else (gitdir, value)
            i += 1
        elif text.startswith("-"):
            i += 1
        else:
            break
    if i >= len(words):
        return []
    verb = words[i].text.lower()
    args = [w.text for w in words[i + 1:]]
    found: list[Path] = []
    folder = resolve(workdir, cwd) if workdir else resolve(gitdir, cwd) if gitdir else cwd
    for pos, arg in enumerate(args):
        if arg.startswith("--output="):
            found.extend(filter(None, [resolve(Word(arg[9:], False), cwd)]))
        elif arg == "--output" and pos + 1 < len(args):
            found.extend(filter(None, [resolve(words[i + 2 + pos], cwd)]))
    if verb == "pull" and syncs is not None and folder is not None and ff_pull(args) is not None:
        syncs.append((folder, *ff_pull(args)))
    elif git_mutates(verb, args) and folder is not None:
        found.insert(0, folder)
    return found


def ff_pull(args: list[str]) -> tuple[str | None, str | None] | None:
    """`(remote, branch)` of `pull --ff-only [<remote> <branch>]`, else None: any other option is not a sync."""
    if args.count("--ff-only") != 1:
        return None
    rest = [a for a in args if a != "--ff-only"]
    if any(a.startswith("-") for a in rest) or len(rest) not in (0, 2):
        return None
    return (rest[0], rest[1]) if rest else (None, None)


def git_mutates(verb: str, args: list[str]) -> bool:
    shorts = [a[1:] for a in args if a.startswith("-") and not a.startswith("--")]
    if verb in GIT_ALWAYS:
        return True
    if verb == "apply":
        return not {"--check", "--stat", "--numstat", "--summary"} & set(args)
    if verb == "clean":
        return not ("--dry-run" in args or any("n" in s for s in shorts))
    if verb == "stash":
        return not (args and args[0] in ("list", "show"))
    if verb == "tag":
        if any(a.split("=")[0] in TAG_READ for a in args) or any(set(s) & {"l", "n", "v"} for s in shorts):
            return False
        return bool([a for a in args if not a.startswith("-")]) or any(set(s) & set("dasfmu") for s in shorts) \
            or "--delete" in args
    if verb == "branch":
        return bool({"--delete", "--move", "--force", "--copy"} & set(args)) \
            or any(set(s) & GIT_BRANCH_EDIT for s in shorts)
    if verb == "worktree":
        return bool(args) and args[0] in ("move", "remove")
    return state_mutates(verb, args, shorts)


def state_mutates(verb: str, args: list[str], shorts: list[str]) -> bool:
    """Verbs that write the repository's shared state (`.git`) or its tree outside GIT_ALWAYS."""
    plain = [a for a in args if not a.startswith("-")]
    if verb == "config":
        if {"--global", "--system", "--file", "-f"} & set(args) or any(a.startswith("--file=") for a in args):
            return False
        if any(a.startswith(("--get", "--show", "--name-only", "--list")) for a in args) or "-l" in args:
            return False
        return len(plain) > 1 or bool({"--add", "--unset", "--unset-all", "--replace-all", "--edit", "-e",
                                       "--rename-section", "--remove-section"} & set(args))
    if verb == "sparse-checkout":
        return not (plain and plain[0] == "list")
    if verb == "submodule":
        return bool(plain) and plain[0] not in ("status", "summary", "foreach")
    if verb == "read-tree":
        return any("u" in s for s in shorts)
    if verb == "symbolic-ref":
        return len(plain) >= 2 or bool({"-d", "--delete"} & set(args))
    if verb == "notes":
        return bool(plain) and plain[0] in ("add", "append", "edit", "remove", "prune", "merge", "copy")
    if verb == "replace":
        return bool(plain) and not ({"-l", "--list", "--format"} & set(args))
    return verb == "checkout-index"


def writer_targets(prog: str, words: list[Word]) -> list[Word]:
    rest = words[1:]
    if prog in ("sed", "perl"):
        return inplace_files(prog, rest)
    key = "cp" if prog in COPY else "mv" if prog in MOVE else "ln" if prog == "ln" else prog
    positional, targets, destination = parse(rest, VALUE_OPTS.get(key, set()))
    if prog in WRITE_ALL:
        return positional + targets
    if prog in WRITE_FIRST:
        return targets or positional[:1]
    if prog in COPY:
        return destination or (targets + positional[-1:] if len(positional) + len(targets) > 1 else [])
    if prog in MOVE:
        every = positional + targets + destination
        return every if len(every) > 1 or destination else []
    if prog == "ln":
        return destination or (positional[-1:] if len(positional) > 1 else [])
    return []


def resources(command: str, cwd: Path, syncs: list | None = None) -> list[Path]:
    """Absolute paths the command changes (a folder for a git verb, a target for a writer), in order.

    With `syncs` a list, a `git pull --ff-only` is appended as (folder, remote, branch), not returned.
    """
    found: list[Path] = []
    here: Path | None = cwd
    for segment in segments(command):
        for target in segment.redirects:
            path = resolve(target, here)
            if path is not None:
                found.append(path)
        words = strip_prefixes(segment.words)
        if not words:
            continue
        prog = program_of(words[0])
        if prog in CD:
            _, targets, _ = parse(words[1:])
            positional = parse(words[1:])[0]
            chosen = (targets or positional[:1])
            here = resolve(chosen[0], here) if chosen and chosen[0].text != "-" else None
        elif prog == "git":
            found.extend(git_resources(words, here, syncs))
        else:
            for word in writer_targets(prog, words):
                path = resolve(word, here)
                if path is not None:
                    found.append(path)
    unique: list[Path] = []
    for path in found:
        if path not in unique:
            unique.append(path)
    return unique

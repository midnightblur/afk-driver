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
KEYWORDS = {"if", "then", "elif", "else", "while", "until", "do", "!"}  # the next word is a program
SUDO_VALUE = {"-u", "-g", "-h", "-p", "-c", "-d", "-r", "-t", "-D", "--user", "--group", "--host", "--prompt",
              "--chdir", "--role", "--type", "--close-from"}
ENV_VALUE = {"-u", "--unset"}
ENV_CHDIR = {"-C", "--chdir"}
GIT_ENV = {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR"}
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PS_GIT_ENV = re.compile(r"^\$env:(GIT_DIR|GIT_WORK_TREE|GIT_COMMON_DIR)(?:=(.*))?$", re.I | re.S)
EXPANDS = ("$(", "`", "<(")
CD = {"cd", "chdir", "set-location", "sl", "pushd", "push-location"}
PUSH = {"pushd", "push-location"}
POP = {"popd", "pop-location"}
TOPLEVEL = re.compile(r"^(?:\$\(git rev-parse --show-toplevel\)|`git rev-parse --show-toplevel`)([\\/][\w.\\/-]*)?$")
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
CONTINUATION = re.compile(r"[\\`]\r?\n")  # Bash `\` and PowerShell backtick, outside comments and single quotes
GITBASH_DRIVE = re.compile(r"^/([A-Za-z])(?:/|$)")
GIT_ALWAYS = {"add", "am", "checkout", "cherry-pick", "commit", "merge", "mv", "pull", "rebase", "reset",
              "restore", "revert", "rm", "switch", "update-ref", "update-index"}
GIT_BRANCH_EDIT = set("dDmMfcCu")
BRANCH_CONFIG = {"--delete", "--move", "--force", "--copy", "--set-upstream-to", "--unset-upstream",
                 "--edit-description"}
PULL_QUIET = {"-q", "--quiet", "-v", "--verbose", "--progress", "--no-progress", "-p", "--prune", "--no-prune"}
TAG_READ = {"-l", "--list", "-v", "--verify", "-n", "--contains", "--no-contains", "--merged", "--no-merged",
            "--points-at", "--sort", "--column"}
PS_TARGET = {"path", "literalpath", "filepath", "destination"}
PS_VALUE = {"inputobject", "outvariable", "variable", "value", "encoding", "itemtype", "name", "newname", "filter", "include", "exclude", "width",
            "stream", "credential", "erroraction", "errorvariable", "pipelinevariable"}
WRITE_ALL = {"rm", "rmdir", "unlink", "del", "erase", "rd", "remove-item", "ri", "touch", "mkdir", "md", "tee"}
WRITE_FIRST = {"tee-object", "set-content", "sc", "add-content", "ac", "out-file", "clear-content", "clc", "new-item", "ni",
               "rename-item", "rni", "ren"}
PS_ONLY = {"ri", "sc", "ac", "clc", "ni", "rni", "cpi", "mi", "del", "erase", "rd", "md", "copy", "move", "ren"}
PS_SHARED = {"rm", "rmdir", "cp", "mv", "mkdir", "tee"}  # a Unix writer too: exempt only in the PowerShell tool
CMDLET = re.compile(r"^[a-z]+-[a-z]+$")
COPY = {"cp", "copy", "copy-item", "cpi"}
MOVE = {"mv", "move", "move-item", "mi"}
VALUE_OPTS = {"touch": {"t", "d", "r", "date", "reference"}, "mkdir": {"m", "mode"}, "md": {"m", "mode"},
              "cp": {"t", "target-directory", "suffix"}, "mv": {"t", "target-directory", "suffix"},
              "ln": {"t", "target-directory", "suffix"}}


class Word:
    __slots__ = ("text", "opaque", "split")

    def __init__(self, text: str, opaque: bool, split: bool | None = None):
        self.text, self.opaque = text, opaque
        self.split = opaque if split is None else split  # an unquoted expansion can become several words


class Segment:
    def __init__(self):
        self.words: list[Word] = []
        self.redirects: list[Word] = []
        self.piped = False  # part of a pipeline: runs in a subshell
        self.mark = ""  # "open" / "close" for a `(` / `)` boundary
        self.expands = False  # an unquoted heredoc body runs a substitution
        self.git_env: list[tuple[str, Word | None]] = []  # set by steps(); None is an opaque value


def read_word(text: str, i: int) -> tuple[Word | None, int]:
    """One shell word from `i`: quotes and escapes resolved, `$`, backtick and globs mark it opaque."""
    chars: list[str] = []
    opaque = quoted = split = False
    n = len(text)
    while i < n:
        c = text[i]
        joined = CONTINUATION.match(text, i)
        if joined:
            i = joined.end()
            continue
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
                joined = CONTINUATION.match(text, i)
                if joined:
                    i = joined.end()
                    continue
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
                opaque = split = True
            chars.append(c)
            i += 1
    if not chars and not quoted:
        return None, i
    return Word("".join(chars), opaque, split), i


def segments(text: str) -> list[Segment]:
    found: list[Segment] = []
    current = Segment()
    heredocs: list[tuple[str, bool, Segment]] = []  # delimiter, body expands, the segment it feeds
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
        joined = CONTINUATION.match(text, i)
        if joined:
            i = joined.end()
        elif c in " \t\r":
            i += 1
        elif c == "\n":
            close()
            i += 1
            while heredocs and i <= n:
                end = text.find("\n", i)
                line, i = (text[i:], n + 1) if end < 0 else (text[i:end], end + 1)
                delimiter, expanding, fed = heredocs[0]
                if line.strip() == delimiter:
                    heredocs.pop(0)
                elif expanding and any(mark in line for mark in EXPANDS):
                    fed.expands = True
        elif c in "()":
            close()
            found.append(Segment())
            found[-1].mark = "open" if c == "(" else "close"
            i += 1
        elif c in ";|":
            double = c == "|" and text[i + 1:i + 2] == "|"
            piped = c == "|" and not double
            current.piped = current.piped or piped
            close()
            current.piped = piped
            i += 2 if double else 1
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
            start = i
            word, i = read_word(text, i)
            if word:
                quoted = any(c in text[start:i] for c in "'\"\\")
                heredocs.append((word.text, not quoted, current))
        elif c == "<":
            i += 1
            skip_blank()
            _, i = read_word(text, i)
        elif c in "{}" and (i + 1 >= n or text[i + 1] in " \t\r\n;"):
            close()
            i += 1
        elif c == "#":  # a comment runs to the line end; a trailing `\` or backtick does not continue it
            end = text.find("\n", i)
            i = n if end < 0 else end
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
    """The program a word names: its last path part, lowercased, without a Windows launcher suffix."""
    name = re.split(r"[\\/]", word.text)[-1].lower()
    return re.sub(r"\.(?:exe|cmd|bat|ps1)$", "", name)


def strip_prefixes(words: list[Word], effects: dict | None = None, keywords: bool = False) -> list[Word]:
    """Drop `VAR=1`, `env`, `sudo`, `time` and similar wrappers; [] when the program is opaque.

    `effects["chdir"]` receives the folder word of `env -C`, `effects["git_env"]` each
    `GIT_DIR`-style assignment, and `effects["opaque"]` is set when the program cannot be read
    (an opaque word or `env -S`). With `keywords`, `then`/`do`-style control words are dropped
    too; mutation analysis leaves them, so a branch `cd` is no `cd`.
    """
    words = list(words)
    effects = effects if effects is not None else {}

    def assign(word: Word) -> None:
        name, _, value = word.text.partition("=")
        if name in GIT_ENV:
            effects.setdefault("git_env", []).append((name, Word(value, word.opaque)))

    while words:
        head = words[0]
        if ASSIGN.match(head.text) or (keywords and head.text in KEYWORDS and not head.opaque):
            assign(words.pop(0))
        elif head.opaque:
            effects["opaque"] = True
            return []
        elif head.text.lower() in WRAPPERS:
            wrapper = head.text.lower()
            words.pop(0)
            while words and (words[0].text.startswith("-") or ASSIGN.match(words[0].text)):
                if words[0].opaque and not ASSIGN.match(words[0].text):
                    effects["opaque"] = True
                    return []
                popped = words.pop(0)
                option = popped.text
                if ASSIGN.match(option):
                    assign(popped)
                    continue
                if wrapper == "env" and (option.startswith("--split-string") or (
                        not option.startswith("--") and "S" in option)):
                    effects["opaque"] = True  # the program is inside the split string
                    return []
                if wrapper == "sudo" and (option in ("-D", "--chdir") or option.startswith("--chdir=")):
                    folder = words.pop(0) if option in ("-D", "--chdir") and words else (
                        Word(option[8:], False) if option.startswith("--chdir=") else None)
                    if folder is not None:
                        effects["chdir"] = folder
                elif wrapper == "sudo" and option in SUDO_VALUE and words:
                    words.pop(0)
                if wrapper == "env" and option in ENV_VALUE and words:
                    words.pop(0)
                if wrapper == "env":
                    if option in ENV_CHDIR and words:
                        effects["chdir"] = words.pop(0)
                    elif option.startswith("--chdir="):
                        effects["chdir"] = Word(option[8:], popped.opaque)
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


def git_options(words: list[Word], cwd: Path | None,
                visited: list | None = None) -> tuple[int, Path | None, Word | None, Word | None]:
    """(index of the verb, folder after every `-C`, `--git-dir` word, `--work-tree` word) of a git command."""
    i, workdir, gitdir = 1, None, None
    while i < len(words):
        text = words[i].text
        if text in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path") and i + 1 < len(words):
            value = words[i + 1]
            i += 2
            if text == "-C":
                cwd = cwd if not value.opaque and not value.text else resolve(value, cwd)
                if visited is not None and cwd is not None:
                    visited.append(cwd)
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
    return i, cwd, gitdir, workdir


def git_folder(words: list[Word], cwd: Path | None) -> Path | None:
    """The work tree a git command acts on (`-C`, `--git-dir`, `--work-tree` applied), or None when unknown."""
    _, cwd, gitdir, workdir = git_options(words, cwd)
    chosen = workdir or gitdir
    return resolve(chosen, cwd) if chosen is not None else cwd


def git_resources(words: list[Word], cwd: Path | None, syncs: list | None = None,
                  visited: list | None = None, pulls: list | None = None) -> list[Path]:
    i, cwd, gitdir, workdir = git_options(words, cwd, visited)
    if i >= len(words):
        return []
    verb = words[i].text.lower()
    args = [w.text for w in words[i + 1:]]
    found: list[Path] = []
    repo = resolve(gitdir, cwd) if gitdir else cwd
    folder = resolve(workdir, cwd) if workdir else repo
    for pos, arg in enumerate(args):
        if arg.startswith("--output="):
            found.extend(filter(None, [resolve(Word(arg[9:], words[i + 1 + pos].opaque), cwd)]))
        elif arg == "--output" and pos + 1 < len(args):
            found.extend(filter(None, [resolve(words[i + 2 + pos], cwd)]))
    if verb == "pull" and syncs is not None and folder is not None and ff_pull(args) is not None:
        syncs.append((folder, *ff_pull(args)))
    elif git_mutates(verb, args) and (folder is not None or repo is not None):
        found = [path for path in (repo, folder) if path is not None] + found
        if verb == "pull" and pulls is not None:
            pulls.extend(path for path in (repo, folder) if path is not None)
    return found


def ff_pull(args: list[str]) -> tuple[str | None, str | None] | None:
    """`(remote, branch)` of `pull --ff-only [<remote> <branch>]`, else None: any other option is not a sync."""
    if args.count("--ff-only") != 1:
        return None
    rest = [a for a in args if a != "--ff-only" and a not in PULL_QUIET]
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
        return bool(BRANCH_CONFIG & {a.split("=")[0] for a in args}) \
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


def writer_targets(prog: str, words: list[Word], powershell: bool = False) -> list[Word]:
    rest = words[1:]
    exe = words[0].text.lower().endswith(".exe")
    if not exe and (CMDLET.match(prog) or prog in PS_ONLY or (powershell and prog in PS_SHARED)) and any(
            w.text.lower() in ("-whatif", "-whatif:$true") for w in rest):
        return []
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
        if destination or len(positional) > 1:
            return destination or positional[-1:]
        one = positional[0] if positional else None
        if not one or not one.text.strip("/\\"):
            return []
        return [Word(re.split(r"[\\/]", one.text.rstrip("/\\"))[-1], one.opaque)]
    return []


def cd_target(words: list[Word], here: Path | None, toplevel=None) -> Path | None:
    """The folder a `cd`-class command moves to, or None when it is not literal.

    `toplevel(folder)` answers the one substitution read: the repository root, `git rev-parse --show-toplevel`.
    """
    root = TOPLEVEL.match(" ".join(w.text for w in words[1:]))
    if root:
        found = toplevel(here) if toplevel is not None and here is not None else None
        return resolve(Word(str(found) + (root.group(1) or ""), False), None) if found is not None else None
    positional, targets, _ = parse(words[1:])
    chosen = targets or positional[:1]
    if not chosen:
        return Path.home() if len(words) == 1 else None
    return resolve(chosen[0], here) if chosen[0].text != "-" else None


def stack_only(words: list[Word]) -> bool:
    """`pushd`/`popd` with `-n`, `+N` or `-N`, or a bare `pushd`: a stack edit the folder model does not follow."""
    args = [w.text for w in words[1:]]
    return (program_of(words[0]) in PUSH | POP and any(re.fullmatch(r"-n|[+-]\d+", a) for a in args)) or (
        program_of(words[0]) == "pushd" and not args)


def exported(words: list[Word], powershell: bool, assigned: dict | None = None) -> list[tuple[str, Word | None]]:
    """The git variables an `export` or a PowerShell `$env:` assignment sets for later segments.

    A bare `export NAME` carries the value `assigned` holds for it; an unknown value is None.
    """
    match = PS_GIT_ENV.match(words[0].text) if powershell and words else None
    if match:
        if match.group(2) is not None:
            value = Word(match.group(2), any(c in match.group(2) for c in "$`*?"))
        else:
            value = words[2] if len(words) > 2 and words[1].text == "=" else None
        return [(match.group(1).upper(), value)]
    if not words or words[0].text != "export" or unexports(words):
        return []
    found: list[tuple[str, Word | None]] = []
    for word in words[1:]:
        name, equals, value = word.text.partition("=")
        if name in GIT_ENV:
            found.append((name, Word(value, word.opaque) if equals else (assigned or {}).get(name)))
        elif word.opaque and not ASSIGN.match(word.text):
            found.append(("GIT_DIR", None))  # an opaque name could be any git variable
    return found


def unexports(words: list[Word]) -> bool:
    """An `export` with an `n` flag: it removes names from the environment."""
    return bool(words) and words[0].text == "export" and any(
        w.text.startswith("-") and "n" in w.text for w in words[1:])


def unexported(words: list[Word]) -> list[tuple[str, bool]] | None:
    """(name, keeps its shell value) per git variable `unset [-v] NAME…` or `export -n NAME…` removes;
    None for any other `unset` or `export -n` shape, which leaves every git variable unknown."""
    if not words or not (words[0].text == "unset" or unexports(words)):
        return []
    flag = "-n" if words[0].text == "export" else "-v"
    names = words[1:]
    if names[:1] and names[0].text == flag and not names[0].opaque:
        names = names[1:]
    elif flag == "-n":
        return None
    if any(w.opaque or not IDENTIFIER.match(w.text) for w in names):
        return None
    return [(w.text, flag == "-n") for w in names if w.text in GIT_ENV]


def steps(command: str, cwd: Path | None, powershell: bool = False, toplevel=None):
    """(segment, words without wrappers, folder it runs in, folder before it) per command segment.

    A `cd`, `pushd` or `popd` outside a pipeline moves later segments; a folder change inside `( )`
    ends at the `)` unless `powershell`. A folder is None when it is not literal. `toplevel` is
    passed to `cd_target`.
    """
    here: Path | None = cwd
    saved: list[tuple[Path | None, dict, dict]] = []
    pushed: list[Path | None] = []
    git_env: dict[str, Word | None] = {}
    assigned: dict[str, Word | None] = {}  # shell variables a later bare `export` exports
    for segment in segments(command):
        if segment.mark:
            if segment.mark == "open":
                saved.append((here, dict(git_env), dict(assigned)))
            elif saved:
                kept, kept_env, kept_vars = saved.pop()
                if not powershell:
                    here, git_env, assigned = kept, kept_env, kept_vars
            continue
        effects: dict = {}
        words = strip_prefixes(segment.words, effects)
        spot = resolve(effects["chdir"], here) if effects.get("chdir") else here
        segment.git_env = list(git_env.items()) + list(effects.get("git_env", []))
        yield segment, words, spot, here
        prog = program_of(words[0]) if words else ""
        if segment.piped:
            continue
        if not words and not effects.get("opaque"):
            for name, value in effects.get("git_env", []):  # a bare assignment; an exported name stays exported
                assigned[name] = value
                if name in git_env:
                    git_env[name] = value
        removed = [] if powershell else unexported(words)
        if removed is None:
            for name in GIT_ENV:
                git_env[name] = assigned[name] = None
        for name, keep in removed or []:
            git_env.pop(name, None)
            if not keep:
                assigned.pop(name, None)
        for name, value in exported(segment.words if powershell else words, powershell, assigned):
            git_env[name] = assigned[name] = value
        if prog in PUSH | POP and stack_only(words):
            here = None
        elif prog in CD:
            if prog in PUSH:
                pushed.append(here)
            here = cd_target(words, here, None if git_env or effects.get("git_env") else toplevel)
        elif prog in POP:
            here = pushed.pop() if pushed else None


def resources(command: str, cwd: Path, syncs: list | None = None, visited: list | None = None,
              pulls: list | None = None, powershell: bool = False, toplevel=None) -> list[Path]:
    """Absolute paths the command changes (a folder for a git verb, a target for a writer), in order.

    With `syncs` a list, a `git pull --ff-only` is appended as (folder, remote, branch), not returned.
    With `visited` a list, every folder the command runs in or enters (cd, `-C`, `env -C`) is appended.
    With `pulls` a list, the folders of a mutating `git pull` are appended. `powershell` keeps a
    folder change made inside `( )` and lets `-WhatIf` exempt every writer. `toplevel` is passed to `steps`.
    """
    found: list[Path] = []
    if visited is not None:
        visited.append(cwd)
    for segment, words, spot, here in steps(command, cwd, powershell, toplevel):
        for target in segment.redirects:
            path = resolve(target, here)
            if path is not None:
                found.append(path)
        if not words:
            continue
        prog = program_of(words[0])
        if prog in CD:
            moved = cd_target(words, here, None if segment.git_env else toplevel)
            if visited is not None and moved is not None:
                visited.append(moved)
        elif prog == "git":
            if visited is not None and spot is not None:
                visited.append(spot)
            found.extend(git_resources(words, spot, syncs, visited, pulls))
        else:
            if visited is not None and spot is not None:
                visited.append(spot)
            for word in writer_targets(prog, words, powershell):
                path = resolve(word, spot)
                if path is not None:
                    found.append(path)
    unique: list[Path] = []
    for path in found:
        if path not in unique:
            unique.append(path)
    return unique

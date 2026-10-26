"""The guard's allow-list: the shell segments it can prove read-only.

`proven(words, redirects)` is True only for a listed program in a listed read-only form whose
redirects reach no file. An unlisted program, a path-qualified program, a write flag, a command
substitution (except a quoted proven one held by `cd`, `ls` or `cat`), an opaque argument to a form
whose flags decide what it does (outside a value-only position, `value_only`, or after the literal
`--` of `git`, `rg` or a forge `view`, or a git read's `--end-of-options`), or a PowerShell script
block is unproven. `shell_mutations` has already replaced each variable that holds a known literal. A proven forge `view` may still start a browser (`--web`).
protected_branch_guard runs only proven segments in a guarded placement; grow the list here, one
tested form at a time.
"""
from __future__ import annotations

import re

import shell_mutations as sm

PLAIN = {"cat", "ls", "dir", "pwd", "head", "tail", "wc", "grep", "egrep", "fgrep", "stat", "which", "type",
         "echo", "printf", "jq", "diff", "test", "[", "[[", "true", "false", ":", "cd", "chdir", "pushd", "popd",
         "whoami", "uname", "basename", "dirname", "realpath", "readlink", "tr", "cut", "column", "sleep",
         "for", "fi", "done", "read", "set", "export", "unset", "exit", "du", "df", "ps", "printenv", "id", "nl",
         "od", "sha256sum", "md5sum", "cmp", "comm", "paste", "seq", "strings", "nproc", "tasklist"}
CMDLETS = {"set-location", "sl", "push-location", "pop-location", "select-string", "sls", "test-path",
           "resolve-path", "join-path", "split-path", "write-output", "write-host", "select-object",
           "sort-object", "measure-object", "where-object", "format-table", "format-list", "out-string",
           "out-null", "out-host", "get-childitem", "gci", "get-content", "gc", "get-item", "gi",
           "get-itemproperty", "gp", "get-itempropertyvalue", "gpv", "get-location", "gl", "get-date",
           "get-filehash", "get-process", "gps", "get-service", "gsv", "get-variable", "gv", "get-member", "gm",
           "get-alias", "gal", "get-psdrive", "gdr", "get-acl", "get-unique", "gu", "get-host", "get-culture",
           "get-timezone", "convertto-json", "convertfrom-json", "compare-object", "group-object",
           "get-ciminstance"}
HELD_READERS = {"cd", "ls", "cat"}  # take a proven command's output as their operand
VERSION = {p: ("--version", "-V") for p in ("python", "python3", "py", "afk-python", "pip", "pip3", "uv")}
VERSION.update({"node": ("--version", "-v"), "npm": ("--version", "-v"), "java": ("--version", "-version"),
                "javac": ("--version", "-version"), "mvn": ("--version", "-v"), "gh": ("--version",),
                "glab": ("--version",), "docker": ("--version", "-v")})  # each read in its --help: prints, exits
GIT_LATE_OPTIONS = {"blame", "shortlog", "range-diff", "ls-remote"}  # read options after --end-of-options
GIT_SWITCHES = {"-p", "--patch", "-s", "--no-patch", "--stat", "--shortstat", "--numstat", "--name-only",
                "--name-status", "--oneline", "--graph", "--all", "--decorate", "--no-decorate", "--first-parent",
                "--no-merges", "--merges", "--reverse", "--cached", "--staged", "--raw", "--summary", "--verify",
                "--quiet", "-q", "-z", "--abbrev-commit", "--no-color", "--color", "--symbolic-full-name"}
GIT_FETCHES = ("--upload-pack", "--exec")  # runs the named program, also when abbreviated
RG_SWITCHES = "inSswFlcHNxvLuUPzaqobp0."
XARGS_VALUE = "adEILnPs"  # each takes the rest of the cluster or the next word
XARGS_LONG = {"arg-file", "delimiter", "max-lines", "max-args", "max-procs", "max-chars", "process-slot-var"}
XARGS_SWITCH_LONG = {"null", "no-run-if-empty", "open-tty", "interactive", "verbose", "exit", "show-limits"}
AWK_REFUSED = set("fEilopdDW")  # a program file, library, inplace edit, output file, debugger or `-W` option
AWK_REFUSED_LONG = ("--file", "--exec", "--include", "--load", "--pretty-print", "--profile", "--dump-variables",
                    "--debug")
AWK_RUNS = ("system", "|", ">", "getline", "@")  # a command, a pipe, a file write or read, a gawk directive
NPM_READ = {"ls": ({"-a", "--all", "--json", "-l", "--long", "-p", "--parseable", "-g", "--global", "--link",
                    "--package-lock-only", "--unicode", "--workspaces", "--include-workspace-root",
                    "--install-links"}, {"--depth", "--omit", "--include", "-w", "--workspace"}),
            "view": ({"--json", "--workspaces", "--include-workspace-root"}, {"-w", "--workspace"}),
            "outdated": ({"-a", "--all", "--json", "-l", "--long", "-p", "--parseable", "-g", "--global"},
                         {"-w", "--workspace", "--before", "--min-release-age"})}
NPM_READ.update({"list": NPM_READ["ls"], "show": NPM_READ["view"]})
PIP_QUIET = {"-v", "--verbose", "-q", "--quiet", "--isolated", "--disable-pip-version-check", "--no-color",
             "--no-input"}
PIP_READ = {"list": (PIP_QUIET | {"-o", "--outdated", "-u", "--uptodate", "-e", "--editable", "-l", "--local",
                                  "--user", "--not-required", "--exclude-editable", "--include-editable", "--pre",
                                  "--no-index"},
                     {"--path", "--format", "--exclude", "-i", "--index-url", "--extra-index-url", "-f",
                      "--find-links"}),
            "show": (PIP_QUIET | {"-f", "--files"}, set())}
XXD_VALUE = {"-c", "-cols", "-g", "-groupsize", "-l", "-len", "-n", "-name", "-o", "-offset", "-s", "-seek", "-R"}
DISPLAY_KEYS = ("color.", "log.")  # `-c` keys that only change how git prints
HERDR_READ = {("status",), ("pane", "list"), ("pane", "current"), ("pane", "get"), ("pane", "layout"),
              ("pane", "process-info"), ("pane", "neighbor"), ("pane", "edges"), ("pane", "read"),
              ("pane", "wait-output"), ("agent", "list"), ("agent", "get"), ("agent", "read"), ("agent", "wait"),
              ("agent", "explain"), ("workspace", "list"), ("workspace", "get"), ("tab", "list"), ("tab", "get"),
              ("worktree", "list"), ("session", "list"), ("api", "snapshot"), ("integration", "status"),
              ("machine", "list")}
FIND_VALUE = {"-name", "-iname", "-path", "-ipath", "-type"}  # each takes exactly one operand
FIND_TAKES = FIND_VALUE | {"-D", "-amin", "-anewer", "-atime", "-cmin", "-cnewer", "-ctime", "-context",
                          "-files0-from", "-fstype", "-gid", "-group", "-ilname", "-inum", "-iregex",
                          "-iwholename", "-links", "-lname", "-maxdepth", "-mindepth", "-mmin", "-mtime",
                          "-newer", "-perm", "-printf", "-regex", "-regextype", "-samefile", "-size", "-uid",
                          "-used", "-user", "-wholename", "-xtype"}  # each takes the next word as its value
VIEW_GROUPS = {"gh": {"pr", "issue", "run", "release", "repo"}, "glab": {"mr", "issue", "release", "repo"}}
FIND_WRITES = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"}
GIT_READERS = {"status", "log", "diff", "show", "grep", "rev-parse", "ls-files", "describe", "blame", "shortlog",
               "cat-file", "ls-tree", "merge-base", "for-each-ref", "rev-list", "name-rev", "check-ignore",
               "check-attr", "ls-remote", "show-ref", "show-branch", "whatchanged", "range-diff", "cherry",
               "count-objects", "var", "version", "help"}
GIT_OUTPUT = ("--output", "--open-files-in-pager")
GIT_CONFIG_READ = ("--get", "--list", "-l", "--show-origin", "--show-scope", "--name-only", "--null", "-z",
                   "--global", "--system", "--local", "--worktree", "--type", "--default", "--includes",
                   "--no-includes", "--bool", "--int", "--path")
FORGE_READ = {"view", "list", "status", "checks", "diff", "show", "watch"}
FORGE_API_WRITES = ("-X", "--method", "-f", "-F", "--field", "--raw-field", "--input")
CURL_SHORT_WRITES = set("oODcTdFXKJ")
CURL_LONG_WRITES = ("--output", "--remote-name", "--remote-header-name", "--create-dirs", "--dump-header",
                    "--cookie-jar", "--trace", "--stderr", "--libcurl", "--etag-save", "--hsts", "--alt-svc",
                    "--config", "--upload-file", "--data", "--form", "--json", "--request", "--post", "--put")
DOCKER_VALUE = {"-H", "--host", "-c", "--context", "--config", "-l", "--log-level", "--tlscacert", "--tlscert",
                "--tlskey"}
DOCKER_READ = {("ps",), ("logs",), ("inspect",), ("images",), ("version",), ("info",),
               ("container", "ls"), ("container", "ps"), ("container", "list"), ("container", "logs"),
               ("container", "inspect"), ("image", "ls"), ("image", "list"), ("image", "inspect"),
               ("compose", "ps"), ("compose", "logs")}


def proven_segment(segment: sm.Segment) -> bool:
    """`proven` for a parsed segment; a heredoc body that runs a substitution is unproven."""
    return not segment.expands and proven(segment.words, segment.redirects)


def proven(words: list[sm.Word], redirects: list[sm.Word]) -> bool:
    """True when the segment is a listed read-only form and every redirect reaches no file."""
    if any(not w.sink for w in redirects):
        return False
    effects: dict = {}
    stripped = sm.strip_prefixes(words, effects, keywords=True)
    if any(w.runs and not held_read(w, stripped) for w in words):
        return False
    if not stripped:
        return not effects.get("opaque")
    if re.search(r"[\\/]", stripped[0].text):
        return False
    prog = sm.program_of(stripped[0])
    args = [w.text for w in stripped[1:]]
    if prog in CMDLETS:
        return not any("{" in a for a in args)
    if len(stripped) == 2 and not stripped[1].opaque and args[0] in VERSION.get(prog, ()):
        return True
    if prog == "xargs":
        return _xargs(stripped[1:])
    check = FORMS.get(prog)
    if check is None:
        return prog in PLAIN
    ended = False
    ends = prog in ("git", "rg") or forge_view(prog, stripped[1:])  # every word after a literal `--` is an operand
    verb = git_verb(args) if prog == "git" else None
    for at, word in enumerate(stripped[1:]):
        ended = ended or (word.text == "--" and not word.opaque and ends) or (
            verb is not None and at > verb[0] and git_options_end(stripped[1:], at, verb))
        if word.opaque and not ended and not value_only(prog, stripped[1:], at):
            return False  # an expansion could become the flag that writes or runs a program
    return check(args)


def held_read(word: sm.Word, stripped: list[sm.Word]) -> bool:
    """A quoted `"$(…)"` operand of `cd`, `ls` or `cat` whose plain inner command is itself proven."""
    if word.inner is None or not stripped or sm.program_of(stripped[0]) not in HELD_READERS \
            or not any(word is w for w in stripped[1:]):
        return False
    inner = sm.segments(word.inner)
    return bool(inner) and all(not s.mark and proven_segment(s) for s in inner)


def git_verb(args: list[str]) -> tuple[int, str] | None:
    """(index, verb) of a git command's verb among its arguments, past the global options."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    return (i, args[i].lower()) if i < len(args) else None


def git_options_end(words: list[sm.Word], at: int, verb: tuple[int, str]) -> bool:
    """A literal `--end-of-options` that ends a reader verb's options: it is no value of the word before it."""
    word = words[at]
    if word.opaque or word.text != "--end-of-options" or verb[1] not in GIT_READERS - GIT_LATE_OPTIONS:
        return False
    before = words[at - 1]
    return at - 1 == verb[0] or (not before.opaque and (
        not before.text.startswith("-") or "=" in before.text or before.text in GIT_SWITCHES
        or bool(re.fullmatch(r"-\d+", before.text))))


def value_only(prog: str, words: list[sm.Word], at: int) -> bool:
    """An opaque word that can only be a value: a quoted `find` predicate operand, the quoted pattern of a
    literal `-e` given to `rg` that is no value itself, or the one opaque operand right after a forge `<group> view`."""
    if prog in VIEW_GROUPS:
        return at == 2 and forge_view(prog, words) and sum(w.opaque for w in words) == 1
    before = words[at - 1] if at else None
    if before is None or before.opaque or words[at].split:
        return False
    if prog == "find":
        value = False  # whether the next word is the value of a predicate
        for word in words[:at - 1]:
            value = not value and (word.text in FIND_TAKES or bool(re.fullmatch(r"-newer[aBcmt]{2}", word.text)))
        return not value and before.text in FIND_VALUE
    if prog != "rg" or before.text not in ("-e", "--regexp"):
        return False
    if at == 1:
        return True
    flag = words[at - 2]
    return not flag.opaque and (not flag.text.startswith("-") or flag.text.startswith("--") and "=" in flag.text
                                or bool(re.fullmatch(r"-[%s]+" % re.escape(RG_SWITCHES), flag.text)))


def forge_view(prog: str, words: list[sm.Word]) -> bool:
    """A literal `gh`/`glab` `<group> view`: after its `--` an expansion is the operand, never a flag."""
    head = words[:2]
    return (len(head) == 2 and all(not w.opaque for w in head) and head[0].text in VIEW_GROUPS.get(prog, ())
            and head[1].text == "view")


def _shorts(args: list[str]) -> str:
    """Every letter of the single-dash option clusters."""
    return "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--"))


def _find(args: list[str]) -> bool:
    return not any(a in FIND_WRITES for a in args)


def _sort(args: list[str]) -> bool:
    return "o" not in _shorts(args) and not any(a.startswith("--output") for a in args)


def _uniq(args: list[str]) -> bool:
    return len([a for a in args if not a.startswith("-")]) <= 1


def _rg(args: list[str]) -> bool:
    return not any(a.startswith("--pre") for a in args)


def _date(args: list[str]) -> bool:
    return "s" not in _shorts(args) and not any(a.startswith("--set") for a in args)


def _hostname(args: list[str]) -> bool:
    return all(a.startswith("-") for a in args)


def _sed(args: list[str]) -> bool:
    """No in-place edit, no script file, and no script holding a `w`, `W` or `e` (write, execute)."""
    scripts: list[str] = []
    positional: list[str] = []
    i = 0
    while i < len(args):
        text = args[i]
        i += 1
        if text == "--":
            positional.extend(args[i:])
            break
        if text.startswith("--"):
            name, _, value = text.partition("=")
            if name.startswith(("--in-place", "--file")):
                return False
            if name == "--expression":
                scripts.append(value if value else (args[i] if i < len(args) else ""))
                i += not value
        elif text.startswith("-") and len(text) > 1:
            for pos, char in enumerate(text[1:], 1):
                if char in "if":
                    return False
                if char in "el":
                    rest = text[pos + 1:]
                    value = rest or (args[i] if i < len(args) else "")
                    i += not rest
                    if char == "e":
                        scripts.append(value)
                    break
        else:
            positional.append(text)
    if not scripts and positional:
        scripts.append(positional[0])
    return not any(set(script) & set("wWe") for script in scripts)


def _curl(args: list[str]) -> bool:
    if CURL_SHORT_WRITES & set(_shorts(args)):
        return False
    return not any(a.startswith(CURL_LONG_WRITES) for a in args if a.startswith("--"))


def _herdr(args: list[str]) -> bool:
    if args in (["--version"], ["-V"], ["--help"], ["-h"]):
        return True
    if args[:1] == ["--session"]:
        args = args[2:]
    plain = [a for a in args if not a.startswith("-")]
    return (tuple(plain[:1]) in HERDR_READ or tuple(plain[:2]) in HERDR_READ) and "--trust-repository" not in args


def _docker(args: list[str]) -> bool:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in DOCKER_VALUE else 1
    plain = [a for a in args[i:] if not a.startswith("-")]
    return tuple(plain[:1]) in DOCKER_READ or tuple(plain[:2]) in DOCKER_READ


def _forge(args: list[str]) -> bool:
    plain = [a for a in args if not a.startswith("-")]
    if plain[:2] == ["api", "graphql"]:
        return _graphql(args)
    if plain[:1] == ["api"]:
        return not any(a.startswith(FORGE_API_WRITES) for a in args if a.startswith("-"))
    return len(plain) >= 2 and plain[1] in FORGE_READ


def _gh(args: list[str]) -> bool:
    return args[:1] == ["search"] or _forge(args)


def _graphql(args: list[str]) -> bool:
    """`gh api graphql` whose fields are literal, read no file, and hold no `mutation`."""
    i = 0
    while i < len(args):
        text = args[i]
        i += 1
        if text.startswith(("-X", "--method", "--input")):
            return False
        if text in ("-f", "-F", "--field", "--raw-field"):
            value = args[i] if i < len(args) else ""
            i += 1
        elif text.startswith(("--field=", "--raw-field=")):
            value = text.split("=", 1)[1]
        elif text.startswith(("-f", "-F")):
            value = text[2:].lstrip("=")
        else:
            continue
        if "mutation" in value.lower() or (text.startswith(("-F", "--field")) and "=@" in value):
            return False
    return True


def _git(args: list[str]) -> bool:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-c" and i + 1 < len(args) and _display_key(args[i + 1]):
            i += 2
            continue
        if args[i] in ("-c", "--exec-path", "--config-env") or args[i].startswith(("--exec-path=", "--config-env=")):
            return False  # a configured pager, editor or helper runs a program
        i += 2 if args[i] in ("-C", "--git-dir", "--work-tree", "--namespace") else 1
    if i >= len(args):
        return all(a in ("--version", "--help", "--no-pager") for a in args[:i]) and i > 0
    verb, rest = args[i].lower(), args[i + 1:]
    plain = [a for a in rest if not a.startswith("-")]
    if any(a.startswith(GIT_OUTPUT) or a.startswith("-O") for a in rest):
        return False
    if verb in ("fetch", "ls-remote") and any(
            len(a.split("=")[0]) > 2 and any(f.startswith(a.split("=")[0]) for f in GIT_FETCHES) for a in rest):
        return False
    if verb == "fetch":
        return not any(":" in a for a in plain) and "--update-head-ok" not in rest
    if verb == "branch":
        clusters = [a for a in rest if a.startswith("-") and not a.startswith("--")]
        return not plain and not sm.BRANCH_CONFIG & {a.split("=")[0] for a in rest} and not any(
            set(a[1:]) & sm.GIT_BRANCH_EDIT for a in clusters)
    if verb in ("remote", "tag", "stash", "worktree", "reflog", "config", "submodule"):
        return _git_listing(verb, rest, plain)
    return verb in GIT_READERS


def _git_listing(verb: str, rest: list[str], plain: list[str]) -> bool:
    """The read forms of the git verbs that also write."""
    if verb == "remote":
        return not plain or plain[0] in ("show", "get-url")
    if verb == "tag":
        return not sm.git_mutates("tag", rest)
    if verb == "stash":
        return plain[:1] in (["list"], ["show"])
    if verb == "worktree":
        return plain[:1] == ["list"]
    if verb == "reflog":
        return not plain or plain[0] not in ("expire", "delete", "write")
    if verb == "submodule":
        return plain[:1] in (["status"], ["summary"])
    return any(a.startswith(("--get", "--list")) or a == "-l" for a in rest) and all(
        a.startswith(GIT_CONFIG_READ) for a in rest if a.startswith("-"))


def _display_key(setting: str) -> bool:
    """A `-c` setting that only changes how git prints: no program, hook or signature check runs."""
    key, _, value = setting.partition("=")
    key = key.lower()
    return key == "core.quotepath" or (key == "core.pager" and value == "cat") or (
        key.startswith(DISPLAY_KEYS) and key != "log.showsignature")


def _xargs(words: list[sm.Word]) -> bool:
    """`xargs` whose options are literal and whose command is proven with the read items in its place."""
    replace = None
    i = 0
    while i < len(words) and words[i].text.startswith("-") and words[i].text != "-":
        word = words[i]
        i += 1
        if word.opaque:
            return False
        if word.text == "--":
            break
        if word.text.startswith("--"):
            name, equals, value = word.text[2:].partition("=")
            if name == "replace":
                replace = value if equals else "{}"
            elif name in XARGS_LONG:
                i += not equals
            elif name != "eof" and name not in XARGS_SWITCH_LONG:
                return False
            continue
        for pos, char in enumerate(word.text[1:], 1):
            rest = word.text[pos + 1:]
            if char in XARGS_VALUE or char in "eil":
                if char in XARGS_VALUE and not rest:
                    rest = words[i].text if i < len(words) else ""
                    i += 1
                if char == "I" or char == "i":
                    replace = rest or "{}"
                break
            if char not in "0oprtx":
                return False
    command = words[i:] or [sm.Word("echo", False)]
    if replace is None:
        return proven(command + [sm.Word("$item", True)], [])
    if replace in command[0].text:
        return False  # a read item would choose the program
    return proven([sm.Word(w.text, True, False) if replace in w.text else w for w in command], [])


def _awk(args: list[str]) -> bool:
    """No program file, library, inplace edit or output file, and no program text that runs a command,
    pipes, writes or reads through `getline`."""
    scripts: list[str] = []
    positional: list[str] = []
    i = 0
    while i < len(args):
        text = args[i]
        i += 1
        if text == "--" or not text.startswith("-") or text == "-":
            positional.extend(args[i - (text != "--"):])
            break
        if text.startswith("--"):
            name, equals, value = text.partition("=")
            if len(name) > 2 and any(r.startswith(name) for r in AWK_REFUSED_LONG):
                return False
            if len(name) > 2 and "--source".startswith(name):
                scripts.append(value if equals else (args[i] if i < len(args) else ""))
                i += not equals
            elif len(name) > 2 and any(v.startswith(name) for v in ("--field-separator", "--assign")):
                i += not equals
            continue
        for pos, char in enumerate(text[1:], 1):
            if char in AWK_REFUSED:
                return False
            if char in "Fve":
                value = text[pos + 1:] or (args[i] if i < len(args) else "")
                i += not text[pos + 1:]
                if char == "e":
                    scripts.append(value)
                break
    if not scripts:
        scripts = positional[:1]
    return bool(scripts) and not any(mark in script for script in scripts for mark in AWK_RUNS)


def _file(args: list[str]) -> bool:
    """No magic-file compile (it writes a `.mgc`) and no access-time restore."""
    return not set("Cp") & set(_shorts(args)) and not any(
        len(a.split("=")[0]) > 2 and any(f.startswith(a.split("=")[0]) for f in ("--compile", "--preserve-date"))
        for a in args if a.startswith("--"))


def _tree(args: list[str]) -> bool:
    """No `-o` output file and no `-R`, which writes a page in every folder."""
    return not set("oR") & set(_shorts(args))


def _xxd(args: list[str]) -> bool:
    """At most one file operand: a second one is the output file."""
    positional = 0
    i = 0
    while i < len(args):
        text = args[i]
        i += 1
        if text == "--":
            positional += len(args) - i
            break
        if text.startswith("-") and text != "-":
            i += text in XXD_VALUE
        else:
            positional += 1
    return positional <= 1


def _listing(table: dict, args: list[str]) -> bool:
    """A listed read verb first, then only its listed options, each value given literally."""
    if not args or args[0] not in table:
        return False
    switches, valued = table[args[0]]
    i = 1
    while i < len(args):
        text = args[i]
        i += 1
        if not text.startswith("-"):
            continue
        name, equals, _ = text.partition("=")
        if name in valued:
            i += not equals
        elif equals or name not in switches:
            return False
    return True


FORMS = {"find": _find, "sort": _sort, "uniq": _uniq, "rg": _rg, "date": _date, "hostname": _hostname,
         "sed": _sed, "curl": _curl, "docker": _docker, "gh": _gh, "glab": _forge, "git": _git,
         "herdr": _herdr, "awk": _awk, "gawk": _awk, "mawk": _awk, "nawk": _awk, "file": _file, "tree": _tree,
         "xxd": _xxd, "npm": lambda a: _listing(NPM_READ, a), "pip": lambda a: _listing(PIP_READ, a),
         "pip3": lambda a: _listing(PIP_READ, a), "where": lambda a: not any("{" in x for x in a)}

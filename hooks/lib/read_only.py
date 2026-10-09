"""The guard's allow-list: the shell segments it can prove read-only.

`proven(words, redirects)` is True only for a listed program in a listed read-only form whose
redirects reach no file. An unlisted program, a path-qualified program, a write flag, a command
substitution or a PowerShell script block is unproven. protected_branch_guard runs only proven
segments in a guarded placement; grow the list here, one tested form at a time.
"""
from __future__ import annotations

import re

import shell_mutations as sm

PLAIN = {"cat", "ls", "dir", "pwd", "head", "tail", "wc", "grep", "egrep", "fgrep", "stat", "which", "type",
         "echo", "printf", "jq", "diff", "test", "[", "[[", "true", "false", ":", "cd", "chdir", "pushd", "popd",
         "whoami", "uname", "basename", "dirname", "realpath", "readlink", "tr", "cut", "column", "sleep",
         "herdr", "for", "fi", "done", "read", "set", "export", "unset", "exit"}
CMDLETS = {"set-location", "sl", "push-location", "pop-location", "select-string", "sls", "test-path",
           "resolve-path", "join-path", "split-path", "write-output", "write-host", "gci", "gc", "select-object",
           "sort-object", "measure-object", "where-object", "format-table", "format-list", "out-string",
           "out-null", "out-host"}
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


def proven(words: list[sm.Word], redirects: list[sm.Word]) -> bool:
    """True when the segment is a listed read-only form and every redirect reaches no file."""
    if any(w.text.lower() not in sm.NO_TARGET for w in redirects):
        return False
    stripped = sm.strip_prefixes(words, keywords=True)
    if not stripped:
        return not any(w.opaque and not sm.ASSIGN.match(w.text) for w in words)
    if any(w.opaque and ("`" in w.text or "$(" in w.text) for w in stripped):
        return False
    if re.search(r"[\\/]", stripped[0].text):
        return False
    prog = sm.program_of(stripped[0])
    args = [w.text for w in stripped[1:]]
    if prog in CMDLETS or prog.startswith("get-"):
        return not any("{" in a for a in args)
    check = FORMS.get(prog)
    return check(args) if check else prog in PLAIN


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


def _docker(args: list[str]) -> bool:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in DOCKER_VALUE else 1
    plain = [a for a in args[i:] if not a.startswith("-")]
    return tuple(plain[:1]) in DOCKER_READ or tuple(plain[:2]) in DOCKER_READ


def _forge(args: list[str]) -> bool:
    plain = [a for a in args if not a.startswith("-")]
    if plain[:1] == ["api"]:
        return not any(a.startswith(FORGE_API_WRITES) for a in args if a.startswith("-"))
    return len(plain) >= 2 and plain[1] in FORGE_READ


def _git(args: list[str]) -> bool:
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] in ("-c", "--exec-path", "--config-env") or args[i].startswith(("--exec-path=", "--config-env=")):
            return False  # a configured pager, editor or helper runs a program
        i += 2 if args[i] in ("-C", "--git-dir", "--work-tree", "--namespace") else 1
    if i >= len(args):
        return all(a in ("--version", "--help", "--no-pager") for a in args[:i]) and i > 0
    verb, rest = args[i].lower(), args[i + 1:]
    plain = [a for a in rest if not a.startswith("-")]
    if any(a.startswith(GIT_OUTPUT) or a.startswith("-O") for a in rest):
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


FORMS = {"find": _find, "sort": _sort, "uniq": _uniq, "rg": _rg, "date": _date, "hostname": _hostname,
         "sed": _sed, "curl": _curl, "docker": _docker, "gh": _forge, "glab": _forge, "git": _git}

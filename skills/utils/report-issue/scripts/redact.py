#!/usr/bin/env python3
"""Strip everything but plugin-side context from outgoing issue text.

    redact.py --plugin-root P [--repo-root R] [--keep-repo OWNER/NAME]
              [--check] [-o OUT] [IN]

Reads IN (default stdin), writes the redacted text to OUT (default stdout).
Two passes:

1. Replace every sensitive shape with a placeholder. A URL goes first and
   whole (`<url>`, credentials and host included) unless it is the target
   repository or a public docs host; a `user:secret@host` authority goes whole
   with or without a scheme. Then: private keys, auth headers, secret names
   bound to a value by `:`, `=`, a space, or quotes (anywhere on a line, the
   quotes need not close), token and cloud-key shapes, addresses, account ids,
   handles, home paths, IPv4 and IPv6 addresses (zone id included), tracker
   ticket ids, the consuming repository's identity (root path, remote hosts,
   and every remote path segment: owner, group, name), and the git user's
   handles. A `<placeholder>` walls a rule off from the text around it, EXCEPT
   where it is a path segment (`skills/afk/<name>/SKILL.md`): there it is part of
   the path, which the path rule then judges whole.
   A secret name binds whatever its prefix or suffix (`GITLAB_TOKEN`,
   `MY_SECRET`), and takes a quoted value whole to its real closing quote:
   spaces, line breaks and escaped quotes included — but only to the end of its
   PARAGRAPH: a blank line ends the value whatever follows, so one stray quote
   takes the rest of its own paragraph and never the sections under it. A
   SHOUTED key (`PASSWORD:`) also binds a value under a blank
   line; a lowercase word ending a paragraph binds nothing. In a connection
   string — a run of 2 or more `k=v` pairs joined by `;` or a line break — every
   pair naming a user, host, database or credential loses its value. So does a
   `-W`/`--password`/`--user` shell flag anywhere, and a `-p` (glued or spaced)
   or `-u`/`-U` after a network or database command or a `login` — to `sort -u`
   the argument is a file and to `find -print` the flag is a flag, so the command
   decides.
   A secret name over a `|` or `>` block marker takes the whole indented block
   under it; a PARENT key takes nothing, so `credentials:` leaves the
   `password:` under it to its own rule. A dotted name starting with a letter,
   `_`, a leading `.` or a `*.` wildcard label is a host (`<host>`), or a
   qualified symbol when it holds a capital (`<symbol>`) — no TLD list, and a
   known file extension does not exempt it. An `@name` carrying a dotted tail is
   that host, taken whole. Every rule rewrites
   only text outside the `<placeholder>`s earlier rules wrote.
   Identity is an ALLOWLIST: a path-shaped token survives only when it is a
   generic run-artifact path, or resolves under the plugin root — absolute or
   `${AFK_PLUGIN_ROOT}`-prefixed, or relative with 2+ segments whose parent
   directory exists in the plugin and which the consuming repository does NOT
   also hold (when both hold it, the spellings are one and identity wins);
   a dotted name only when it is a public host, a prose abbreviation (`e.g.`),
   a version (`v1.0.15`), a two-label lowercase call (`line.strip()` — a stack
   frame has more labels and a capital, so it still goes), or the PLUGIN's own
   tracked text spells it verbatim (`verification.tiers`, `pom.xml`, `SDD.md` —
   public by definition, and the detail an issue must cite to be actionable)
   and no machine context contradicts it — a network command, a
   `host`/`server`/`peer`/`node` word, `handshake with`, `connect(ed) to`,
   `resolved`, or a following `is the host`. That context list is FINITE and
   names commands and phrasings, so a wording outside it keeps the file name: a
   declared limit, narrow because the same token is usually a plugin file;
   a source-file name only when the plugin ships it; a PascalCase word only
   when the plugin's own text uses it or it is a standard-library error name.
   Everything else is a placeholder. The ticket, account, address, and
   source-file shapes are the ones `hooks/lib/sensitive-patterns.tsv` owns for
   the genericity gate.
2. Scan the result for RESIDUAL shapes, per piece of a line BETWEEN the
   placeholders pass 1 wrote: a placeholder ALREADY in the input that `redact()`
   probed and found hiding a value, a secret word bound to a MASK the input
   brought — a run of one repeated character or a fenced token, in any fence —
   with a value behind it that cannot be decided, any first-pass shape that
   survived, high-entropy blobs, secret keywords bound to a value the plugin's
   own text does not use (`password is required` is prose), a quoted literal
   beside a credential-ish column or key name, and any word
   from the consuming repository's own vocabulary (tracked file stems and directory
   names, capped; matched case-folded, singular or plural, whole or by its
   camel/kebab/snake parts). A word the plugin's own text also uses is exempt,
   except the remote's owner and repository name, which are identity first.

THE GAP, in one place. One class of value no pattern here can decide: a
SINGLE-LABEL token that is at once ordinary plugin vocabulary and a private
identity — a one-word host (`build01`, `orders`), or a class or service name
that spells a word the plugin's own text uses. Nothing in the shape separates
it from prose, so pass 1 keeps it and pass 2's vocabulary exemption clears it.
A SECOND declared class: a credential inside a quoted literal with no key
naming it (`VALUES ('jsmith', 'Hunter2!dragon')`). Nothing in the shape of a
quoted string says it is a secret, and redacting every long literal would blank
the evidence an issue is made of, so pass 1 keeps it and pass 2 reports the line
as `credential-literal` whenever a credential-ish word shares it — a warning
that queues the draft, never a silent pass. The probe and the mask scan read a
TWO-LINE window (a key and the value under it); a value further down is not
reached. Redacting these classes would blank ordinary sentences; guessing would
be worse than declaring them. The plugin's owner accepted this residual risk for a
public repository. Every gap found so far outside this class was closed by a
rule; a new one is a defect to fix here, never a guess to add.

`--check` skips pass 1 and only scans. Exit codes:
    0  clean
    1  residual hits — each printed to stderr as `redact: line N: <class>`,
       N counted in the redacted text, except `placeholder-in-input`, which
       is found before pass 1 and counts N in the input
    2  usage error
"""
from __future__ import annotations

import argparse
import builtins
import functools
import math
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_PLUGIN_ROOT = HERE.parents[3]

TOKEN_SHAPES = [
    r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"glpat-[A-Za-z0-9_-]{20,}",
    r"xox[abprs]-[A-Za-z0-9-]{10,}",
    r"(?:AKIA|ASIA|AIDA|AROA|AGPA|ANPA|ANVA|AIPA|APKA)[0-9A-Z]{16}",
    r"sk-[A-Za-z0-9_-]{20,}",
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}",
]
# A variable name, not a kebab phrase: `-` joins words in prose (`secret-block`,
# `credential-literal` are this file's own rule names), `_` joins them in a name.
SECRET_NAME = r"[A-Za-z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|PRIVATE[_-]?KEY|CREDENTIALS?)[A-Za-z0-9_]*"
# A quoted value runs to its REAL closing quote, across line breaks and past an
# escaped quote. It crosses a line break ONLY while a closing quote still lies
# ahead IN THE SAME PARAGRAPH: a blank line ends the value whatever follows, so
# one stray quote takes the rest of its own paragraph and never the sections
# under it. A quote closing three headings later is a different quote.
QUOTED_BODY = (r"((?:\\.|(?!\3)[^\n]"
               r"|(?=(?:\\.|(?!\3)[^\n]|\n(?![ \t]*\n))*?\3)\n(?![ \t]*\n))+)")
# The same name SHOUTED — a config key, never a word of prose. Only a key
# reaches across a blank line to the value under it.
SECRET_KEY_NAME = r"[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|PRIVATE_?KEY|CREDENTIALS?)[A-Z0-9_]*"
# Every word that binds a value: the named forms above plus the bare words prose
# uses. One home — the space-bound rule and the residual scan both read it.
SECRET_WORD = rf"{SECRET_NAME}|token|password|passwd|secret|api[-_ ]?key|authorization|cookie"
HEADER_NAME = r"(?:proxy-)?(?:authorization|x-api-key|cookie|set-cookie|private-token)"
PUBLIC_HOSTS = {
    "github.com", "api.github.com", "docs.github.com", "raw.githubusercontent.com",
    "anthropic.com", "docs.anthropic.com", "claude.ai", "claude.com",
    "example.com", "example.org", "example.net",
}
PUBLIC_SUFFIXES = (".example.com", ".example.org", ".example.net", ".test", ".invalid")
# Standard-library error names an issue needs to stay useful; a product's own
# exception class is not on it.
STD_ERRORS = {n for n in dir(builtins) if n.endswith(("Error", "Exception", "Warning"))} | {
    "JSONDecodeError", "CalledProcessError", "TimeoutExpired", "SubprocessError",
    "NullPointerException", "IllegalArgumentException", "IllegalStateException",
    "IOException", "FileNotFoundException", "NoSuchFileException",
    "ClassNotFoundException", "UnsupportedOperationException", "RuntimeException",
    "IndexOutOfBoundsException", "ArrayIndexOutOfBoundsException",
    "NumberFormatException", "ConcurrentModificationException", "InterruptedException",
    "TimeoutException", "OutOfMemoryError", "StackOverflowError", "SyntaxError",
    "ReferenceError", "RangeError", "URIError", "EvalError", "AggregateError",
}
VOCAB_FILE_CAP = 20000
KEPT_IPS = {"127.0.0.1", "0.0.0.0", "::1", "::"}
DOC_HOSTS = {"docs.github.com", "docs.anthropic.com"}
# Dotted prose, not machines — the host rule stops before the closing dot, so
# these are spelled without it. A call (`line.strip()`) is kept by its `(`.
PROSE_DOTTED = {"e.g", "i.e", "et.al", "a.k.a"}
# The host rule's own token shape, read over the plugin tree to learn which
# dotted names the plugin already publishes.
DOTTED_TOKEN = re.compile(
    r"(?<![\w.@/\\$<-])[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_][A-Za-z0-9_-]*)+(?![\w-])")
# Full and `::`-compressed forms. Every compressed form needs `::`, so a time
# (10:30:00) or a file:line reference never matches.
_H = r"[0-9a-f]{1,4}"
IPV6 = (rf"(?<![\w:.])(?:(?:{_H}:){{7}}{_H}|(?:{_H}:){{1,7}}:|(?:{_H}:){{1,6}}:{_H}"
        rf"|(?:{_H}:){{1,5}}(?::{_H}){{1,2}}|(?:{_H}:){{1,4}}(?::{_H}){{1,3}}"
        rf"|(?:{_H}:){{1,3}}(?::{_H}){{1,4}}|(?:{_H}:){{1,2}}(?::{_H}){{1,5}}"
        rf"|{_H}:(?::{_H}){{1,6}}|:(?::{_H}){{1,7}}|::)"
        # The zone id (`%eth0`, URL-encoded `%25eth0`) names a local interface,
        # so it goes with the address.
        r"(?:%(?:25)?[A-Za-z0-9._-]+)?(?![\w:])")
# A placeholder an earlier rule wrote (or the template prescribes): later rules
# never rewrite inside one.
PLACEHOLDER = re.compile(r"<[a-z][a-z-]*>")
PLACEHOLDER_SPLIT = re.compile(r"(<[a-z][a-z-]*>)")
# A token SHAPED like one of ours but not one of ours (`<REDACTED>`, `<XXX>`).
# Only the probe reads it: whatever spelling the input brought, a bracketed word
# splits a line the way a real placeholder does, so the line gets probed.
PLACEHOLDER_LIKE = re.compile(r"<[A-Za-z][\w .-]*>")
# A MASK the author already wrote over a value. Two whole shapes, not a list of
# spellings: a run of ONE repeated character (`*****`, `xxxxx`, `-----`, `.....`)
# and a FENCED token, whatever the fence and however many layers of it
# (`<REDACTED>`, `<<redacted>>`, `[hidden]`, `(omitted)`, `***hidden***`). A mask
# binds where the secret rules bind, so the real value is the token AFTER it —
# and what that token is cannot be decided here. `residual()` reports the line.
# A fence must CLOSE, or hold no word at all (`<!--`): an opener glued to a word
# is a value wearing a bracket, and pass 1 takes it whole. (No value is spelled
# anywhere in this file: a word written here joins the plugin's own vocabulary,
# which the prose exemption below would then clear.)
MASK = (r"(?P<mask>(?P<mask_char>\S)(?P=mask_char){2,}"
        r"|<+[^\s<>]*>+|\[+[^\s\[\]]*\]+|\(+[^\s()]*\)+|\{+[^\s{}]*\}+"
        r"|[*_#]+[^\s*_#]*[*_#]+|[<\[({][^\s\w]*)(?=\s|$)")
MASKED_VALUE = re.compile(
    rf"(?i)(?<![\w-])(?:{SECRET_WORD})[\"']?[ \t]*[=:]?[ \t]*{MASK}[ \t]*\n?[ \t]*(?P<after>\S+)")
# Pass 1 leaves a mask standing. Replacing it would erase the one sign pass 2
# reads, and the value behind it would ship as ordinary prose.
MASK_TOKEN = re.compile(rf"^{MASK}$")
# Pass 2's own scans. The keyword one captures the follower, so prose can be
# told from a value; the literal one is a WARNING shape, never a redaction.
SECRET_KEYWORD = re.compile(r"(?i)\b(?:password|passwd|secret|api[_-]?key|private[_ -]key)\b"
                            r"[\"']?[ \t]*(?:[:=]|\bis\b)[ \t]*[\"']?([^\s<\"'][^\s\"']*)")
CREDENTIAL_LITERAL = re.compile(r"(?i)(?<![\w-])(?:pw|pass|passwd|password|secret|token"
                                r"|api[_-]?key|credentials?)s?(?![\w-])")
QUOTED_LITERAL = re.compile(r"'([^'\n]*)'|\"([^\"\n]*)\"")
GENERIC_PATHS = re.compile(
    r"^(?:plan/[A-Z][A-Z-]*\.md|plan/review/INDEX\.md|\.afk/config(?:\.local)?\.yaml"
    r"|\.claude/afk-issues(?:/<[a-z-]+>\.md)?)$"
)
TEXT_SUFFIXES = {".md", ".sh", ".py", ".json", ".yaml", ".yml", ".toml", ".txt", ".tsv"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", "tests", ".pytest_cache"}
PATH_TOKEN = r"[^\s\"'`()\[\],;|]*[\\/][^\s\"'`()\[\],;|]*"
PLACEHOLDER_SEGMENT = re.compile(r"^(?:<[^>]*>|\{[^}]*\}|.*\*.*)$")
# The keys a connection string must not keep a value for, and the shape of one
# pair in it — any key, so that a run is recognised by its joins, not by which
# keys a vendor chose.
CONNECTION_KEY = (r"(?:user\s?id|userid|uid|user|username|password|pwd|server|data\s?source"
                  r"|host|hostname|database|initial\s?catalog|account)")
CONNECTION_PAIR = r"[A-Za-z][A-Za-z ]{0,24}\s*=\s*[^;\n]+"
CONNECTION_VALUE = re.compile(rf"(?i)(?<![\w-])({CONNECTION_KEY}\s*=\s*)(?!<)[^;\n]+")
# What marks a name as a MACHINE, not a file. An issue body is about plugin
# files, so a plugin basename is kept by default; only this context turns one
# into a host. The list is FINITE: a phrasing outside it keeps the name (see
# the module docstring's declared limit).
NET_COMMANDS = (r"telnet|curl|wget|nc|netcat|ssh|scp|sftp|rsync|dig|nslookup|traceroute"
                r"|tracert|mount|psql|mysql|redis-cli|mongo|ftp|ping|host|nmap|openssl")
HOST_CONTEXT = re.compile(
    r"(?i)(?:\b(?:host|hostname|server|peer|node|upstream)\b"
    rf"|\b(?:{NET_COMMANDS})\b(?:[ \t]+-{{1,2}}[\w-]+(?:[= ]\S+)?)*"
    r"|\b(?:handshake[ \t]+with|connect(?:ed|ion)?[ \t]+to|resolved?(?:[ \t]+to)?)\b)"
    r"[ \t:=]+$")
# And after it: `<name> is the host`.
HOST_CONTEXT_AFTER = re.compile(
    r"(?i)^[ \t]*(?:is|was|remains)[ \t]+(?:the[ \t]+|a[ \t]+|our[ \t]+)?"
    r"(?:host|hostname|server|peer|node|upstream)\b")


def _host_context(m: re.Match, written: str = "") -> bool:
    """Context is what shares the token's LINE. A sentence ending in `server`
    says nothing about the first word of the next line. `written` is the text in
    front of the piece, so a machine word before a wall still reaches a host
    after it (`curl -u <redacted> pom.xml`)."""
    before = (written + m.string[:m.start()]).rsplit("\n", 1)[-1]
    after = m.string[m.end():].split("\n", 1)[0]
    return bool(HOST_CONTEXT.search(before) or HOST_CONTEXT_AFTER.match(after))


def load_patterns(plugin_root: Path) -> dict[str, str]:
    path = plugin_root / "hooks" / "lib" / "sensitive-patterns.tsv"
    patterns: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, _, regex = line.partition("\t")
        patterns[name.strip()] = regex.strip()
    for need in ("ticket-id", "notation-prefixes", "account-id", "email", "source-file"):
        if need not in patterns:
            raise SystemExit(f"redact: {path} has no `{need}` pattern")
        try:
            re.compile(patterns[need])
        except re.error as problem:
            raise SystemExit(f"redact: {path} `{need}` does not compile: {problem}")
    return patterns


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _path_forms(path: str) -> list[str]:
    """Every spelling a path can take in tool output on this machine."""
    if not path:
        return []
    p = path.rstrip("/\\")
    forms = {p, p.replace("\\", "/"), p.replace("/", "\\")}
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", p)
    if m:
        rest = m.group(2).replace("\\", "/")
        forms.add(f"/{m.group(1).lower()}/{rest}")
        forms.add(f"/mnt/{m.group(1).lower()}/{rest}")
    return sorted((f for f in forms if len(f) > 3), key=len, reverse=True)


def _remote_parts(url: str) -> tuple[str | None, list[str]]:
    """The host and every path segment of a git remote URL."""
    text = url.strip()
    m = re.match(r"^(?:[a-z+]+://)?(?:[^@/\s]+@)?([^/:\s]+)[:/](.+?)(?:\.git)?/?$", text)
    if not m:
        return None, []
    return m.group(1), [s for s in m.group(2).split("/") if s]


@functools.lru_cache(maxsize=4)
def _plugin_inventory(plugin_root: Path) -> tuple[set[str], set[str], set[str], set[str], set[str]]:
    """Basenames the plugin ships, the PascalCase and lowercase words its own
    text uses, and every DOTTED token that text spells verbatim — the allowlists
    identity redaction keeps. The plugin tree is public, so a token it already
    publishes leaks nothing; `verification.tiers` and `pom.xml` are the kind of
    detail an issue must be able to name. This file and the test tree are read
    for words but NOT for dotted tokens: both spell host shapes on purpose, and
    an allowlist built from them would exempt the very shapes they exist to
    catch."""
    basenames: set[str] = set()
    pascal: set[str] = set()
    words: set[str] = set()
    dotted: set[str] = set()
    # TRACKED text only. A cache or a build artifact under the plugin root is
    # not something the plugin publishes, and git is the one authority on which
    # is which. No git, no allowance — the redacting answer is the safe one.
    tracked = set(_git(plugin_root, "ls-files").splitlines())
    mine = Path(__file__).resolve()
    for dirpath, dirnames, filenames in os.walk(plugin_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            basenames.add(name)
            if Path(name).suffix not in TEXT_SUFFIXES:
                continue
            try:
                text = (Path(dirpath) / name).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            pascal.update(re.findall(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+\b", text))
            words.update(w.lower() for w in re.findall(r"\b[A-Za-z][A-Za-z0-9-]*\b", text))
            here = Path(dirpath) / name
            relative = here.relative_to(plugin_root).as_posix()
            if relative in tracked and here != mine and "tests" not in here.parts:
                dotted.update(t.lower() for t in DOTTED_TOKEN.findall(text))
    return basenames, pascal, words, dotted, _config_sections(plugin_root, tracked)


def _config_sections(plugin_root: Path, tracked: set[str]) -> set[str]:
    """The top-level names the consuming repository's config may carry.

    A config key is a fact an issue must be able to name, and prose frequency is
    the wrong authority for it: a reader accepts keys its own documents never
    spell (`tracker.kind`). So the names come from the CONFIG READER's own
    top-level set and from the config contract's table, never from how often the
    prose says them."""
    sections: set[str] = set()
    for relative, pattern in (("scripts/afk-config.py", r"TOP_LEVEL\s*=\s*\{([^}]*)\}"),
                              ("CONFIG.md", r"(?m)^\|\s*(`[^|]+`)\s*\|")):
        if relative not in tracked:
            continue
        try:
            text = (plugin_root / relative).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for block in re.findall(pattern, text):
            sections.update(name.lower() for name in re.findall(r"[a-z][a-z0-9-]*", block))
    return sections


def _forms(word: str) -> set[str]:
    """Case-folded word and its singulars (trailing `es`, `s`), 4+ letters."""
    w = word.lower()
    forms = {w}
    if w.endswith("es") and len(w) > 5:
        forms.add(w[:-2])
    if w.endswith("s") and len(w) > 4:
        forms.add(w[:-1])
    return {f for f in forms if len(f) >= 4}


def _name_forms(name: str) -> set[str]:
    """Forms of a name and of each camel, kebab, or snake part of it."""
    forms = _forms(name)
    for part in re.split(r"[-_.]+|(?<=[a-z0-9])(?=[A-Z])", name):
        if len(part) >= 4:
            forms |= _forms(part)
    return forms


def _repo_vocabulary(repo_root: Path) -> set[str]:
    """The consuming repository's own names: tracked file stems and directory
    names with their parts and singulars, capped at VOCAB_FILE_CAP files. A body
    word whose forms meet this set is a residual."""
    vocab: set[str] = set()
    for number, name in enumerate(_git(repo_root, "ls-files").splitlines()):
        if number >= VOCAB_FILE_CAP:
            break
        parts = name.split("/")
        for piece in parts[:-1] + [parts[-1].split(".")[0]]:
            vocab |= _name_forms(piece)
    return vocab


class Redactor:
    def __init__(self, plugin_root: Path, repo_root: Path | None, keep_repo: str | None):
        self.pat = load_patterns(plugin_root)
        self.plugin_root = plugin_root.resolve()
        self.keep_repo = (keep_repo or "").strip("/").lower()
        self.keep_parts = set(self.keep_repo.split("/")) if self.keep_repo else set()
        (self.basenames, self.pascal, self.words, self.dotted,
         self.config_sections) = _plugin_inventory(self.plugin_root)
        self.vocabulary: set[str] = set()
        self.identity_words: set[str] = set()
        # Kept whole: a relative path the consuming repository also holds is
        # identity, not plugin detail (`_plugin_path`).
        self.repo_root = repo_root.resolve() if repo_root is not None else None
        self.input_placeholders: list[int] = []
        self.rules: list[tuple[str, re.Pattern, object]] = []
        self._build(repo_root)

    def _add(self, cls: str, regex: str, repl, flags: int = 0) -> None:
        self.rules.append((cls, re.compile(regex, flags), repl))

    def _literal(self, cls: str, values, repl: str, scope: str = "") -> None:
        """`scope="path"` narrows a literal to the places that NAME a repository
        — a path segment, an `owner/name`, a URL authority, a remote line. A
        consuming repository is often called an ordinary word (`orders`, `core`,
        `consumer`), and replacing every occurrence of that word leaves the
        plugin's own evidence a grammatical sentence with no meaning. The word
        is identity where it addresses the repository, and prose everywhere
        else."""
        values = sorted({v for v in values if v and len(v) >= 3}, key=len, reverse=True)
        if not values:
            return
        alt = "|".join(re.escape(v) for v in values)
        if scope == "path":
            self._add(cls, rf"(?:(?<=[\/@:])(?:{alt})(?![A-Za-z0-9_])"
                           rf"|(?<![A-Za-z0-9_])(?:{alt})(?=[\/]))", repl, re.I)
            return
        self._add(cls, rf"(?<![A-Za-z0-9_])(?:{alt})(?![A-Za-z0-9_])", repl, re.I)

    def _build(self, repo_root: Path | None) -> None:
        a = self._add
        a("private-key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", "<private-key>")
        # A URL goes whole, credentials and host included, before any rule can
        # split it into parts.
        a("url", r"(?i)\b[a-z][a-z0-9+.-]*://[^\s)>\]\"'`<]+", self._url)
        # `user:secret@host/path` with no scheme is still one credential, so it
        # goes whole rather than leaving the host behind.
        # The `user:secret@` prefix decides it, so the host may be any shape:
        # dotted, single-label, IPv4, or a bracketed IPv6 address.
        # The password may hold colons and percent-encoding; the host may be a
        # bracketed IPv6 address with a zone id.
        a("credential-authority",
          r"(?<![\w.@/:-])[A-Za-z0-9._%+-]{1,64}:[^\s/\"'`,;]{1,128}@"
          r"(?:\[[0-9A-Za-z:.%_-]+\]|[A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_])?)"
          r"(?::\d{1,5})?(?:/[^\s\"'`<>,;]*)?",
          "<url>")
        a("auth-header", rf"(?i)\b({HEADER_NAME}[\"']?\s*[:=][ \t]*)(?!<redacted>)\S[^\n]*", r"\1<redacted>")
        a("bearer", r"(?i)\b(bearer|basic)(\s+|\s*[:=]\s*)(?!<redacted>)[\"']?[A-Za-z0-9._~+/=-]{12,}[\"']?", r"\1\2<redacted>")
        a("token", "|".join(TOKEN_SHAPES), "<token>")
        # Before the secret rules, so the whole string is still one piece: a
        # run of 2 or more `k=v` pairs joined by `;` or a line break is a
        # connection string, and every pair in it naming an identity or a
        # credential loses its value. A lone `user=` in a script line is not a
        # run, and keeps its value.
        a("connection-string",
          rf"(?i)(?<![\w-]){CONNECTION_PAIR}(?:[ \t]*[;\n][ \t]*{CONNECTION_PAIR}){{1,}}",
          self._connection_string)
        # Same quoted-value handling as the space-bound rule below: to the real
        # closing quote, across line breaks and past an escaped quote.
        # Before the `=`/`:` rule, which would bind only the `|` or `>` marker
        # and leave the block under it in the clear. The whole indented block is
        # the value, however many lines it runs. The marker itself does NOT
        # survive: the `=`/`:` rule then takes it as the key's inline value, so
        # the output reads `password: <redacted>` over one `<redacted>` line.
        a("secret-block",
          rf"(?i)(?<![\w-])({SECRET_WORD})([ \t]*:[ \t]*[|>][-+0-9]*[ \t]*\n)"
          r"((?:[ \t]+[^\n]*\n?)+)",
          lambda m: f"{m.group(1)}{m.group(2)}  <redacted>\n", re.M)
        # A CONFIG KEY reaches across blank lines; a prose word does not. The
        # name decides: `PASSWORD:` over an empty line still binds the value
        # under it, while `the quoted secret:` ending a paragraph binds nothing.
        # Case-sensitive on purpose — a key is shouted, prose is not.
        a("secret-assignment",
          rf"(?<![\w-])({SECRET_KEY_NAME})([\"']?[ \t]*[=:][ \t]*\n(?:[ \t]*\n)+[ \t]*)"
          r"(?![{\[])(?!<redacted>)"
          r"(?![\"']?[\w-]+[\"']?[ \t]*[:=]\s)"
          r"(?:([\"'])((?:\\.|(?!\3)[^\n])+)(\3)?|([^\s\"'][^\s;]*))",
          self._secret_assignment)
        a("secret-assignment",
          # The separator crosses at most ONE line break: a key on its own line
          # still binds the value under it (`DB_PASSWORD:` then the value), but
          # a key at the end of a paragraph does not reach the next paragraph.
          # A parent key binds no value: `credentials:` over `password: X` must
          # leave the child alone. Only the NEXT-LINE branch refuses a key —
          # on its own line a value may carry any `:` or `=` it likes — and the
          # refusal lives in the PATTERN, since a refusing handler would still
          # consume the child key with its match.
          rf"(?i)(?<![\w-])({SECRET_NAME})([\"']?[ \t]*[=:]"
          r"(?:[ \t]*|[ \t]*\n[ \t]*(?![\"']?[\w-]+[\"']?[ \t]*[:=]\s)))"
          r"(?![{\[])(?!<redacted>)"
          # The bare branch refuses a quote: the quoted branch owns those, and a
          # lone quote is what a placeholder leaves behind when a piece ends.
          rf"(?:([\"']){QUOTED_BODY}(\3)?|([^\s\"'][^\s;]*))",
          self._secret_assignment, re.S)
        # The same secret names the `=`/`:` rule takes, prefixed and suffixed
        # forms included (GITLAB_TOKEN, MY_SECRET), plus the bare words prose
        # uses. `_` is a word character, so the left guard is a class, not `\b`.
        # A quoted value goes whole to its real closing quote — across line
        # breaks, past an escaped quote, and to the end of the input when the
        # quote never closes. An unquoted one is the next word, across a markdown
        # cell wall (`| password | value |`) and never punctuation alone. Any
        # length: `cookie 'x'` is a value.
        a("secret-spaced",
          rf"(?i)(?<![\w-])({SECRET_WORD})"
          rf"([ \t]*\|[ \t]*|[ \t]+)(?:([\"']){QUOTED_BODY}(\3)?"
          r"|(?=[^\s\"',;|]*\w)([^\s\"',;=:|][^\s\"',;|]*))",
          self._secret_spaced, re.S)
        # Every command-sensitive flag reads the words BEFORE it on its line, so
        # all of them run FIRST: a placeholder another flag rule writes would
        # wall the command off from the flags after it
        # (`mysql --user root -pSECRET`, `mysql -u root -pSECRET`).
        # A GLUED `-p` is a password to `mysql` and a `login`; to `find`,
        # `tar` and `mvn` it is the head of an ordinary long flag (`-print`,
        # `-pxvf`, `-pl`). The command on the line decides, as it does for `-u`.
        a("credential-flag", r"(?<![\w-])(-p)(?!<)[^\s;]+", self._password_flag)
        # A spaced `-p` is a port to `docker run` and a password to any `login`.
        # The word on the line decides, the same way the command decides `-u`.
        a("credential-flag", r"(?<![\w-])(-p(?:=|[ \t]+))(?!<|-)([^\s;]+)",
          lambda m: (f"{m.group(1)}<redacted>"
                     if _login_line(m, self._before) else m.group(0)))
        # `--password=secret`, `-W secret`: a long credential flag names itself,
        # whatever the command. The value is never the next FLAG.
        a("credential-flag",
          r"(?<![\w-])(--(?:user|username|password|pwd)(?:=|[ \t]+)|-W[ \t]+)(?!<|-)([^\s;]+)",
          r"\1<redacted>")
        # `-u` and `-U` mean a user only to a network or database command; to
        # `sort`, `diff` and `grep` they mean something else and the argument is
        # an ordinary file. The command decides.
        a("credential-flag",
          r"(?<![\w-])(-[uU](?:=|[ \t]+))(?!<|-)([^\s;]+)", self._credential_flag)

        # Roots first: the plugin root is shown as the variable skills use, the
        # consuming repository as a placeholder, a home directory as `~`.
        # An INSTALLED plugin sits under the reporter's home directory, so the
        # whole traceback frame would go as one home path and the report would
        # lose the file that crashed. The home part goes; everything from the
        # marketplace directory down is plugin-side and stays, version included.
        # The rewrite must stay TRUE: the run used a cache copy under a home
        # directory, and `${AFK_PLUGIN_ROOT}` would assert it ran from the plugin
        # root. So only the home part goes, and the install path reads as what it
        # is — a maintainer can see the run came from an installed copy.
        a("plugin-path",
          r"(?i)(?:[A-Za-z]:)?[\\/]?(?:[^\s\"'`]*[\\/])?"
          r"(\.(?:claude|codex)[\\/]plugins[\\/](?:cache|marketplaces)[\\/]afk-toolkit[\\/])",
          r"~/\1")
        for form in _path_forms(str(self.plugin_root)):
            a("plugin-path", re.escape(form), "${AFK_PLUGIN_ROOT}", re.I)
        # A shell default expansion is a SHAPE the reader needs: which variable,
        # and that it has a fallback. Only the fallback can carry a private path,
        # so the path rule judges that alone and the expansion keeps its walls.
        a("plugin-path", r"(\$\{[A-Za-z_][A-Za-z0-9_]*:[-=?+])([^}\n]*)(\})",
          lambda m: f"{m.group(1)}{self._inner_path(m.group(2))}{m.group(3)}")
        identity: set[str] = set()
        handles: set[str] = set()
        self.product_classes: set[str] = set()
        if repo_root is not None:
            repo_root = repo_root.resolve()
            if repo_root != self.plugin_root:
                for form in _path_forms(str(repo_root)):
                    a("repo-path", re.escape(form), "<repo>", re.I)
                identity.add(repo_root.name)
                # The remote's owner and name, apart from the directory: those
                # are identity first whatever word they spell, and keep their
                # residual in prose. The directory basename does not (below).
                remote_names: set[str] = set()
                for line in _git(repo_root, "remote", "-v").splitlines():
                    parts = line.split()
                    if len(parts) < 2:
                        continue
                    host, segments = _remote_parts(parts[1])
                    if "/".join(segments).lower() == self.keep_repo:
                        continue
                    identity.add(parts[1])
                    if host and host.lower() not in PUBLIC_HOSTS:
                        identity.add(host)
                    identity.update(s for s in segments if s.lower() not in self.keep_parts)
                    remote_names.update(s.lower() for s in segments)
                    if len(segments) >= 2:
                        identity.add("/".join(segments[-2:]))
                for name in _git(repo_root, "ls-files").splitlines():
                    base = name.rsplit("/", 1)[-1]
                    if re.fullmatch(self.pat["source-file"], base):
                        self.product_classes.add(base.rsplit(".", 1)[0])
                self.identity_words = {i.lower() for i in identity if "/" not in i and ":" not in i}
                # The DIRECTORY BASENAME, when it is also a plugin word and no
                # remote spells it, is the declared single-label class: in prose
                # it is the plugin's own evidence (`... has no consumer`), so it
                # raises no residual. Where it addresses the repository the
                # path-scoped literal above still redacts it.
                basename = repo_root.name.lower()
                if basename in self.words and basename not in remote_names:
                    self.identity_words.discard(basename)
                self.vocabulary = _repo_vocabulary(repo_root) | self.identity_words
            for key in ("user.name", "user.email"):
                value = _git(repo_root, "config", key).strip()
                if key == "user.email":
                    value = value.split("@")[0]
                handles.update(t for t in re.split(r"[^A-Za-z0-9]+", value) if len(t) >= 3)
        home = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
        for form in _path_forms(home):
            a("home-path", re.escape(form), "~", re.I)
        a("home-path", r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s]+", "~")
        a("home-path", r"(?<![\w.~])/(?:home|Users)/[^/\s]+", "~")
        # A name the plugin's own text also uses is identity only where it
        # addresses the repository; anywhere else it is a word of the evidence.
        self._literal("repo-identity", {v for v in identity if v.lower() not in self.words},
                      "<repo>")
        self._literal("repo-identity", {v for v in identity if v.lower() in self.words},
                      "<repo>", scope="path")

        a("email", self.pat["email"], "<email>")
        a("account-id", self.pat["account-id"], "<account-id>")
        # The domain tail goes with the head: splitting it leaves
        # `<handle>.acme.local` behind, because the host rule cannot start
        # after an `@`. A dot in the token makes it a machine, not a person.
        a("handle", r"(?<![\w.@/<])@[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:\.[A-Za-z0-9_][A-Za-z0-9_-]*)*\b",
          self._handle)
        a("ip", r"\b(?:\d{1,3}\.){3}\d{1,3}\b", lambda m: m.group(0) if m.group(0) in KEPT_IPS else "<ip>")
        a("ipv6", IPV6, lambda m: m.group(0) if m.group(0) in KEPT_IPS else "<ip>", re.I)
        # Before the host rule, which would otherwise claim every bare
        # source-file name. A separator in the lookbehind keeps a path's own
        # basename out: the path rule judges the path whole.
        a("product-file", rf"(?<![A-Za-z0-9_.<\\/-]){self.pat['source-file']}(?![A-Za-z0-9_])", self._product_file)
        # A letter starts the first label, so a version number (1.0.15) is not a
        # host; the last label is any length and may be numeric, so db.x and
        # db.123 are.
        # A leading `.` or `*.` belongs to the name, not to the boundary before
        # it: a proxy list, a resolver line, a cookie domain and a certificate
        # error all spell a private domain that way.
        a("host", r"(?<![\w.@/\\$<-])(?:\*\.|\.)?[A-Za-z_](?:[A-Za-z0-9_-]*[A-Za-z0-9_])?(?:\.[A-Za-z0-9_](?:[A-Za-z0-9_-]*[A-Za-z0-9_])?)*\.[A-Za-z0-9]+(?![\w-]|\.\w)", self._host)
        a("ticket-id", rf"(?<![A-Za-z0-9_]){self.pat['ticket-id']}(?![A-Za-z0-9_])", self._ticket)
        a("product-symbol", r"`([A-Z][A-Za-z0-9]*)`", lambda m: "`<product-symbol>`" if m.group(1) in self.product_classes else m.group(0))
        a("path", PATH_TOKEN, self._path)
        a("pascal-case", r"(?<![\w$<])[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+(?![\w])", lambda m: m.group(0) if m.group(0) in self.pascal or m.group(0) in STD_ERRORS else "<symbol>")
        self._literal("user-handle", handles, "<user>")

    def _url(self, m: re.Match) -> str:
        """Kept only for the target repository or a public docs host, and never
        with credentials; everything else is one `<url>`."""
        url = m.group(0)
        if self.keep_repo and re.match(rf"(?i)https://github\.com/{re.escape(self.keep_repo)}(?:[/#?]|$)", url):
            return url
        authority = re.match(r"(?i)^[a-z][a-z0-9+.-]*://([^/?#]*)", url)
        if authority and authority.group(1).lower() in DOC_HOSTS:
            return url
        return "<url>"

    def _secret_spaced(self, m: re.Match) -> str:
        """A secret keyword binds what follows a space: a quoted string whole,
        spaces and all, or the next word. Any length, closing quote optional.
        After a BARE prose keyword, an unquoted value the plugin's own text uses
        is prose (`password is required`), not a value; after a named variable
        (`GITLAB_TOKEN`) nothing is prose."""
        key, gap, quote, quoted, close, bare = m.groups()
        named = bool(re.fullmatch(SECRET_NAME, key, re.I)) and re.search(r"[_-]", key)
        if quote is None:
            # A word carries the sentence's punctuation; the vocabulary does not.
            word = bare.strip("-.,:;!?*`()[]{}\"'").lower()
            if MASK_TOKEN.match(bare) or (not named and word in self.words):
                return m.group(0)
            return f"{key}{gap}<redacted>"
        # Only OUR spelling is already a redaction; `"<REDACTED>"` is a value.
        if PLACEHOLDER.match(quoted):
            return m.group(0)
        # `close` is None where the quote never closed; write no quote either.
        return f"{key}{gap}{quote}<redacted>{close or ''}"

    def _password_flag(self, m: re.Match) -> str:
        """A glued `-p` carries a password only where a command can ask for one.
        Elsewhere it opens a long flag, and the whole flag is the plugin's own
        evidence: `find . -print` must survive an issue body intact."""
        if not _command_owns_flag((self._before + m.string[:m.start()]).rsplit("\n", 1)[-1]):
            return m.group(0)
        return f"{m.group(1)}<redacted>"

    def _credential_flag(self, m: re.Match) -> str:
        """`-u`/`-U` after a network or database command is a user name; after
        `sort -u` or `diff -u` it is not a credential at all. A value holding a
        colon is `name:secret` whatever the command."""
        if ":" in m.group(2):
            return f"{m.group(1)}<redacted>"
        # The command is the one in THIS shell segment: a `curl` further up the
        # report, or before `&&`, says nothing about a `sort` here. The segment
        # includes the text in front of a wall, so `curl <url> -u admin` still
        # has its `curl`; a URL pass 1 replaced says the same.
        line = re.split(r"\|\||&&|[|;&]",
                        (self._before + m.string[:m.start()]).rsplit("\n", 1)[-1])[-1]
        if not re.search(rf"(?i)(?<![\w-])(?:{NET_COMMANDS}|http"
                         r"|git[ \t]+(?:clone|fetch|pull|push|ls-remote))\b|<url>", line):
            return m.group(0)
        return f"{m.group(1)}<redacted>"

    def _secret_assignment(self, m: re.Match) -> str:
        """A parent key binds no value of its own: `credentials:` followed by
        `password: X` must leave the child alone, or the child's value ships in
        the clear. A container opener is the same case in JSON."""
        name, separator, quote, quoted, close, bare = m.groups()
        if MASK_TOKEN.match(bare or "") or PLACEHOLDER.match(quoted or ""):
            return m.group(0)
        return f"{name}{separator}{quote or ''}<redacted>{close or ''}"

    def _connection_string(self, m: re.Match) -> str:
        """Inside the run, every identity or credential pair loses its value;
        the keys and the shape stay, so the report still reads. One such pair in
        a run of 2 or more is enough — `user=` beside `timeout=` still names a
        person — but a lone assignment is not a connection string at all."""
        run = m.group(0)
        if not CONNECTION_VALUE.search(run):
            return run
        return CONNECTION_VALUE.sub(r"\1<redacted>", run)

    def _handle(self, m: re.Match) -> str:
        """An `@name` is a person, and `@a.b` a machine — except where code puts
        a DECORATOR or an ANNOTATION, and in an npm scope. Python and Java
        evidence quotes `@pytest.fixture`, `@dataclass` and `@Override`
        constantly; `ask @jane` in running prose still goes.

        Code puts one: inside a code fence; directly before `(`; or ALONE on
        its line after optional indentation. Alone, not merely first: `@jane
        can you look` opens a line too. A DOTTED token alone on its line must
        also be INDENTED: a bare domain typed on its own line at column 0 has
        exactly a decorator's shape, and no vocabulary test separates them
        (`corp` is a plugin word). An unfenced top-level `@pytest.fixture`
        therefore goes — evidence lost, never a secret shipped. Indented, a
        dotted token whose LAST label is a domain suffix is still a machine: a
        YAML list of mail domains indents exactly like a decorator."""
        token = m.group(0)
        text = m.string
        after = text[m.end():]
        before = text[:m.start()].rsplit("\n", 1)[-1]
        # `@scope/name`: an npm package, which the path rule then keeps — only
        # when the plugin's own text spells the scope. A scope is an
        # organisation, so any other one is private.
        if (re.match(r"/[a-z0-9][a-z0-9._-]*(?![\w/])", after) and token == token.lower()
                and token[1:] in self.words):
            return token
        alone = not before.strip() and not after.split("\n", 1)[0].strip()
        vetted = "." not in token or (before != "" and not _domain_suffix(token))
        if after.startswith("(") or _in_fence(text, m.start()) or (alone and vetted):
            return token
        return "<host>" if "." in token else "<handle>"

    def _host(self, m: re.Match) -> str:
        """Any dotted name is a host, or a qualified symbol when it holds a
        capital. A known file extension alone does not make it a file name —
        `database.prod.log` is a host; only a public host, or a file the plugin
        ships, is kept. A private host can spell a plugin basename, so
        machine context around it (`host redact.py accepted a connection`)
        overrides the name and redacts it."""
        token = m.group(0)
        low = token.lower()
        if low in PUBLIC_HOSTS or low.endswith(PUBLIC_SUFFIXES) or low in PROSE_DOTTED:
            return token
        # `v1.0.15`: a tag, not a machine — no host spells a version.
        if re.fullmatch(r"(?i)v\d[\d.]*", token):
            return token
        # `.pre-commit-config.yaml`: a DOTFILE — one stem after the dot, then a
        # config extension. `.corp.acme.local` has 2+ labels after the dot and
        # stays a host.
        if re.fullmatch(r"(?i)\.[A-Za-z0-9_-]+\.(?:yaml|yml|json|toml|cfg|ini|conf|lock|md|txt)",
                        token):
            return token
        # A dotted token the plugin's own tracked text spells verbatim
        # (`SDD.md`, `verification.tiers`, `pom.xml`): public by definition, and
        # the detail an issue has to cite to be actionable. Machine context on
        # the line still wins — `host api.call` is a machine.
        if low in self.dotted and not _host_context(m, self._before):
            return token
        # A CONFIG KEY: two lowercase labels whose first names a section the
        # config reader accepts (`tracker.kind`, `git.branch-pattern`). The
        # reader, not the prose, is the authority — it takes keys no document
        # spells. Two labels only: `git.corp.acme.local` is a machine.
        if (low.count(".") == 1 and low.split(".")[0] in self.config_sections
                and not re.search(r"[A-Z]", token) and not _host_context(m, self._before)):
            return token
        # `line.strip()`, `re.compile(p)`: a call on a lowercase receiver, not a
        # machine. Two labels and no capital — a stack frame has more of both.
        if (m.string[m.end():m.end() + 1] == "(" and token.count(".") == 1
                and not re.search(r"[A-Z]", token)):
            return token
        if token in self.basenames and not _host_context(m, self._before):
            return token
        return "<symbol>" if re.search(r"[A-Z]", token) else "<host>"

    def _ticket(self, m: re.Match) -> str:
        prefix = m.group(0).split("-")[0]
        return m.group(0) if re.fullmatch(self.pat["notation-prefixes"], prefix) else "<ticket>"

    def _product_file(self, m: re.Match) -> str:
        return m.group(0) if m.group(0) in self.basenames else "<product-file>"

    def _documented_env(self, token: str) -> str | bool:
        """An ALL-CAPS environment-variable name the plugin's own text documents
        is not a blob, whatever its length. Setting one is half of what an issue
        about the plugin says, so `AFK_SKIP_BRANCH_CHECK=1` must not queue a body
        that is otherwise wholly plugin-side. The VALUE still faces the scan."""
        name = re.match(r"^([A-Z][A-Z0-9_]{3,})(?:=(.*))?$", token)
        # `_` is what joins the words of a variable name, and the vocabulary is
        # harvested word by word, so the name is documented when every part is.
        if not name or not all(part.lower() in self.words
                               for part in name.group(1).split("_") if part):
            return False
        return not name.group(2) or not _high_entropy(name.group(2))

    def _inner_path(self, text: str) -> str:
        """The path decision, applied to text a wall already bounds."""
        return re.sub(PATH_TOKEN, self._path, text) if re.search(r"[\\/]", text) else text

    def _path(self, m: re.Match) -> str:
        token = m.group(0)
        if "://" in token or token.startswith("</") or not re.search(r"[A-Za-z0-9]", token):
            return token
        # `/afk:execute` is how a skill is INVOKED, not where a file lives: one
        # slash, a namespace, a name. Every issue about this plugin names one,
        # so a path rule that eats it destroys the report's subject.
        if re.fullmatch(r"/[a-z][a-z0-9-]*:[a-z][a-z0-9-]*", token):
            return token
        core = token.rstrip(".:,;!?")
        tail = token[len(core):]
        # A line number and a pytest `::node` id are coordinates, never
        # identities, and they are what makes a failure line worth reading. Both
        # survive the path going: the forge project path is the secret, the name
        # of the test that failed is the report.
        line = re.search(r"(?:(?:::[^\s:]+)+|(?::\d+){1,2})$", core)
        core = core[:line.start()] if line else core
        if self.keep_repo and core.lower().split("#")[0] == self.keep_repo:
            return token
        # `@anthropic-ai/claude-code`: an npm scoped package whose scope the
        # plugin's own text spells. Any other scope is an organisation name.
        scoped = re.fullmatch(r"@([a-z0-9][a-z0-9._-]*)/[a-z0-9][a-z0-9._-]*", core)
        if scoped and scoped.group(1) in self.words:
            return token
        segments = [s for s in re.split(r"[\\/]", core) if s]
        # `**/*.py`: a GLOB of pure wildcard segments and an extension is a
        # pattern, not a place — it names no directory to be private about.
        if (len(segments) >= 2 and all(re.fullmatch(r"\*{1,2}", s) for s in segments[:-1])
                and re.fullmatch(r"\*\.[A-Za-z0-9]+", segments[-1])):
            return token
        rooted = bool(re.match(r"^(?:[\\/]|\.{1,2}[\\/]|~|\$|[A-Za-z]:)", core))
        has_ext = bool(re.search(r"\.[A-Za-z0-9]{1,8}$", segments[-1])) if segments else False
        if not rooted and not has_ext and len(segments) == 2:
            if all(s.isdigit() for s in segments) or all(s.lower() in self.words or s.startswith("<") for s in segments):
                return token
        return token if self._plugin_path(core) else "<path>" + (line.group(0) if line else "") + tail

    def _plugin_path(self, core: str) -> bool:
        """Plugin-side: under the plugin root (existing or not), or a generic
        run-artifact path. A relative path counts when the directory holding it
        exists in the plugin, whatever the file itself — a crash names the file
        that is missing, and that name is the point of the report. It does NOT
        count when the consuming repository holds the same relative path: the
        two spellings are indistinguishable, so identity wins."""
        if re.match(r"^\$\{?AFK_PLUGIN_ROOT\}?(?:[\\/]|$)", core):
            return True
        # An INSTALLED copy: everything from the marketplace directory down is
        # the plugin's own tree, whatever home directory holds it.
        if re.search(r"(?i)\.(?:claude|codex)[\\/]plugins[\\/]"
                     r"(?:cache|marketplaces)[\\/]afk-toolkit[\\/]", core):
            return True
        rel = core.replace("\\", "/")
        # A leading `./` or `../` says where the reader stood, not where the
        # file is: `../plan/PLAN.md` and `./scripts/run.sh` are judged as the
        # path after it. A `..` INSIDE the path still refuses below.
        while rel.startswith(("./", "../")):
            rel = rel.split("/", 1)[1]
        rel = rel.lstrip("/") if rel != core.replace("\\", "/") else rel
        if GENERIC_PATHS.match(rel):
            return True
        if rel.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", rel) or ".." in rel.split("/"):
            return False
        if (self.repo_root is not None and self.repo_root != self.plugin_root
                and (self.repo_root / rel).exists()):
            return False
        segments = [s for s in rel.split("/") if s]
        here = self.plugin_root
        for segment in segments:
            # A placeholder SEGMENT is unknown text, so the path is judged by
            # the plugin directory ABOVE it (`adapters/build-gate/<kind>/x.sh`).
            # A path whose FIRST segment is a placeholder has no such directory:
            # its root is the unknown, so it is not plugin-side.
            if PLACEHOLDER_SEGMENT.match(segment):
                return here != self.plugin_root and here.is_dir()
            here = here / segment
        if here != self.plugin_root and here.exists():
            return True
        return len(segments) >= 2 and here.parent.is_dir()

    def redact(self, text: str) -> str:
        """Each rule rewrites only the text between placeholders, so no later
        rule can reach into a `<placeholder>` an earlier one wrote.

        A bracketed token ALREADY in the input splits a line the same way, so it
        can hide the value after it — whatever its spelling, ours or not. Every
        such line is PROBED, not assumed guilty: erase its bracketed tokens and
        redact the line again; when that changes the outcome, one of them was
        hiding a value, and `residual()` reports the line for a human. A queued
        body this tool already redacted probes clean, so a republish takes no
        waiver. (No value is spelled in this docstring: a word written here
        joins the plugin's own vocabulary and would exempt itself.)"""
        self.probe_placeholders(text)
        return self._apply(text)

    def probe_placeholders(self, text: str) -> None:
        lines = text.splitlines()
        self.input_placeholders = [
            number for number, line in enumerate(lines, 1)
            if _hideable_mask(line)
            # OUR OWN placeholder already replaced the value, so nothing hides
            # behind it and the line stands alone. A FOREIGN mask hides an
            # unknown, and a key's value can sit on the line under it, so that
            # one is probed across the two-line window.
            and self._placeholder_hides(line if PLACEHOLDER.search(line)
                                        and not _foreign_mask(line)
                                        else _window(lines, number))]

    # The text already written in front of the piece a rule is reading. A
    # placeholder pass 1 wrote is a WALL, so the piece after `curl <url>` holds
    # no `curl`; a rule asking which command owns a flag reads this as well.
    _before = ""

    def _apply(self, text: str) -> str:
        for _cls, rx, repl in self.rules:
            out: list[str] = []
            for piece, wall in _split_outside_paths(text):
                self._before = "".join(out)
                out.append(piece if wall else rx.sub(repl, piece))
            text = "".join(out)
        return text

    def _changes(self, repl, m: re.Match, before: str) -> bool:
        self._before = before
        return self._substitute(repl, m) != m.group(0)

    def _placeholder_hides(self, line: str) -> bool:
        """Redact the line as it stands, then again with its masks erased, and
        ask what the second run TOOK that the first one kept. Comparing the two
        texts would answer a different question — erasing a mask also closes a
        gap, and a rule reaching over that gap rewrites shell punctuation or a
        word of the plugin's own prose. Neither is a hidden value, so neither
        counts: only a token with a word character that the plugin's text does
        not use says a mask was covering something."""
        erase = _erase_masks
        kept = set(erase(self._apply(line)).split())
        taken = kept - set(erase(self._apply(erase(line))).split())
        return any(re.search(r"\w", token)
                   and token.strip("-.,:;!?*`()[]{}\"'|").lower() not in self.words
                   for token in taken)

    def residual(self, text: str) -> list[tuple[int, str]]:
        # Line numbers are the input's: a placeholder there is the reason.
        hits: list[tuple[int, str]] = [(n, "placeholder-in-input") for n in self.input_placeholders]
        lines = text.splitlines()
        # Pass 1 sees the whole text, so it keeps a decorator inside a code
        # fence; one line alone cannot see the fence, so the scan carries it.
        fenced = False
        for number, line in enumerate(lines, 1):
            in_fence = fenced
            if re.match(r"[ \t]*(?:```|~~~)", line):
                fenced = not fenced
            spans: list[tuple[str, str]] = []
            written = ""
            for p, wall in _split_outside_paths(line):
                if p and not wall:
                    spans.append((p, written))
                written += p
            pieces = [p for p, _ in spans]
            bare = " ".join(pieces)
            for cls, rx, repl in self.rules:
                if cls == "handle" and in_fence:
                    continue
                if any(self._changes(repl, m, before) for piece, before in spans for m in rx.finditer(piece)):
                    hits.append((number, cls))
            # A net under the `-u` rule: a `name:secret` still standing after a
            # user flag queues, whichever rule should have taken it.
            if USER_PAIR_LEFT.search(line):
                hits.append((number, "credential-flag"))
            for piece in re.findall(r"[A-Za-z0-9+_=-]{20,}", bare):
                if _high_entropy(piece) and not self._documented_env(piece):
                    hits.append((number, "high-entropy"))
            # Per piece, never on the joined text: joining fabricates an
            # adjacency the line does not have, and a value pass 1 already
            # replaced is gone from the pieces, not sitting after its keyword.
            # The opening quote may be all a piece has left of a value pass 1
            # already replaced, so the quote is skipped, never counted as one.
            if any(self._secret_keyword(piece) for piece in pieces):
                hits.append((number, "secret-keyword"))
            # A quoted literal beside a credential-ish column or key name. Too
            # weak a signal to redact on — an issue body quotes ordinary strings
            # — and too strong to pass in silence, so it queues for a human.
            if CREDENTIAL_LITERAL.search(line) and any(
                    len(v) >= 8 and re.search(r"[\W\d]", v)
                    for m in QUOTED_LITERAL.finditer(line)
                    for v in [m.group(1) if m.group(1) is not None else m.group(2)]
                    if not PLACEHOLDER.fullmatch(v)):
                hits.append((number, "credential-literal"))
            # A secret word bound to a mask the INPUT brought, with a token after
            # it: the value behind the mask is undecidable. A follower the
            # plugin's own text uses is prose (`password (required) for the …`).
            if self._masked(_window(lines, number)):
                hits.append((number, "secret-masked"))
            for word in re.findall(r"(?<![\w])[A-Za-z][A-Za-z0-9_-]{3,}", bare):
                # The remote's owner and repository name win over the
                # plugin-vocabulary exemption: they are identity first, whatever
                # ordinary word they spell.
                if _name_forms(word) & self.identity_words:
                    hits.append((number, "repo-vocabulary"))
                    break
                if word.lower() in self.words:
                    continue
                if _name_forms(word) & self.vocabulary - self.words:
                    hits.append((number, "repo-vocabulary"))
                    break
        return sorted(set(hits))

    def _secret_keyword(self, piece: str) -> bool:
        """A keyword bound to a VALUE, never to ordinary prose. `password is
        required` names no value; a word the plugin's own text does not use
        after `:`, `=` or `is` does."""
        m = SECRET_KEYWORD.search(piece)
        return bool(m) and m.group(1).strip("-.,:;!?*`()[]{}\"'|").lower() not in self.words

    def _masked(self, line: str) -> bool:
        """Scanned on the WHOLE line: a mask can wrap one of our own
        placeholders (`<<redacted>>`), which the piece split would cut in half.
        Our own placeholder standing alone is a redaction, not a mask, and the
        probe in `redact()` owns that case."""
        for m in MASKED_VALUE.finditer(line):
            if PLACEHOLDER.fullmatch(m.group("mask")):
                continue
            if m.group("after").strip("-.,:;!?*`()[]{}\"'|").lower() not in self.words:
                return True
        return False

    @staticmethod
    def _substitute(repl, m: re.Match) -> str:
        return repl(m) if callable(repl) else m.expand(repl)


def _login_line(m: re.Match, before: str = "") -> bool:
    """A `login` earlier on the SAME line makes the next flag a credential.
    `before` is the text in front of the piece, across any wall."""
    return bool(re.search(r"(?i)\blogin\b", (before + m.string[:m.start()]).rsplit("\n", 1)[-1]))


# A `name:secret` standing after a user flag in REDACTED text: the residual
# net under the `-u` rule.
USER_PAIR_LEFT = re.compile(r"(?<![\w-])(?:-[uU]|--user)(?:=|[ \t]+)(?!<)[^\s:;]+:[^\s;]+")


# Last labels that make a dotted `@a.b` a machine even where a decorator could
# stand. Any 2-letter label counts as a country code. No common Python or Java
# decorator ends in one of these.
DOMAIN_SUFFIXES = frozenset(
    "com net org io dev app local internal corp lan intra home cloud co".split())


def _domain_suffix(token: str) -> bool:
    last = token.rsplit(".", 1)[-1].lower()
    return last in DOMAIN_SUFFIXES or bool(re.fullmatch(r"[a-z]{2}", last))


def _in_fence(text: str, pos: int) -> bool:
    """Whether `pos` sits inside a ``` code fence: an odd count of fence lines
    above it. Read on the text a rule sees, so a fence split by an earlier
    placeholder can read as closed — the decorator then goes, never a secret."""
    return len(re.findall(r"(?m)^[ \t]*(?:```|~~~)", text[:pos])) % 2 == 1


def _command_owns_flag(before: str) -> bool:
    """Whether the command that OWNS this flag can ask for a password.

    `host`, `ping` and `mount` are ordinary English as well as commands, so
    looking anywhere on the line makes a sentence mentioning one destroy the
    flag of the command actually running (`ping the box, then find . -print`).
    The owner is the command starting the shell segment the flag sits in, and it
    still owns the flag only while everything between them reads as a command
    line: flags, their values, and one subcommand word (`docker login`). The
    first BARE word after that is prose, and prose ends the command."""
    segment = re.split(r"\|\||&&|[|;&]", before)[-1].split()
    if not segment:
        return False
    head = segment[0].lower()
    bare_allowed = 1
    for token in segment[1:]:
        if token.startswith("-"):
            bare_allowed = 1
            continue
        if bare_allowed:
            bare_allowed -= 1
            if token.lower() == "login":
                return True
            continue
        return False
    return bool(re.fullmatch(rf"(?i)(?:{NET_COMMANDS})", head))


def _split_outside_paths(text: str) -> list[tuple[str, bool]]:
    """Split a piece of text on the placeholders a rule must not rewrite inside.

    A placeholder that sits INSIDE a path (`skills/afk/<name>/SKILL.md`) is a
    path SEGMENT, not a wall: splitting there would hand the path rule a bare
    `/SKILL.md` and cost the plugin its own documented path convention. Such a
    placeholder stays glued to its neighbours, and the path rule's own
    placeholder-segment test decides what the path is."""
    raw = PLACEHOLDER_SPLIT.split(text)
    pieces: list[tuple[str, bool]] = []
    # Whether the LAST piece is a wall. A glued piece can spell a placeholder
    # exactly (`<repo>` alone in front of its path), and re-reading the text to
    # decide would then wall off what was just glued.
    walled = False
    for index, piece in enumerate(raw):
        before = raw[index - 1] if index else ""
        after = raw[index + 1] if index + 1 < len(raw) else ""
        wall = bool(PLACEHOLDER.fullmatch(piece)) and not (
            before.endswith(("/", "\\")) or after.startswith(("/", "\\")))
        if pieces and not walled and not wall:
            pieces[-1] = (pieces[-1][0] + piece, False)
        else:
            pieces.append((piece, wall))
            walled = wall
    return pieces


def _in_path(m) -> bool:
    """A bracketed token touching a path separator is a path SEGMENT."""
    before = m.string[m.start() - 1] if m.start() else ""
    after = m.string[m.end()] if m.end() < len(m.string) else ""
    return before in "/\\" or after in "/\\"


def _erase_masks(text: str) -> str:
    """Blank every bracketed token that could be covering a value. One inside a
    path covers nothing, so it stays and the path keeps its shape."""
    return PLACEHOLDER_LIKE.sub(lambda m: m.group(0) if _in_path(m) else " ", text)


def _hideable_mask(line: str) -> bool:
    """Whether the line carries a bracketed token worth probing at all."""
    return any(not _in_path(m) for m in PLACEHOLDER_LIKE.finditer(line))


def _foreign_mask(line: str) -> bool:
    """A bracketed token the input brought that is not one of our spellings."""
    return any(not PLACEHOLDER.fullmatch(m.group(0)) for m in PLACEHOLDER_LIKE.finditer(line))


def _window(lines: list[str], number: int) -> str:
    """A mask's line plus the line under it — a key and the value below it are
    one shape. The window is TWO lines, declared: a value further down than that
    is not reached."""
    return "\n".join(lines[number - 1:number + 1])


def _high_entropy(token: str) -> bool:
    """A key-shaped blob: letters and digits, not a hex id, not kebab words."""
    if re.fullmatch(r"[0-9a-fA-F]+", token) or re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)+", token):
        return False
    if not (re.search(r"[0-9]", token) and re.search(r"[A-Za-z]", token)):
        return False
    mixed = re.search(r"[a-z]", token) and re.search(r"[A-Z]", token)
    if not (mixed or not re.search(r"[a-z]", token)):
        return False
    counts = {c: token.count(c) for c in set(token)}
    entropy = -sum(n / len(token) * math.log2(n / len(token)) for n in counts.values())
    return entropy > 3.5


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="redact.py", add_help=True)
    parser.add_argument("input", nargs="?")
    parser.add_argument("-o", "--output")
    parser.add_argument("--plugin-root", default=str(DEFAULT_PLUGIN_ROOT))
    parser.add_argument("--repo-root")
    parser.add_argument("--keep-repo")
    parser.add_argument("--check", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    try:
        text = (Path(args.input).read_text(encoding="utf-8") if args.input
                else sys.stdin.buffer.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError) as problem:
        sys.stderr.write(f"redact: cannot read input: {problem}\n")
        return 2
    try:
        redactor = Redactor(Path(args.plugin_root), Path(args.repo_root) if args.repo_root else None, args.keep_repo)
    except SystemExit as problem:
        sys.stderr.write(f"{problem}\n")
        return 2
    if args.check:
        redactor.probe_placeholders(text)
    else:
        text = redactor.redact(text)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8", newline="\n")
        else:
            sys.stdout.buffer.write(text.encode("utf-8"))
    hits = redactor.residual(text)
    for number, cls in hits:
        # The probe runs before pass 1, so its line numbers are the input's; a
        # multiline quoted value collapses lines and moves every other class.
        where = "input line" if cls == "placeholder-in-input" else "line"
        sys.stderr.write(f"redact: {where} {number}: {cls}\n")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

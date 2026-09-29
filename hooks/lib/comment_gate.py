#!/usr/bin/env python3
"""Commit-time comment gate: tracker references and the 2-line cap.

    python comment_gate.py --plugin-root DIR [--tracker KIND] [--project-keys A,B] [--json]

Reads `git diff --cached -U0` in the current repository and the staged blob of
each changed file. It blocks (exit 2) an added comment that holds a tracker
reference, and a run of more than 2 consecutive added comment lines. `RATIONALE.md`
owns the policy. Exit 0 otherwise; files with no known comment syntax are listed
on stderr as unchecked and never block.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

MAX_RUN = 2


class Finding(NamedTuple):
    path: str
    line: int
    kind: str
    message: str


class Spec(NamedTuple):
    """Lexical rules of one language family.

    `triple` is `escape` or `raw` for triple-quoted strings spanning lines. `verbatim` is
    C# `@"..."` (a doubled quote escapes). `quote_run` is a C# raw string: n quotes open,
    the next run of n or more closes. `here_string` is PowerShell `@"` ... `"@`, closed
    at a line start. `holes` names the interpolation dialect whose holes hold code:
    `kotlin` (`${...}` in raw strings), `scala` (the same, only after an interpolator
    prefix), `csharp` (`{...}` as deep as the `$` count of a raw string), `powershell`
    (`$(...)` in an expandable here-string).
    """

    lines: tuple = ()
    blocks: tuple = ()           # (open, close, doc-open prefixes)
    quotes: tuple = ('"', "'")
    backtick: bool = False
    triple: str = ""
    verbatim: bool = False
    quote_run: bool = False
    here_string: bool = False
    holes: str = ""
    rust: bool = False
    ws_before: bool = False      # a line marker needs whitespace or line start before it
    doc_lines: tuple = ()


C_BLOCK = (("/*", "*/", ("/**", "/*!")),)
C_LIKE = Spec(lines=("//",), blocks=C_BLOCK, doc_lines=("///", "//!"))
C_TICK = C_LIKE._replace(backtick=True)
HASH = Spec(lines=("#",), ws_before=True)
FAMILIES = {
    "cstyle": C_LIKE,
    "cstyle-triple": C_LIKE._replace(triple="escape"),
    "cstyle-raw3": C_LIKE._replace(triple="raw", holes="kotlin"),
    "cstyle-scala": C_LIKE._replace(triple="raw", holes="scala"),
    "csharp": C_LIKE._replace(verbatim=True, quote_run=True, holes="csharp"),
    "powershell": HASH._replace(blocks=(("<#", "#>", ()),), here_string=True,
                                holes="powershell"),
    "cstyle-tick": C_TICK,
    "rust": C_LIKE._replace(rust=True),
    "hash": HASH,
    "python": HASH._replace(triple="escape"),
    "php": Spec(lines=("//", "#"), blocks=C_BLOCK, ws_before=False),
    "sql": Spec(lines=("--",), blocks=C_BLOCK, quotes=("'",)),
    "markup": Spec(blocks=(("<!--", "-->", ()),), quotes=()),
    "css": Spec(blocks=C_BLOCK, quotes=('"', "'")),
    "scss": Spec(lines=("//",), blocks=C_BLOCK, doc_lines=("///",)),
    "vue": Spec(lines=("//",), blocks=C_BLOCK + (("<!--", "-->", ()),), backtick=True,
                doc_lines=("///",)),
}

EXTENSIONS = {
    **dict.fromkeys(("c", "cc", "cpp", "cxx", "h", "hpp", "hh", "proto", "m", "mm"), "cstyle"),
    **dict.fromkeys(("java", "groovy", "gradle", "swift", "dart"), "cstyle-triple"),
    **dict.fromkeys(("kt", "kts"), "cstyle-raw3"),
    "scala": "cstyle-scala",
    "cs": "csharp",
    **dict.fromkeys(("js", "jsx", "ts", "tsx", "mjs", "cjs", "go"), "cstyle-tick"),
    "rs": "rust",
    **dict.fromkeys(("py", "pyi"), "python"),
    **dict.fromkeys(("sh", "bash", "zsh", "rb", "pl", "r", "yml", "yaml", "toml", "tf",
                     "mk", "cmake", "properties", "conf", "ini"), "hash"),
    **dict.fromkeys(("ps1", "psm1", "psd1"), "powershell"),
    "php": "php",
    "sql": "sql",
    **dict.fromkeys(("html", "htm", "xml", "xhtml", "xsl", "xsd", "fxml", "jsp"), "markup"),
    "css": "css",
    **dict.fromkeys(("scss", "less"), "scss"),
    "vue": "vue",
}
NAMES = {"Dockerfile": "hash", "Makefile": "hash", "Jenkinsfile": "cstyle"}
SKIP_EXTENSIONS = frozenset((
    "md", "markdown", "txt", "json", "jsonl", "csv", "tsv", "lock", "svg", "png", "jpg", "jpeg",
    "gif", "ico", "webp", "pdf", "zip", "gz", "jar", "class", "woff", "woff2", "ttf", "eot",
    "map", "snap", "patch", "diff", "rst", "adoc", "tpl", "ftl"))

DIRECTIVE_RE = re.compile(
    r"(?i)^(?:!|eslint[-:]|@ts-|prettier-ignore|noqa\b|type:\s*ignore|pylint:|nolint\b|"
    r"nosonar|checkstyle[:\s]|istanbul\s+ignore|c8\s+ignore|coverage:|pragma\s*:|"
    r"pragma\s+(?:once|mark|warning|clang|omp)\b|shellcheck\s+(?:disable|source|shell|enable)\b|"
    r"rubocop:|fmt:\s*(?:on|off)|@formatter:|noinspection\b|#?(?:end)?region\b|"
    r"yamllint\b|jshint\b|tslint:|stylelint-|lint:|-\*-|\+build\b|go:|spotless:|"
    r"spdx-license-identifier)")
LICENSE_RE = re.compile(
    r"(?i)\b(?:copyright|all rights reserved|permission is hereby granted|"
    r"licen[cs]ed under|spdx-license-identifier)\b")
GENERATED_RE = re.compile(
    r"(?i)(?:code generated|do not edit|@generated|auto-?generated|generated by)")
LOCAL_NOTATION = frozenset((
    "SHA", "MD", "CVE", "CWE", "AES", "TLS", "UTC", "WCAG", "IEEE", "HTTP", "RSA", "ES", "TS"))


class LineInfo:
    __slots__ = ("code", "text", "doc", "in_comment")

    def __init__(self):
        self.code = False
        self.text = ""
        self.doc = False
        self.in_comment = False


def classify_path(path: str) -> str:
    """`checked`, `skip` (data or prose, no comments to judge) or `unchecked`."""
    name = path.rsplit("/", 1)[-1]
    if name in NAMES:
        return "checked"
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension in EXTENSIONS:
        return "checked"
    if extension in SKIP_EXTENSIONS:
        return "skip"
    return "unchecked"


def family_of(path: str) -> Spec:
    name = path.rsplit("/", 1)[-1]
    if name in NAMES:
        return FAMILIES[NAMES[name]]
    return FAMILIES[EXTENSIONS[name.rsplit(".", 1)[-1].lower()]]


_RUST_CHAR = re.compile(r"'(?:\\.[^']*|[^\\'])'")


def _close_of_string(raw: str, start: int, quote: str) -> int:
    """Index just past the closing quote, or -1 when the line ends first."""
    i = start
    while i < len(raw):
        if raw[i] == "\\":
            i += 2
            continue
        if raw[i] == quote:
            return i + 1
        i += 1
    return -1


def _close_verbatim(raw: str, start: int) -> int:
    """Index just past the closing quote of a verbatim string, or -1 when the line ends first."""
    i = start
    while i < len(raw):
        if raw[i] == '"':
            if raw.startswith('""', i):
                i += 2
                continue
            return i + 1
        i += 1
    return -1


def _close_triple(raw: str, start: int, quote: str, escape: bool) -> int:
    """Index just past the closing `quote` (three characters), or -1 when the line ends first."""
    i = start
    while i < len(raw):
        if escape and raw[i] == "\\":
            i += 2
            continue
        if raw.startswith(quote, i):
            return i + 3
        i += 1
    return -1


def _close_quote_run(raw: str, start: int, count: int) -> int:
    """Index just past the first run of `count` or more quotes at or after `start`, or -1."""
    found = re.compile('"{%d,}' % count).search(raw, start)
    return found.end() if found else -1


HOLE_DIALECTS = {
    "kotlin": ("//", ("/*", "*/"), "{", "}", "\\"),
    "scala": ("//", ("/*", "*/"), "{", "}", "\\"),
    "csharp": ("//", ("/*", "*/"), "{", "}", "\\"),
    "powershell": ("#", ("<#", "#>"), "(", ")", "`"),
}
HOLE_OPENERS = {
    "kotlin": re.compile(r"\$\{"),
    "scala": re.compile(r"(?<!\$)(?:\$\$)*\$\{"),
    "powershell": re.compile(r"(?<!`)(?:``)*\$\("),
}


def _skip_hole_string(raw: str, start: int, kind: str) -> int:
    """Index just past a quoted string inside a hole, or the line end when it stays open."""
    quote, escape = raw[start], HOLE_DIALECTS[kind][4]
    i = start + 1
    while i < len(raw):
        if kind == "powershell" and quote == "'":
            if raw[i] == "'":
                if raw.startswith("''", i):
                    i += 2
                    continue
                return i + 1
        elif raw[i] == escape:
            i += 2
            continue
        elif raw[i] == quote:
            return i + 1
        i += 1
    return len(raw)


def _scan_ps_string(raw: str, i: int) -> tuple[int, bool]:
    """Scan PowerShell double-quoted string text from `raw[i:]`.

    Returns `(index, opened)`: the index past the closing quote, or past a `$(` that opens
    a subexpression (`opened`), or the line end when the string stays open.
    """
    n = len(raw)
    while i < n:
        if raw[i] == "`":
            i += 2
        elif raw.startswith('""', i):
            i += 2
        elif raw[i] == '"':
            return i + 1, False
        elif raw.startswith("$(", i):
            return i + 2, True
        else:
            i += 1
    return n, False


def _scan_hole(raw: str, i: int, kind: str, stack: tuple, in_block: bool, width: int,
               pieces: list[str]):
    """Scan code inside an interpolation hole from `raw[i:]`.

    `stack` holds one bracket depth per open code level and `"dq"` per open PowerShell
    string. Returns `(index, stack, in_block, closed)`; comment text goes to `pieces`.
    """
    line_marker, (block_open, block_close), opener, closer, _ = HOLE_DIALECTS[kind]
    frames = list(stack)
    n = len(raw)
    while i < n:
        if frames[-1] == "dq":
            i, opened = _scan_ps_string(raw, i)
            if opened:
                frames.append(0)
            else:
                frames.pop()
            continue
        if in_block:
            end = raw.find(block_close, i)
            pieces.append(raw[i:] if end < 0 else raw[i:end])
            if end < 0:
                return n, tuple(frames), True, False
            in_block, i = False, end + len(block_close)
            continue
        if raw.startswith(block_open, i):
            end = raw.find(block_close, i + len(block_open))
            pieces.append(raw[i + len(block_open):] if end < 0 else raw[i + len(block_open):end])
            if end < 0:
                return n, tuple(frames), True, False
            i = end + len(block_close)
            continue
        if raw.startswith(line_marker, i) and (
                kind != "powershell" or i == 0 or raw[i - 1].isspace() or raw[i - 1] == "("):
            pieces.append(raw[i + len(line_marker):])
            return n, tuple(frames), False, False
        char = raw[i]
        if kind == "powershell" and char == '"':
            frames.append("dq")
            i += 1
            continue
        if char in "\"'":
            i = _skip_hole_string(raw, i, kind)
            continue
        if char == opener:
            frames[-1] += 1
        elif char == closer:
            if frames[-1] > 0:
                frames[-1] -= 1
            elif len(frames) > 1:
                frames.pop()
            elif raw.startswith(closer * width, i):
                return i + width, tuple(frames), False, True
        i += 1
    return n, tuple(frames), False, False


def scan(text: str, spec: Spec) -> list[LineInfo]:
    """One LineInfo per line: is there code, what comment text, is it a doc comment."""
    result: list[LineInfo] = []
    state = None   # ("block", close, doc) | ("str", quote)
    for raw in text.replace("\r\n", "\n").split("\n"):
        info = LineInfo()
        pieces: list[str] = []
        i, n = 0, len(raw)
        while i < n:
            if state is not None and state[0] == "block":
                _, close, doc = state
                end = raw.find(close, i)
                body = raw[i:] if end < 0 else raw[i:end]
                pieces.append(body)
                info.doc = info.doc or doc
                info.in_comment = True
                if end < 0:
                    i = n
                else:
                    state = None
                    i = end + len(close)
                continue
            if state is not None and state[0] == "vstr":
                info.code = True
                end = _close_verbatim(raw, i)
                if end < 0:
                    i = n
                else:
                    state = None
                    i = end
                continue
            if state is not None and state[0] == "hole":
                _, kind, outer, stack, in_block, width = state
                info.code = True
                before = len(pieces)
                i, stack, in_block, closed = _scan_hole(raw, i, kind, stack, in_block, width, pieces)
                info.in_comment = info.in_comment or len(pieces) > before
                state = outer if closed else ("hole", kind, outer, stack, in_block, width)
                continue
            if state is not None and state[0] in {"tri", "run", "str"}:
                info.code = True
                if state[0] == "tri":
                    end = _close_triple(raw, i, state[1], state[2])
                    opener = HOLE_OPENERS[state[3]].search(raw, i) if state[3] else None
                    if opener and (end < 0 or opener.start() < end):
                        state = ("hole", state[3], state, (0,), False, 1)
                        i = opener.end()
                        continue
                elif state[0] == "run":
                    end = _close_quote_run(raw, i, state[1])
                    braces = re.compile(r"\{{%d,}" % state[2]).search(raw, i) if state[2] else None
                    quotes = re.compile('"{%d,}' % state[1]).search(raw, i)
                    if braces and (quotes is None or braces.start() < quotes.start()):
                        state = ("hole", "csharp", state, (0,), False, state[2])
                        i = braces.end()
                        continue
                else:
                    end = _close_of_string(raw, i, "`")
                if end < 0:
                    i = n
                else:
                    state = None
                    i = end
                continue
            if state is not None and state[0] == "here":
                info.code = True
                if i == 0 and raw.startswith(state[1] + "@"):
                    state = None
                    i = 2
                    continue
                opener = HOLE_OPENERS["powershell"].search(raw, i) if state[1] == '"' else None
                if opener:
                    state = ("hole", "powershell", state, (0,), False, 1)
                    i = opener.end()
                else:
                    i = n
                continue
            char = raw[i]
            opened = False
            for open_, close, doc_opens in spec.blocks:
                if raw.startswith(open_, i):
                    doc = any(raw.startswith(d, i) for d in doc_opens) and raw[i:i + 4] != "/**/"
                    end = raw.find(close, i + len(open_))
                    info.in_comment = True
                    info.doc = info.doc or doc
                    if end < 0:
                        pieces.append(raw[i + len(open_):])
                        state = ("block", close, doc)
                        i = n
                    else:
                        pieces.append(raw[i + len(open_):end])
                        i = end + len(close)
                    opened = True
                    break
            if opened:
                continue
            marker = next((m for m in spec.lines if raw.startswith(m, i)), None)
            if marker is not None and (not spec.ws_before or i == 0 or raw[i - 1].isspace()):
                doc = any(raw.startswith(d, i) for d in spec.doc_lines) and \
                    not raw.startswith(marker * 2 + marker[0], i)
                pieces.append(raw[i + len(marker):])
                info.in_comment = True
                info.doc = info.doc or doc
                i = n
                continue
            if spec.triple and raw.startswith(('"""', "'''"), i):
                triple = raw[i:i + 3]
                escape = spec.triple == "escape"
                prefixed = i > 0 and (raw[i - 1].isalnum() or raw[i - 1] == "_")
                holes = spec.holes if spec.holes in {"kotlin", "scala"} and triple == '"""' \
                    and not escape and (spec.holes == "kotlin" or prefixed) else ""
                info.code = True
                state = ("tri", triple, escape, holes)
                i += 3
                continue
            if spec.quote_run and raw.startswith('"""', i):
                count = len(raw) - i - len(raw[i:].lstrip('"'))
                dollars = i - len(raw[:i].rstrip("$"))
                info.code = True
                state = ("run", count, dollars)
                i += count
                continue
            if spec.here_string and raw[i:i + 2] in ('@"', "@'") and not raw[i + 2:].strip():
                info.code = True
                state = ("here", raw[i + 1])
                i = n
                continue
            if spec.verbatim and raw.startswith(('@"', '$@"', '@$"'), i):
                info.code = True
                end = _close_verbatim(raw, raw.index('"', i) + 1)
                if end < 0:
                    state = ("vstr",)
                    i = n
                else:
                    i = end
                continue
            if char == "`" and spec.backtick:
                info.code = True
                end = _close_of_string(raw, i + 1, "`")
                if end < 0:
                    state = ("str",)
                    i = n
                else:
                    i = end
                continue
            if char in spec.quotes:
                info.code = True
                if spec.rust and char == "'" and not _RUST_CHAR.match(raw, i):
                    i += 1
                    continue
                end = _close_of_string(raw, i + 1, char)
                i = n if end < 0 else end
                continue
            if not char.isspace():
                info.code = True
            i += 1
        text_out = " ".join(p.strip().lstrip("*").strip() for p in pieces).strip()
        info.text = text_out
        result.append(info)
    return result


class ReferencePatterns:
    def __init__(self, regexes, notation=frozenset()):
        self.regexes = regexes
        self.notation = notation

    def find(self, text: str) -> str | None:
        for regex in self.regexes:
            for match in regex.finditer(text):
                value = match.group(0)
                prefix = re.match(r"([A-Z][A-Z0-9]*)-\d+$", value)
                if prefix and prefix.group(1) in self.notation:
                    continue
                return value
        return None


def _tsv(root: Path) -> dict[str, str]:
    values = {}
    try:
        lines = (root / "hooks" / "lib" / "sensitive-patterns.tsv").read_text(
            encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        if not line or line.startswith("#") or "\t" not in line:
            continue
        name, pattern = line.split("\t", 1)
        values[name] = pattern.strip()
    return values


def load_reference_patterns(plugin_root, tracker: str, keys: str = "") -> ReferencePatterns:
    """Tracker-owned reference forms.

    Configured project keys match alone. With none, the shared ticket shape applies
    minus the notation prefixes.
    """
    root = Path(plugin_root)
    tsv = _tsv(root)
    notation = (set((tsv.get("notation-prefixes") or "").split("|")) - {""}) | LOCAL_NOTATION
    project_keys = [k for k in re.split(r"[,\s|]+", keys or "") if re.fullmatch(r"[A-Za-z]\w*", k)]
    patterns: list[str] = []
    if tracker:
        manifest = root / "adapters" / "tracker" / tracker / "adapter.json"
        try:
            patterns = list(json.loads(manifest.read_text(encoding="utf-8")).get(
                "referencePatterns") or [])
        except (OSError, ValueError):
            patterns = []
    if project_keys:
        alternatives = "|".join(re.escape(k) for k in project_keys)
        patterns.append(rf"\b(?:{alternatives})-[0-9]{{1,7}}\b")
        notation = set()
    elif not patterns and tracker != "github-issues":
        patterns = [tsv.get("ticket-id") or r"[A-Z][A-Z0-9]{1,9}-[0-9]{1,6}"]
    return ReferencePatterns([re.compile(p) for p in patterns], notation)


def check_file(path: str, staged_text: str, added: set[int],
               patterns: ReferencePatterns) -> list[Finding]:
    infos = scan(staged_text, family_of(path))
    groups = _exempt_groups(infos)
    findings: list[Finding] = []
    run: list[int] = []

    def flush():
        if len(run) > MAX_RUN:
            findings.append(Finding(
                path, run[0], "cap",
                f"{path}:{run[0]}: {len(run)} consecutive added comment lines "
                f"(max {MAX_RUN}); move the rationale to the change (RATIONALE.md)"))
        run.clear()

    for number, info in enumerate(infos, 1):
        is_added = number in added
        in_group = number in groups
        exempt = in_group or bool(info.text and DIRECTIVE_RE.search(info.text))
        if is_added and info.text and not in_group:
            hit = patterns.find(info.text)
            if hit:
                findings.append(Finding(
                    path, number, "tracker",
                    f"{path}:{number}: tracker reference {hit} in an added comment; "
                    "put it on the change (RATIONALE.md)"))
        if not (is_added and info.in_comment):
            flush()
            continue
        if not info.text or exempt or info.doc:
            continue
        run.append(number)
    flush()
    return findings


def _exempt_groups(infos: list[LineInfo]) -> set[int]:
    """Line numbers inside a comment block holding license or generated-marker text."""
    exempt: set[int] = set()
    start = None
    for number in range(1, len(infos) + 2):
        info = infos[number - 1] if number <= len(infos) else None
        in_group = info is not None and info.in_comment and not info.code
        if in_group and start is None:
            start = number
        if not in_group and start is not None:
            block = range(start, number)
            if any(LICENSE_RE.search(infos[k - 1].text) or GENERATED_RE.search(infos[k - 1].text)
                   for k in block):
                exempt.update(block)
            start = None
    return exempt


def parse_added(diff: str) -> dict[str, set[int]]:
    """Path -> new line numbers of added lines, from a -U0 unified diff."""
    added: dict[str, set[int]] = {}
    path = None
    new_line = remaining = 0
    for raw in diff.splitlines():
        if raw.startswith("diff --git "):
            path = None
            remaining = 0
        elif remaining == 0 and raw.startswith("+++ "):
            target = raw[4:].split("\t", 1)[0]
            if target.startswith('"'):
                try:
                    target = json.loads(target)
                except ValueError:
                    target = target.strip('"')
            path = None if target == "/dev/null" else target[2:] if target[:2] == "b/" else target
        elif raw.startswith("@@") and path:
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", raw)
            if match:
                new_line = int(match.group(1))
                remaining = int(match.group(2)) if match.group(2) is not None else 1
        elif remaining > 0 and path and raw.startswith("+"):
            added.setdefault(path, set()).add(new_line)
            new_line += 1
            remaining -= 1
    return added


def staged_blobs(paths: list[str], cwd) -> dict[str, str]:
    """Staged content of each path through one `git cat-file --batch`."""
    if not paths:
        return {}
    request = "".join(f":{path}\n" for path in paths).encode("utf-8")
    run = subprocess.run(["git", "cat-file", "--batch"], cwd=cwd, input=request,
                         capture_output=True)
    data, position, blobs = run.stdout, 0, {}
    for path in paths:
        end = data.find(b"\n", position)
        if end < 0:
            break
        header = data[position:end].decode("utf-8", "replace").split()
        position = end + 1
        if len(header) == 3 and header[1] == "blob":
            size = int(header[2])
            blobs[path] = data[position:position + size].decode("utf-8", "replace")
            position += size + 1
    return blobs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-root", required=True)
    parser.add_argument("--tracker", default="")
    parser.add_argument("--project-keys", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    cwd = Path.cwd()
    diff = subprocess.run(
        ["git", "-c", "core.quotepath=off", "diff", "--cached", "-U0", "--no-color",
         "--no-ext-diff", "--diff-filter=ACMR"],
        cwd=cwd, capture_output=True).stdout.decode("utf-8", "replace")
    added = parse_added(diff)
    patterns = load_reference_patterns(args.plugin_root, args.tracker, args.project_keys)
    checked = sorted(p for p in added if classify_path(p) == "checked")
    unchecked = sorted(p for p in added if classify_path(p) == "unchecked")
    blobs = staged_blobs(checked, cwd)
    findings: list[Finding] = []
    for path in checked:
        if path in blobs:
            findings.extend(check_file(path, blobs[path], added[path], patterns))
    if args.json:
        print(json.dumps({"findings": [f._asdict() for f in findings], "unchecked": unchecked}))
    else:
        for finding in findings:
            print(finding.message, file=sys.stderr)
        if unchecked:
            print("[afk] comment gate: unchecked (no known comment syntax): "
                  + ", ".join(unchecked), file=sys.stderr)
    return 2 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

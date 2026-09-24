#!/usr/bin/env python3
"""Match a `.claude/rules/*.md` file's `paths:` frontmatter against one path.

One home for the glob semantics the nested-steering injector applies on a harness
with no native path-scoped rules, so a rule fires on the same path there as it
does natively. The pattern language mirrors the memory-page rules:

  - `**/*.ts`      any depth, `.ts` leaf
  - `src/**/*`     anything under `src/`
  - `*.md`         the base root only, never nested (a `*` never crosses `/`)
  - `{a,b}.md`     brace multiplication, capped at 1,000 patterns / 4 MiB
  - `[`            an unclosed / invalid class matches nothing
  - a YAML list OR a comma string is accepted for `paths:`
  - unparseable frontmatter, or no `paths:` key, means the rule is unconditional

`FIXTURES` is the table the test asserts against; it IS the specification.

Relative base for a nested `.claude/rules/`: patterns are matched against the
touched path relative to the directory that CONTAINS the `.claude` directory (so
a root `.claude/rules` matches relative to the repo root, and `<sub>/.claude/rules`
matches relative to `<sub>`). See providers/HARNESS-MATRIX.md.
"""
import re

BRACE_MAX_PATTERNS = 1000
BRACE_MAX_BYTES = 4 * 1024 * 1024


def frontmatter(text):
    """The frontmatter lines between the opening and closing `---`, or None.

    None means there is no parseable frontmatter (no leading `---`, or it never
    closes) — the caller reads that as unconditional.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i]
    return None


def _split_top(text):
    """Split on commas that are not inside quotes or a `{...}` brace group."""
    out, buf, depth, quote = [], [], 0, None
    for c in text:
        if quote:
            buf.append(c)
            if c == quote:
                quote = None
            continue
        if c in "\"'":
            quote = c
            buf.append(c)
        elif c == "{":
            depth += 1
            buf.append(c)
        elif c == "}":
            depth = max(0, depth - 1)
            buf.append(c)
        elif c == "," and depth == 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(c)
    out.append("".join(buf))
    return out


def parse_paths(text):
    """(patterns, unconditional) for a rule file's body.

    unconditional is True when the rule applies to every path — no frontmatter,
    unparseable frontmatter, no `paths:` key, or a `paths:` key with nothing
    usable under it.
    """
    fm = frontmatter(text)
    if fm is None:
        return [], True
    idx = None
    for i, line in enumerate(fm):
        if re.match(r"^paths\s*:", line):
            idx = i
            break
    if idx is None:
        return [], True
    rest = fm[idx].split(":", 1)[1].strip()
    patterns = []
    if rest and rest not in ("|", ">"):
        if rest.startswith("[") and rest.endswith("]"):
            rest = rest[1:-1]
        for tok in _split_top(rest):
            tok = tok.strip().strip('"').strip("'")
            if tok:
                patterns.append(tok)
    else:
        for line in fm[idx + 1:]:
            m = re.match(r"^\s*-\s*(.+)$", line)
            if not m:
                if line.strip() == "":
                    continue
                break
            tok = m.group(1).strip().strip('"').strip("'")
            if tok:
                patterns.append(tok)
    if not patterns:
        return [], True
    return patterns, False


def _find_brace(pattern):
    """First top-level `{...}` as (start, end, [options]), or None."""
    start = pattern.find("{")
    if start == -1:
        return None
    depth = 0
    options = []
    current = []
    i = start
    while i < len(pattern):
        c = pattern[i]
        if c == "{":
            depth += 1
            if depth == 1:
                i += 1
                continue
        elif c == "}":
            depth -= 1
            if depth == 0:
                options.append("".join(current))
                return start, i, options
        if depth == 1 and c == ",":
            options.append("".join(current))
            current = []
        else:
            current.append(c)
        i += 1
    return None  # no matching close: treat the `{` literally


def brace_expand(pattern):
    """Every brace expansion of `pattern`, or None when the budget is exceeded."""
    out = [pattern]
    while True:
        changed = False
        nxt = []
        for p in out:
            found = _find_brace(p)
            if found is None:
                nxt.append(p)
                continue
            changed = True
            start, end, options = found
            for opt in options:
                nxt.append(p[:start] + opt + p[end + 1:])
            if len(nxt) > BRACE_MAX_PATTERNS:
                return None
        out = nxt
        if not changed:
            break
    if len(out) > BRACE_MAX_PATTERNS or sum(len(p) for p in out) > BRACE_MAX_BYTES:
        return None
    return out


def _translate(pattern):
    """A glob (no braces) to an anchored regex, or None when it is invalid."""
    i, n = 0, len(pattern)
    out = ["^"]
    while i < n:
        c = pattern[i]
        if c == "*":
            if pattern[i:i + 3] == "**/":
                out.append("(?:.*/)?")
                i += 3
                continue
            if pattern[i:i + 2] == "**":
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
            i += 1
            continue
        if c == "?":
            out.append("[^/]")
            i += 1
            continue
        if c == "[":
            j = i + 1
            if j < n and pattern[j] in "!^":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:
                return None  # unclosed class: matches nothing
            body = pattern[i + 1:j]
            if body.startswith("!"):
                body = "^" + body[1:]
            out.append("[" + body + "]")
            i = j + 1
            continue
        out.append(re.escape(c))
        i += 1
    out.append("$")
    return "".join(out)


def match_one(pattern, rel):
    expanded = brace_expand(pattern)
    if expanded is None:
        return False
    for p in expanded:
        rx = _translate(p)
        if rx is None:
            continue
        try:
            if re.match(rx, rel):
                return True
        except re.error:
            continue
    return False


def matches(patterns, rel):
    rel = rel.replace("\\", "/").lstrip("/")
    return any(match_one(p, rel) for p in patterns)


def rule_matches(text, rel):
    """True when the rule file applies to `rel` (base-relative POSIX path)."""
    patterns, unconditional = parse_paths(text)
    if unconditional:
        return True
    return matches(patterns, rel)


# (paths_value_as_frontmatter_or_None, rel_path, expected). A None frontmatter
# is passed as a plain body with no `---`. A string value is a full file body.
def _fm(paths_line):
    return "---\n%s\n---\nbody\n" % paths_line


FIXTURES = [
    (_fm("paths: [\"**/*.ts\"]"), "src/a/b.ts", True),
    (_fm("paths: [\"**/*.ts\"]"), "a.ts", True),
    (_fm("paths: [\"**/*.ts\"]"), "a.js", False),
    (_fm("paths: [\"src/**/*\"]"), "src/a/b.js", True),
    (_fm("paths: [\"src/**/*\"]"), "src/a", True),
    (_fm("paths: [\"src/**/*\"]"), "lib/a.js", False),
    (_fm("paths: [\"*.md\"]"), "README.md", True),
    (_fm("paths: [\"*.md\"]"), "docs/README.md", False),
    (_fm("paths: [\"{a,b}.md\"]"), "a.md", True),
    (_fm("paths: [\"{a,b}.md\"]"), "b.md", True),
    (_fm("paths: [\"{a,b}.md\"]"), "c.md", False),
    (_fm("paths: [\"[.ts\"]"), "x.ts", False),          # invalid class: nothing
    (_fm("paths: a.md, b.md"), "b.md", True),           # comma string
    (_fm("paths:\n  - \"one.md\"\n  - \"two.md\""), "two.md", True),  # block list
    ("body with no frontmatter\n", "anything.txt", True),             # unconditional
    ("---\npaths: [\"*.md\"]\n(no close)\nbody\n", "deep/x.md", True),  # unparseable -> unconditional
    (_fm("title: x"), "whatever.py", True),             # no paths: key -> unconditional
]

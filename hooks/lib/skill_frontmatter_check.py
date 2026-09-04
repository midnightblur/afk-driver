"""Check F — every SKILL.md frontmatter is loadable YAML naming its own directory.

A harness that cannot parse a skill's frontmatter does not report an error: it
drops the skill, and the catalog looks one entry shorter than the manifest with
nothing to say why. That is how `/afk:diagnose` was absent from one harness for
nine releases while passing every other gate — its description was an unquoted
scalar containing `": "`, which YAML reads as a nested mapping.

Prints one line per problem and exits 0 either way; the caller owns the verdict.
"""
import pathlib
import re
import sys

try:
    import yaml
except ImportError:                    # a real parser when present, rules below when not
    yaml = None

FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\s*?\r?\n", re.S)
ENTRY = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(.*)$")


def plain_scalar_problem(key, value):
    """The YAML rules a plain (unquoted, non-block) scalar must obey.

    Only the two that a description realistically breaks, both of which make the
    line parse as something other than the string that was meant.
    """
    v = value.strip()
    if not v or v[0] in "|>\"'":       # empty, block scalar, or quoted — all fine
        return None
    if ": " in v:
        return "%s: unquoted value contains ': ' — YAML reads it as a nested mapping" % key
    if v.endswith(":"):
        return "%s: unquoted value ends with ':' — YAML reads it as a mapping key" % key
    return None


def check(path):
    """Problems with one SKILL.md, as strings."""
    text = path.read_text(encoding="utf-8")
    rel = path.as_posix()
    out = []

    if text.startswith("﻿"):
        out.append("%s: starts with a byte-order mark before the frontmatter" % rel)
        text = text.lstrip("﻿")

    m = FRONTMATTER.match(text)
    if not m:
        return ["%s: no YAML frontmatter block at the top of the file" % rel]
    body = m.group(1)

    if yaml is not None:
        try:
            doc = yaml.safe_load(body)
        except Exception as exc:
            first = str(exc).splitlines()[0]
            return ["%s: frontmatter is not loadable YAML (%s: %s)" % (rel, type(exc).__name__, first)]
        if not isinstance(doc, dict):
            return ["%s: frontmatter is not a mapping" % rel]
        fields = doc
    else:
        fields = {}
        for line in body.splitlines():
            if not line or line[:1].isspace() or line.lstrip().startswith("#"):
                continue           # continuation of a block scalar, or a comment
            entry = ENTRY.match(line)
            if not entry:
                out.append("%s: frontmatter line is not `key: value` — %r" % (rel, line[:60]))
                continue
            key, value = entry.group(1), entry.group(2)
            problem = plain_scalar_problem(key, value)
            if problem:
                out.append("%s: %s" % (rel, problem))
            fields[key] = value.strip()

    name = fields.get("name")
    if not name:
        out.append("%s: frontmatter has no `name`" % rel)
    elif str(name).strip() != path.parent.name:
        out.append("%s: frontmatter name %r does not match its directory %r"
                   % (rel, str(name).strip(), path.parent.name))
    if not str(fields.get("description", "")).strip():
        out.append("%s: frontmatter has no `description`" % rel)
    return out


def main():
    root = pathlib.Path(sys.argv[1])
    problems = []
    for skill in sorted((root / "skills").glob("*/*/SKILL.md")):
        problems += check(skill)
    for line in problems:
        print(line.replace(root.as_posix() + "/", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Print one version's CHANGELOG.md section body, for a release page.

    python .github/scripts/changelog_section.py 1.4.0 [CHANGELOG.md]

The body is every line after `## [<version>]` up to the next `## [` heading,
trimmed. Exit 1 when the heading is missing or its body is empty.
"""
import re
import sys


def section(text: str, version: str) -> str:
    version = version.removeprefix("v")
    heading = re.compile(r"^## \[" + re.escape(version) + r"\]")
    lines, inside = [], False
    for line in text.splitlines():
        if line.startswith("## ["):
            if inside:
                break
            inside = bool(heading.match(line))
            continue
        if inside:
            lines.append(line)
    return "\n".join(lines).strip()


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__.strip(), file=sys.stderr)
        return 1
    path = sys.argv[2] if len(sys.argv) == 3 else "CHANGELOG.md"
    with open(path, encoding="utf-8") as handle:
        body = section(handle.read(), sys.argv[1])
    if not body:
        print(f"changelog_section: no entries under [{sys.argv[1]}] in {path}", file=sys.stderr)
        return 1
    sys.stdout.write(body + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

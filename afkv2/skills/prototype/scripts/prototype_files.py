"""The disk side of prototype, from the repository root (SDD §3, §8 row "skills/prototype").

`prototype_files.py start --ticket KEY [--frontend NAME]`: the paths of the spec folder, the frontend of the config,
  its catalog, the live block and the anchor (decision D-2). Refuses `missing-input`, `no-frontend`, `pick-frontend`.
`prototype_files.py check --mockup FILE`: refuses `network-call` with each line of a call or a scheme URL, and
  `afkv2-runtime` on the tooltip block; `unreadable` for a file it cannot read.
`prototype_files.py settle --ticket KEY`: checks PROTOTYPE.md against PROTOTYPE-FORMAT.md, checks and scans every
  file of the prototype, then sets the INDEX.md Prototype row. Refuses `bad-prototype`, `network-call`,
  `afkv2-runtime`, `secrets`; INDEX.md stays as it is on each refusal.

Each answer is one JSON object; exit 0 ok, 1 refused, 2 unreadable input.
"""

from __future__ import annotations

import bisect
import re
import sys
from datetime import date
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
PLUGIN = SKILL.parents[1]
sys.path.insert(0, str(SKILL.parent / "use-lavish" / "scripts"))
sys.path.insert(0, str(PLUGIN / "engine"))
sys.path.insert(0, str(PLUGIN / "scripts"))
sys.path.insert(0, str(SKILL.parent / "to-prd" / "scripts"))

import afkv2_config  # noqa: E402
import prd_files  # noqa: E402
from grill_common import Parser, Refusal, serve  # noqa: E402
from page_home import ticket_slug  # noqa: E402
from shell.inject import MARK_END, MARK_START  # noqa: E402

TO_PRD = "/afkv2:to-prd"
ADD_FRONTEND = "catalog_files.py add-frontend --name N --source S --catalog C"
CATALOG_MARK = "README.md"
FILE_NAME = "PROTOTYPE.md"
MOCKUP_DIR = "prototype"
INDEX_ROW = "Prototype"
# Lockstep with PROTOTYPE-FORMAT.md, which owns the format; a test checks that it names each of these.
SECTIONS = ("Screens", "Coverage", "Fidelity", "Decisions", "PRD gaps")
STATES = ("reachable", "gap", "retired")
MARKS = ("live-verified", "catalog", "source-only")
FIDELITY = re.compile(rf"^> Fidelity: *({'|'.join(MARKS)})(?: · screenshots: *(.*?))?\s*$", re.M)

# A scheme URL counts only where a browser loads it (decision D-3): an attribute that fetches or navigates, a CSS
# url() or @import, and an ES import from an address. A scheme here is any `<letters>:` or `//`, except the inline
# and local ones below.
LOCAL_SCHEMES = ("data", "blob", "javascript", "mailto", "tel", "about")
_ADDRESS = rf"(?:(?!(?:{'|'.join(LOCAL_SCHEMES)}):)[A-Za-z][A-Za-z0-9+.-]*:|//)"
NETWORK = {
    "attribute": re.compile(rf"\b(?:src|href|action|formaction|srcset|poster|data|background)\s*=\s*[\"']?\s*{_ADDRESS}",
                            re.I),
    "css-url": re.compile(rf"\burl\(\s*[\"']?\s*{_ADDRESS}", re.I),
    "css-import": re.compile(rf"@import\s+[\"']\s*{_ADDRESS}", re.I),
    "import-from": re.compile(rf"\bfrom\s*[\"']\s*{_ADDRESS}"),
    "fetch": re.compile(r"\bfetch\s*\("),
    "XMLHttpRequest": re.compile(r"\bXMLHttpRequest\b"),
    "WebSocket": re.compile(r"\bWebSocket\s*\("),
    "EventSource": re.compile(r"\bEventSource\s*\("),
    "import()": re.compile(r"(?<![@\w.])import\s*\("),
    "sendBeacon": re.compile(r"\bsendBeacon\s*\("),
}


def _line_of(breaks, offset):
    return bisect.bisect_right(breaks, offset) + 1


def find_network_calls(text):
    """1 finding `{line, found, text}` per line with a call or a scheme URL, in line order. `found` names each kind
    on that line; `text` is the stripped line. Works on any text: a mockup, a catalog card or a style sheet."""
    breaks = [match.start() for match in re.finditer("\n", text)]
    lines = text.split("\n")
    kinds = {}
    for kind, pattern in NETWORK.items():
        for match in pattern.finditer(text):
            found = kinds.setdefault(_line_of(breaks, match.start()), [])
            if kind not in found:
                found.append(kind)
    return [{"line": line, "found": found, "text": lines[line - 1].strip()} for line, found in sorted(kinds.items())]


def _read(path):
    try:
        return Path(path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise Refusal("unreadable", f"{path}: {error}", 2) from error


def _where(findings, name):
    return ", ".join(f"{name}:{finding['line']}" for finding in findings)


def check_text(text, name):
    """Refuse `afkv2-runtime`, then `network-call`, for the text of one written file; `name` names it."""
    marks = [number for number, line in enumerate(text.split("\n"), 1) if MARK_START in line or MARK_END in line]
    if marks:
        raise Refusal("afkv2-runtime", f"the afkv2 tooltip block at {', '.join(f'{name}:{n}' for n in marks)}: a "
                                       "committed mockup holds no afkv2 runtime; delete the block between its marks "
                                       "and open the mockup with --plain", file=str(name), lines=marks)
    calls = find_network_calls(text)
    if calls:
        raise Refusal("network-call", f"a network call or a scheme URL at {_where(calls, name)}: a mockup makes no "
                                      "network call; inline the asset or use a #id link", file=str(name), lines=calls)


def cmd_check(argv):
    parser = Parser(add_help=False)
    parser.add_argument("--mockup", required=True)
    args = parser.parse_args(argv)
    text = _read(args.mockup)
    check_text(text, args.mockup)
    return {"ok": True, "file": args.mockup, "bytes": len(text.encode("utf-8"))}


def _config():
    config = afkv2_config.read_config()
    if not config["ok"]:
        raise Refusal(config["error"]["code"], config["error"]["reason"])
    return config


def _spec(config, ticket):
    """The spec folder of the ticket, with its PRD; a missing PRD refuses `missing-input`."""
    spec_dir = Path(config["spec_folder"]) / ticket_slug(ticket)
    prd = spec_dir / "PRD.md"
    if not prd.is_file():
        raise Refusal("missing-input", f"missing {prd.as_posix()}; {TO_PRD} writes it", missing=prd.as_posix(),
                      writer=TO_PRD)
    return spec_dir


def _frontend(frontends, name):
    """The config entry the run uses: the named one, else the only one."""
    names = [entry["name"] for entry in frontends]
    if name is not None and name not in names:
        raise Refusal("no-frontend", f"the config names no frontend {name!r} (it names {names or 'none'}); add it "
                                     f"with `{ADD_FRONTEND}`")
    if not frontends:
        raise Refusal("no-frontend", f"the config names no frontend; add one with `{ADD_FRONTEND}`")
    if name is None and len(frontends) > 1:
        raise Refusal("pick-frontend", f"the config names {len(names)} frontends: {', '.join(names)}; give one with "
                                       "--frontend", names=names)
    return next(entry for entry in frontends if name in (None, entry["name"]))


def cmd_start(argv):
    parser = Parser(add_help=False)
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--frontend")
    args = parser.parse_args(argv)
    config = _config()
    spec_dir = _spec(config, args.ticket)
    frontend = _frontend(config["frontends"], args.frontend)
    # A catalog exists when its folder holds the catalog README (decision D-2); config paths stay relative (D-1).
    catalog_exists = (Path(config["repo_root"]) / frontend["catalog"] / CATALOG_MARK).is_file()
    live = config.get("live")
    prototype_md = spec_dir / FILE_NAME
    return {"ok": True, "ticket": args.ticket, "spec_dir": spec_dir.as_posix(), "prd": (spec_dir / "PRD.md").as_posix(),
            "index": (spec_dir / "INDEX.md").as_posix(), "prototype_md": prototype_md.as_posix(),
            "mockup_dir": (spec_dir / MOCKUP_DIR).as_posix(), "frontend": frontend, "catalog_exists": catalog_exists,
            "live": live, "anchor": "catalog" if catalog_exists else "live" if live else "source",
            "resume": prototype_md.is_file()}


def _sections(markdown):
    """[(name, body)] of each `##` section, in order."""
    parts = re.split(r"^## +(.+?)[ \t]*$", markdown, flags=re.M)
    return list(zip(parts[1::2], parts[2::2]))


def _table(body):
    """The rows of the first table in `body` as {header cell: cell}."""
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    cells = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]
    if not cells:
        return []
    head = cells[0]
    return [dict(zip(head, row)) for row in cells[1:] if not all(set(cell) <= set("-: ") for cell in row)]


def prd_stories(markdown):
    """The story numbers of the PRD `## User Stories` list, as text."""
    body = dict(_sections(markdown)).get("User Stories", "")
    return [match.group(1) for match in re.finditer(r"^\s*(\d+)\.\s", body, re.M)]


def _header_problems(markdown, frontends):
    problems = []
    frontend = re.search(r"^> Frontend: *(\S.*?)\s*$", markdown, re.M)
    if not frontend:
        problems.append("no header line `> Frontend: <name>`")
    elif frontend.group(1) not in frontends:
        problems.append(f"frontend `{frontend.group(1)}` is not in the config frontends list ({', '.join(frontends)})")
    fidelity = FIDELITY.search(markdown)
    if not fidelity:
        problems.append(f"no header line `> Fidelity: <mark>` with a mark of {', '.join(MARKS)}")
    if not re.search(r"^> Date: *\d{4}-\d{2}-\d{2}\s*$", markdown, re.M):
        problems.append("no header line `> Date: <YYYY-MM-DD>`")
    return problems


def prototype_problems(markdown, stories, spec_dir, frontends):
    """Each way PROTOTYPE.md breaks PROTOTYPE-FORMAT.md; empty when it holds."""
    problems = _header_problems(markdown, frontends)
    sections = _sections(markdown)
    names = [name for name, _ in sections]
    for section in SECTIONS:
        if section not in names:
            problems.append(f"no section `## {section}`")
    present = [name for name in names if name in SECTIONS]
    if not problems and present != list(SECTIONS):
        problems.append(f"the sections come in the order {', '.join(SECTIONS)}")
    bodies = dict(sections)
    screens = _table(bodies.get("Screens", ""))
    if "Screens" in bodies and not screens:
        problems.append("the Screens table has no row")
    for screen in screens:
        mockup = screen.get("Mockup", "").strip("` ")
        if not mockup or not (spec_dir / mockup).is_file():
            problems.append(f"screen {screen.get('Screen')!r}: no mockup file {mockup or '(empty)'} in {spec_dir.as_posix()}")
    covered = []
    for row in _table(bodies.get("Coverage", "")):
        story, state = row.get("Story", ""), row.get("State", "").strip("` ")
        if story in covered:
            problems.append(f"story {story} has 2 coverage rows")
        covered.append(story)
        if story not in stories:
            problems.append(f"a coverage row for story {story}, which the PRD does not hold")
        if state not in STATES:
            problems.append(f"story {story}: state `{state}` is not one of {', '.join(STATES)}")
    if "Coverage" in bodies:
        problems += [f"no coverage row for story {story}" for story in stories if story not in covered]
    return problems


def _written_files(spec_dir):
    """PROTOTYPE.md and every file in the mockup folder, from the spec folder."""
    files = [spec_dir / FILE_NAME, *sorted(p for p in (spec_dir / MOCKUP_DIR).rglob("*") if p.is_file())]
    return [(path, path.relative_to(spec_dir).as_posix()) for path in files]


def cmd_settle(argv):
    parser = Parser(add_help=False)
    parser.add_argument("--ticket", required=True)
    args = parser.parse_args(argv)
    config = _config()
    spec_dir = _spec(config, args.ticket)
    index, prototype_md = spec_dir / "INDEX.md", spec_dir / FILE_NAME
    if not index.is_file():
        raise Refusal("missing-input", f"missing {index.as_posix()}; {TO_PRD} writes it", missing=index.as_posix(),
                      writer=TO_PRD)
    if not prototype_md.is_file():
        raise Refusal("bad-prototype", f"no {prototype_md.as_posix()}", problems=[f"no {FILE_NAME}"])
    stories = prd_stories(_read(spec_dir / "PRD.md").replace("\r\n", "\n"))
    frontends = [entry["name"] for entry in config["frontends"]]
    problems = prototype_problems(_read(prototype_md).replace("\r\n", "\n"), stories, spec_dir, frontends)
    if problems:
        raise Refusal("bad-prototype", "; ".join(problems), problems=problems)
    files = _written_files(spec_dir)
    state = f"chosen {date.today().isoformat()}"
    prd_files.set_row(index, INDEX_ROW, FILE_NAME, state)
    return {"ok": True, "scanned": [name for _, name in files], "index_state": state}


VERBS = {"start": cmd_start, "check": cmd_check, "settle": cmd_settle}


def main(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", 2)
    return VERBS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(serve(main))

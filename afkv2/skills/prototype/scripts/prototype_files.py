"""The disk side of prototype, from the repository root (SDD §3, §8 row "skills/prototype").

`prototype_files.py start --ticket KEY [--frontend NAME]`: the paths of the spec folder, the frontend of the config,
  its catalog, the live block and the anchor (decision D-2). Refuses `missing-input`, `no-frontend`, `pick-frontend`.
`prototype_files.py check --mockup FILE`: refuses `network-call` with each line of a call or a scheme URL in any place, and
  `afkv2-runtime` on the tooltip block; `unreadable` for a file it cannot read.
`prototype_files.py settle --ticket KEY`: checks PROTOTYPE.md against PROTOTYPE-FORMAT.md, checks and scans every
  file of the prototype, then sets the INDEX.md Prototype row. Refuses `bad-prototype`, `network-call`,
  `afkv2-runtime`, `secrets`; INDEX.md stays as it is on each refusal.

Each answer is one JSON object; exit 0 ok, 1 refused, 2 unreadable input.
"""

from __future__ import annotations

import bisect
import html
import re
import sys
from datetime import date
from pathlib import Path, PurePosixPath

SKILL = Path(__file__).resolve().parents[1]
PLUGIN = SKILL.parents[1]
sys.path.insert(0, str(SKILL.parent / "use-lavish" / "scripts"))
sys.path.insert(0, str(PLUGIN / "engine"))
sys.path.insert(0, str(PLUGIN / "scripts"))
sys.path.insert(0, str(SKILL.parent / "to-prd" / "scripts"))

import afkv2_config  # noqa: E402
import notices  # noqa: E402
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

# A call counts by its name. A scheme URL counts in any place of the text (decision D-3, widened after review): in a
# place that loads, any `<letters>:` or `//`; elsewhere, any `<letters>://`, and a `//host` that starts a quoted value,
# an `=` value or a `(` argument. The inline and local schemes below pass. `\` counts as `/`, and each line is read
# with its HTML entities decoded. A W3C namespace name and a doctype id are names, never loaded, so they pass. A
# relative path, such as `new Worker('w.js')`, stays local.
LOCAL_SCHEMES = ("data", "blob", "javascript", "mailto", "tel", "about")
_LOCAL = rf"(?!(?:{'|'.join(LOCAL_SCHEMES)}):)"
_SLASHES = r"[/\\]{2}"
_ADDRESS = rf"(?:{_LOCAL}[A-Za-z][A-Za-z0-9+.-]*:|{_SLASHES})"
NETWORK = {
    "attribute": re.compile(rf"\b(?:src|href|action|formaction|poster|background)\s*=\s*[\"']?\s*{_ADDRESS}", re.I),
    "srcset": re.compile(rf"\bsrcset\s*=\s*(?:[\"'][^\"']*?(?<=[\"'\s,])\s*)?{_ADDRESS}", re.I),
    "object-data": re.compile(rf"<object\b[^>]*\bdata\s*=\s*[\"']?\s*{_ADDRESS}", re.I),
    "css-url": re.compile(rf"\burl\(\s*[\"']?\s*{_ADDRESS}", re.I),
    "css-import": re.compile(rf"@import\s+[\"']\s*{_ADDRESS}", re.I),
    "import-from": re.compile(rf"\bfrom\s*[\"']\s*{_ADDRESS}"),
    "import": re.compile(rf"\bimport\s*[\"']\s*{_ADDRESS}"),
    "fetch": re.compile(r"\bfetch\s*\("),
    "XMLHttpRequest": re.compile(r"\bXMLHttpRequest\b"),
    "WebSocket": re.compile(r"\bWebSocket\s*\("),
    "EventSource": re.compile(r"\bEventSource\s*\("),
    "import()": re.compile(r"(?<![@\w.])import\s*\("),
    "sendBeacon": re.compile(r"\bsendBeacon\s*\("),
    "address": re.compile(rf"(?<![\w+.:-]){_LOCAL}[A-Za-z][A-Za-z0-9+.-]*:{_SLASHES}|(?:[\"'(]\s*|=){_SLASHES}(?=[\w\[])"),
}
_NAMES = re.compile(r"<!DOCTYPE[^>]*>|https?://www\.w3\.org/(?:2000/svg|1999/xhtml|1999/xlink|1998/Math/MathML"
                    r"|XML/1998/namespace|2000/xmlns/?)(?![\w/.-])", re.I)


# A load of another page. lavish (0.1.86) annotates only the file it opened and refuses a load whose query changed,
# so a mockup is 1 page that routes by its hash. A link or a form target counts unless it starts with `#` or a scheme
# (a scheme URL is a network call); a `location` use counts unless it is the hash.
PAGE_LEAVE = {
    "link": re.compile(r"\b(?:href|action|formaction)\s*=(?!=)\s*"
                       r"(?![\"']?\s*(?:#|[A-Za-z][A-Za-z0-9+.-]*:|[/\\]{2}))", re.I),
    "location-call": re.compile(r"\blocation\s*\.\s*(?:search|pathname|assign|replace|reload)\b"),
    "location-write": re.compile(r"\blocation(?:\s*\.\s*href)?\s*=(?!=)"),
}


def _line_of(breaks, offset):
    return bisect.bisect_right(breaks, offset) + 1


def find_network_calls(text):
    """1 finding `{line, found, text}` per line with a call or a scheme URL, in line order. `found` names each kind
    on that line; `text` is the stripped line. Works on any text: a mockup, a catalog card or a style sheet."""
    return _find(text, NETWORK, _NAMES)


def find_page_leaves(text):
    """1 finding `{line, found, text}` per line that loads another page: a link or a form target that is not a `#`
    route, or a `location` use that is not the hash."""
    return _find(text, PAGE_LEAVE)


def _find(text, patterns, names_pattern=None):
    """1 finding per line where a pattern of `patterns` matches, each line read with its HTML entities decoded. A
    match of the kind `address` inside a match of `names_pattern` does not count."""
    lines = text.split("\n")
    decoded = "\n".join(html.unescape(line).replace("\n", " ") for line in lines)
    breaks = [match.start() for match in re.finditer("\n", decoded)]
    names = [match.span() for match in names_pattern.finditer(decoded)] if names_pattern else []
    kinds = {}
    for kind, pattern in patterns.items():
        for match in pattern.finditer(decoded):
            if kind == "address" and any(start <= match.start() < end for start, end in names):
                continue
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
    """Refuse `afkv2-runtime`, then `network-call`, then `page-leave`, for the text of one written file; `name` names it."""
    marks = [number for number, line in enumerate(text.split("\n"), 1) if MARK_START in line or MARK_END in line]
    if marks:
        where = _where([{"line": number} for number in marks], name)
        raise Refusal("afkv2-runtime", f"the afkv2 tooltip block at {where}: a "
                                       "committed mockup holds no afkv2 runtime; delete the block between its marks "
                                       "and open the mockup with --plain", file=str(name), lines=marks)
    calls = find_network_calls(text)
    if calls:
        raise Refusal("network-call", f"a network call or a scheme URL at {_where(calls, name)}: a mockup makes no "
                                      "network call; inline the asset or use a #id link", file=str(name), lines=calls)
    leaves = find_page_leaves(text)
    if leaves:
        raise Refusal("page-leave", f"a load of another page at {_where(leaves, name)}: a mockup is 1 page that "
                                    "routes by its hash; link to #/<screen> and keep all state in the hash",
                      file=str(name), lines=leaves)


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
        raise Refusal(config["error"]["code"], config["error"]["reason"], afkv2_config.exit_code(config))
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
            "requirement_adrs": (spec_dir / "adr" / "requirements").as_posix(), "index": (spec_dir / "INDEX.md").as_posix(), "prototype_md": prototype_md.as_posix(),
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
    """The story numbers of the PRD `## User Stories` list, as text: the number of a numbered item, else the
    position of a top-level bullet item, from 1. Indented items are no stories."""
    body = dict(_sections(markdown)).get("User Stories", "")
    items = re.findall(r"^(?:(\d+)\.|[-*+])\s", body, re.M)
    return list(dict.fromkeys(number or str(position) for position, number in enumerate(items, 1)))


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
    elif fidelity.group(1) == "live-verified" and not [n for n in (fidelity.group(2) or "").split(",") if n.strip()]:
        problems.append("fidelity live-verified names no screenshot: add ` · screenshots: <file>, <file>`")
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
    pages = sorted(p.name for p in (spec_dir / MOCKUP_DIR).glob("*.html"))
    if len(pages) > 1:
        problems.append(f"{MOCKUP_DIR}/ holds {len(pages)} HTML files: {', '.join(pages)}; a mockup is 1 file that "
                        "routes each screen by its hash")
    for screen in screens:
        mockup = screen.get("Mockup", "").strip("` ").split("#", 1)[0]  # the file; `#/<screen>` is its route
        parts = PurePosixPath(mockup).parts
        if len(parts) < 2 or parts[0] != MOCKUP_DIR or ".." in parts:
            problems.append(f"screen {screen.get('Screen')!r}: mockup {mockup or '(empty)'} is not a file in {MOCKUP_DIR}/")
        elif not (spec_dir / mockup).is_file():
            problems.append(f"screen {screen.get('Screen')!r}: no mockup file {mockup or '(empty)'} in {spec_dir.as_posix()}")
    covered = []
    for row in _table(bodies.get("Coverage", "")):
        story, state = row.get("Story", "").strip("` "), row.get("State", "").strip("` ")
        if story in covered:
            problems.append(f"story {story} has 2 coverage rows")
        covered.append(story)
        if story not in stories and state != "retired":
            problems.append(f"a coverage row for story {story}, which the PRD does not hold")
        if story in stories and state == "retired":
            problems.append(f"story {story} is in the PRD, so it is not retired: use reachable or gap")
        if state not in STATES:
            problems.append(f"story {story}: state `{state}` is not one of {', '.join(STATES)}")
    if not stories:
        problems.append("the PRD holds no story: its `## User Stories` section has no top-level list item")
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
    files = _written_files(spec_dir)
    problems += [f"{name} is over {notices.MAX_SCAN_BYTES} bytes, past what the secret scan reads"
                 for path, name in files if path.stat().st_size > notices.MAX_SCAN_BYTES]
    if problems:
        raise Refusal("bad-prototype", "; ".join(problems), problems=problems)
    for path, name in files[1:]:  # the mockup folder; PROTOTYPE.md may name the calls of the live app
        check_text(path.read_bytes().decode("utf-8", "replace"), name)
    hits = notices.scan_files(files)
    if hits:
        where = ", ".join(f"{hit['file']}:{hit['line']} ({hit['shape']})" for hit in hits)
        raise Refusal("secrets", f"a secret shape at {where}: a prototype holds made-up data only", hits=hits)
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

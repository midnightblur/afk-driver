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
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
PLUGIN = SKILL.parents[1]
sys.path.insert(0, str(SKILL.parent / "use-lavish" / "scripts"))
sys.path.insert(0, str(PLUGIN / "engine"))
sys.path.insert(0, str(PLUGIN / "scripts"))

import afkv2_config  # noqa: E402
from grill_common import Parser, Refusal, serve  # noqa: E402
from page_home import ticket_slug  # noqa: E402
from shell.inject import MARK_END, MARK_START  # noqa: E402

TO_PRD = "/afkv2:to-prd"
ADD_FRONTEND = "catalog_files.py add-frontend --name N --source S --catalog C"
CATALOG_MARK = "README.md"
FILE_NAME = "PROTOTYPE.md"
MOCKUP_DIR = "prototype"

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


VERBS = {"start": cmd_start, "check": cmd_check}


def main(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", 2)
    return VERBS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(serve(main))

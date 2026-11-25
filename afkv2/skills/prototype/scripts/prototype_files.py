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

from grill_common import Refusal, serve  # noqa: E402

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


VERBS = {}


def main(argv):
    if not argv or argv[0] not in VERBS:
        raise Refusal("usage", f"the verbs are {', '.join(VERBS)}", 2)
    return VERBS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(serve(main))

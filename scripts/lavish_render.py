"""Render a lavish decision surface from its round JSON.

    python scripts/lavish_render.py <round.json> [-o <artifact.html>]
    python scripts/lavish_render.py <round.json> --check

The agent authors data; this script authors markup. No model writes HTML on
this path, and the same JSON renders byte-identical HTML every time — the
artifact is a build product, the JSON is the durable state.

`LAVISH-KIT.md` at the plugin root is the normative contract: the round
document, the six components, the skeleton and the response grammar. Read it
before authoring a round.

Exit codes:
    0  rendered (or `--check` found no violation)
    1  contract violation — the message names the item and the field
    2  the file is missing or is not JSON

A non-zero exit is not a phase failure: it is the licence to fall back to the
skill's markdown flow, which loses no work.

Standard library only, no network, no external assets in the output.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lavish import page, schema  # noqa: E402


def _links(doc):
    """Every `links[]` entry on every round header, with its round number."""
    for rnd in doc.get("rounds") or []:
        header = rnd.get("header") if isinstance(rnd, dict) else None
        if not isinstance(header, dict):
            continue
        for link in header.get("links") or []:
            if isinstance(link, dict) and link.get("href"):
                yield rnd.get("round"), link["href"]


def warn_dead_links(doc, artifact_dir):
    """Warn on a relative href with no file behind it.

    A dead link is the one failure on this page a human hits and the agent
    never does — it surfaces on a click, long after the render. A warning, not
    an exit: the artifact may legitimately move, and a page is still worth
    rendering with one bad link in it.
    """
    warned = 0
    for number, href in _links(doc):
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href) or href.startswith(("//", "#", "/")):
            continue
        target = href.split("#", 1)[0].split("?", 1)[0]
        if not target:
            continue
        if not os.path.exists(os.path.join(artifact_dir, target)):
            sys.stderr.write("lavish_render: warning: round %s links to %s, which is not "
                             "there beside the artifact\n" % (number, href))
            warned += 1
    return warned


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="lavish_render.py",
        description="Render a lavish decision surface from its round JSON.")
    parser.add_argument("source", help="the round JSON")
    parser.add_argument("-o", "--out",
                        help="artifact path (default: the JSON's name with .html)")
    parser.add_argument("--check", action="store_true",
                        help="validate only; write nothing")
    args = parser.parse_args(argv)

    try:
        with open(args.source, encoding="utf-8") as handle:
            doc = json.load(handle)
    except OSError as exc:
        sys.stderr.write("lavish_render: cannot read %s: %s\n" % (args.source, exc))
        return 2
    except ValueError as exc:
        sys.stderr.write("lavish_render: %s is not valid JSON: %s\n" % (args.source, exc))
        return 2

    try:
        doc = schema.load(doc)
        html = page.build(doc)
    except schema.ContractError as exc:
        sys.stderr.write("lavish_render: contract violation: %s\n" % exc)
        return 1

    out = args.out or (os.path.splitext(args.source)[0] + ".html")
    warn_dead_links(doc, os.path.dirname(os.path.abspath(out)))

    if args.check:
        return 0

    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(html)
    sys.stdout.write("%s\n" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

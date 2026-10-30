"""The slot for a second design provider (PRD SK-09). It is off in P0 and calls nothing.

`second_provider.py review --draft FILE`, where FILE is the round input of the first draft round.

The answer is `state` and `forks`. Each entry of `forks` has the shape of the `fork` field of a round
input item. The P1 protocol fills it: each provider drafts alone, each critiques the other, and they
reconcile; a disagreement that stays becomes one entry (decision 98).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "grill" / "scripts"))

from grill_common import Parser, serve  # noqa: E402

OFF = "off"


def review(argv):
    parser = Parser(add_help=False)
    parser.add_argument("verb", choices=["review"])
    parser.add_argument("--draft", required=True)
    parser.parse_args(argv)
    return {"ok": True, "state": OFF, "forks": []}


if __name__ == "__main__":
    sys.exit(serve(review))

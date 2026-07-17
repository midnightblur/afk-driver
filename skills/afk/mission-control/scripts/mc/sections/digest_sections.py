"""Thin digest-backed sections: flows, entities, decisions, critical-logic,
legend. Each loads its `plan/digests/{name}.json` via mc.digests (schemas +
build contract one-home: the skill's DIGEST-FORMAT.md). Architecture is NOT
here — it merges a live overlay and has its own module.
"""
from __future__ import annotations

from pathlib import Path

from .. import digests


def make_parser(digest_name: str, section_id: str, title: str):
    def parse(spec_dir: Path):
        return digests.load(spec_dir, digest_name, section_id, title)

    parse.__name__ = f"parse_{section_id.replace('-', '_')}"
    return parse


flows = make_parser("flows", "flows", "Flows")
entities = make_parser("entities", "entities", "Entities")
decisions = make_parser("adrs", "decisions", "Decisions")
critical_logic = make_parser("critical-logic", "critical-logic", "Critical logic")
legend = make_parser("legend", "legend", "Legend")

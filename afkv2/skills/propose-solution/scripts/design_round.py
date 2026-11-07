"""Write the page document of one propose-solution session (page format 2; SDD §3 row S-1).

Verbs, run from the repository root:
  build --doc D --session S --ticket K --round-input F [--ticket-file T] [--replace]
  next  --doc D

The grill's round builder writes the document. This script adds what only this skill knows: the
critical aspects in their fixed order, the layers from the top down, the human-locked aspects, the
fork cards, the maps that show all three, the section rules, the 5 blocks of a decision, and the
proposers banner.

An item of the round input may name one of `aspect`, `layer` or `locked`, and may hold a `fork`.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL.parent / "use-lavish" / "scripts"))

import round_document as rd  # noqa: E402
import section_rules  # noqa: E402
from fork_cards import expand_fork  # noqa: E402
from grill_common import Parser, Refusal, read_json, serve  # noqa: E402
from page_links import links_for  # noqa: E402

SKILL_NAME = "propose-solution"
GROUPS = {
    "aspect": {"file": "ASPECTS.md", "row": re.compile(r"^\| \d+ \| `([\w-]+)` \| ([^|]+?) \|", re.M),
               "map": "m-aspects", "title": "Critical aspects", "prefix": "aspect-", "edges": True},
    "layer": {"file": "DRAFT.md", "row": re.compile(r"^\| (L[1-9]) \| ([^|]+?) \|", re.M),
              "map": "m-layers", "title": "Design layers", "prefix": "layer-", "edges": True},
    "locked": {"file": "DRAFT.md", "row": re.compile(r"^\| (HL-[1-9]) \| ([^|]+?) \|", re.M),
               "map": "m-locked", "title": "Human-locked aspects", "prefix": "locked-", "edges": False},
}
ASPECT_KINDS = {"confirm", "debate"}
CRITERION = re.compile(r"^\s*- \[[ xX]\] (AC-\d{3,})\b\s*(.*)$", re.M)
TIP_LIMIT = 1000
PROPOSER_FAILED = "proposer-failed"
# Why only 1 solution proposer drafted, by the reason code of the proposers plan (PRD AC-024).
SOLO_REASONS = {"no-herdr": "herdr is not installed", "outside-herdr": "the session runs outside herdr",
                "no-other-tool": "the other tool is not installed", "bypass-forbidden": "full auto-approval is forbidden",
                PROPOSER_FAILED: "a solution proposer failed before the drafts and critiques were done"}
PROPOSERS_FIELDS = {"count", "tools", "reason"}
PROPOSERS_PHASE = "proposers"
STATE_FAULT = "bad-proposers-state"
STATE_VERSION = 1
DRAFT_GROUPS = ("layer", "locked")
FENCE = ("Each solution proposer ran with full auto-approval in a throwaway worktree. "
         "The worktree fences only the working folder; it is not a sandbox.")


def group_rows(group):
    """The (key, label) rows of one group, in order, from the one file that owns them."""
    spec = GROUPS[group]
    return spec["row"].findall((SKILL / spec["file"]).read_text("utf-8"))


def group_keys(group):
    return [key for key, _ in group_rows(group)]


def node_id(group, key):
    return f"{GROUPS[group]['prefix']}{key.lower()}"


def _reserved_nodes():
    return {node_id(group, key) for group in GROUPS for key in group_keys(group)}


def _tagged(raw):
    """A round-input item with its tag turned into a map node, and its fork turned into a debate card."""
    if not isinstance(raw, dict):
        raise Refusal("bad-item", f"item without an id: {raw!r}")
    raw = dict(raw)
    where = f"item {raw.get('id')}"
    tags = [group for group in GROUPS if group in raw]
    if raw.get("node") in _reserved_nodes() or len(tags) > 1 or (tags and raw.get("node")):
        raise Refusal("bad-item", f"{where}: one of {sorted(GROUPS)} or one node of your own map, not both")
    if "fork" in raw:
        raw = expand_fork(raw)
    elif raw.get("kind") == "debate":
        raise Refusal("not-a-fork", f"{where}: a debate card comes from a `fork` field, so its options stand side by side")
    if not tags:
        if raw.get("kind") == "signoff":
            raise Refusal("signoff-untagged", f"{where}: a sign-off card names its aspect in `locked`")
        return raw
    group = tags[0]
    key = raw.pop(group)
    if key not in group_keys(group):
        raise Refusal("bad-item", f"{where}: {group} {key!r} is not one of {group_keys(group)}")
    raw["node"] = node_id(group, key)
    if group == "aspect":
        if raw.get("kind") not in ASPECT_KINDS:
            raise Refusal("aspect-kind", f"{where}: an aspect question is a `confirm` card or a fork, "
                                         f"so the human answers it; not {raw.get('kind')!r}")
        raw["critical"] = True
    if group == "locked" and raw.get("kind") != "signoff":
        raise Refusal("bad-item", f"{where}: `locked` names the aspect of a `signoff` card")
    return raw


def _alternative_lines(rows):
    """Each `{option, why_lost}` row as the line "option — why it lost", and whether every row holds both fields."""
    rows = rows if isinstance(rows, list) else []
    typed = [row if isinstance(row, dict) else {"option": str(row)} for row in rows]
    lines = [" — ".join(str(row.get(field)).strip() for field in ("option", "why_lost") if str(row.get(field) or "").strip())
             for row in typed]
    whole = bool(rows) and all(isinstance(row.get(field), str) and row[field].strip()
                               for row in typed for field in ("option", "why_lost"))
    return [line for line in lines if line], whole


def _design_decided(raw, known_ids, degraded):
    """A decided card of a design page holds the 5 blocks D-1 to D-5; a card that misses one becomes a confirm card
    with the same fields, listed in `degraded` (SDD §6 I-3, ADR-0004 design)."""
    if raw.get("kind") != "decided":
        return raw
    fields = raw.get("decided") if isinstance(raw.get("decided"), dict) else {}
    lines, typed = _alternative_lines(fields.get("alternatives"))
    shared = {**fields, "alternatives": lines}
    if typed and fields.get("driven_by"):
        return {**raw, "decided": shared}
    blocks, _ = rd._decided_fields(raw.get("id"), shared, known_ids)
    body = copy.deepcopy(raw.get("body"))
    if body:
        body["children"] = [*(body.get("children") or []), *blocks]
    elif blocks:
        body = {**blocks[0], "children": blocks[1:]}
    degraded.append(raw.get("id"))
    return {**{key: value for key, value in raw.items() if key != "decided"}, "kind": "confirm", "body": body}


def _prd(doc_path):
    """The PRD beside the page, which lives in `<spec dir>/pages/`, or None."""
    prd = Path(doc_path).parent.parent / "PRD.md"
    return prd if Path(doc_path).parent.name == "pages" and prd.is_file() else None


def _spec_texts(doc_path):
    """The text of each acceptance criterion of the PRD and of each requirement record, by id; none without a PRD."""
    prd = _prd(doc_path)
    if prd is None:
        return {}
    spec = prd.parent
    texts = {key: value.strip() for key, value in CRITERION.findall(prd.read_text("utf-8"))}
    for record in sorted((spec / "adr" / "requirements").glob("[0-9][0-9][0-9][0-9]-*.md")):
        title = next((line[2:].strip() for line in record.read_text("utf-8").splitlines() if line.startswith("# ")), "")
        texts[f"ADR-{record.name[:4]}"] = title or record.stem
    return texts


def _check_driven_by(doc_path, items, known_ids):
    """Each `driven_by` id of a decided card names an acceptance criterion, a requirement record, another id the PRD
    holds (a catalog id) or a page id. A page with no PRD beside it checks nothing (SDD §3 row S-1)."""
    prd = _prd(doc_path)
    if prd is None:
        return
    texts, prd_text = _spec_texts(doc_path), prd.read_text("utf-8")
    for item in items:
        fields = item.get("decided") if item.get("kind") == "decided" and isinstance(item.get("decided"), dict) else {}
        ids = fields.get("driven_by") if isinstance(fields.get("driven_by"), list) else []
        unknown = [key for key in ids if isinstance(key, str) and key not in texts and key not in known_ids
                   and not re.search(rf"(?<![\w-]){re.escape(key)}(?![\w-])", prd_text)]
        if unknown:
            raise Refusal("driven-by-unknown", f"item {item['id']}: driven_by names {', '.join(unknown)}, which is no "
                                               f"criterion, requirement record or id of the PRD and no page id")


def _driven_by_tips(doc_path, items):
    """1 hover tip per decided card on its Driven by block: the text of each id that is a PRD criterion or a
    requirement record (PRD AC-010)."""
    texts = _spec_texts(doc_path)
    tips = []
    for item in items:
        if item.get("kind") != "decided":
            continue
        fields = item.get("decided") if isinstance(item.get("decided"), dict) else {}
        lines = [f"{key}: {texts[key]}" for key in fields.get("driven_by") or [] if key in texts]
        if lines:
            tips.append({"id": f"{item['id']}-driven-by", "title": "\n".join(lines)[:TIP_LIMIT]})
    return tips


def _merged_tips(doc, round_input, tips):
    """The tips catalog with the driven-by tips of this round. A round's own `tips` replace the stored catalog, but
    the stored driven-by tips of live cards stay, because only this build writes them; a dropped card's tip goes."""
    live = rd._used_ids(doc)
    stored = copy.deepcopy(doc.get("tips") or {})
    kept = [tip for tip in stored.get("ids") or []
            if isinstance(tip, dict) and str(tip.get("id")).endswith("-driven-by") and tip.get("id") in live]
    if "tips" in round_input:
        base = copy.deepcopy(round_input["tips"])
        sent = {tip.get("id") for tip in base.get("ids") or [] if isinstance(tip, dict)}
        base["ids"] = [*(base.get("ids") or []), *(tip for tip in kept if tip["id"] not in sent)]
    else:
        base = stored
        base["ids"] = [tip for tip in stored.get("ids") or []
                       if not str(tip.get("id")).endswith("-driven-by") or tip in kept]
    new = {tip["id"] for tip in tips}
    ids = [tip for tip in base.get("ids") or [] if tip.get("id") not in new] + tips
    return {**base, "ids": ids} if ids else {key: value for key, value in base.items() if key != "ids"}


def proposers_state_path(doc_path):
    """The proposers state file beside the page document."""
    return Path(doc_path).with_suffix(".proposers.json")


def proposers_state(doc_path):
    """The proposers state of the session, or None before the proposers plan wrote it. The shape is in the docstring
    of proposers.py, its writer; this reader checks the fields it acts on: version, count, proposers and cleaned."""
    path = proposers_state_path(doc_path)
    if not path.exists():
        return None
    try:
        state = read_json(path)
    except Refusal as refusal:
        raise Refusal(STATE_FAULT, f"{path}: {refusal.reason}") from None
    entries = state.get("proposers", []) if isinstance(state, dict) else None
    if (not isinstance(state, dict) or state.get("version") != STATE_VERSION or isinstance(state.get("count"), bool)
            or state.get("count") not in (1, 2) or not isinstance(entries, list)
            or not all(isinstance(entry, dict) for entry in entries)
            or not isinstance(state.get("cleaned", False), bool)):
        raise Refusal(STATE_FAULT, f"{path} is not a version {STATE_VERSION} proposers state file")
    if state.get("cleaned") and _open_resources(state):
        raise Refusal(STATE_FAULT, f"{path} records cleanup done and still names {', '.join(_open_resources(state))}")
    return state


def _open_resources(state):
    return [str(proposer.get(kind)) for proposer in (state or {}).get("proposers") or [] if isinstance(proposer, dict)
            for kind in ("pane", "worktree") if proposer.get(kind)]


def _proposers_done(state):
    return bool(state) and (state["count"] == 1 or state.get("cleaned") is True)


def _drafted(doc):
    return any(_cards(doc, node_id(group, key)) for group in DRAFT_GROUPS for key in group_keys(group))


def _check_proposers_closed(doc_path, doc, items):
    """A draft round waits while the state file records a pane or a worktree (SDD §6 I-6). The first draft round
    also waits until the state records count 1 or cleanup done, as `next` does (PRD AC-018)."""
    drafting = {node_id(group, key) for group in DRAFT_GROUPS for key in group_keys(group)}
    if not any(item.get("node") in drafting for item in items):
        return
    state = proposers_state(doc_path)
    left = _open_resources(state)
    if left:
        raise Refusal("proposers-open", f"the draft waits until cleanup closes each proposer pane and worktree: "
                                        f"{', '.join(left)}")
    if not _drafted(doc) and not _proposers_done(state):
        raise Refusal("proposers-first", "the draft waits for the proposers phase: run the proposers plan, and "
                                         "cleanup when 2 proposers ran")


def _tool_name(tool):
    return tool[:1].upper() + tool[1:]


def _proposers_banner(proposers):
    """The R-5 banner line: how many solution proposers drafted, or why only 1 did; then the fence statement of
    SDD §5 when a proposer ran (PRD AC-021, AC-024)."""
    where = f"proposers {proposers!r}"
    if not isinstance(proposers, dict) or set(proposers) != PROPOSERS_FIELDS:
        raise Refusal("bad-proposers", f"{where}: one object with {sorted(PROPOSERS_FIELDS)}")
    count, tools, reason = proposers["count"], proposers["tools"], proposers["reason"]
    if count not in (1, 2) or isinstance(count, bool):
        raise Refusal("bad-proposers", f"{where}: count is 1 or 2")
    if (not isinstance(tools, list) or len(tools) != count or len(set(map(str, tools))) != count
            or not all(isinstance(tool, str) and tool.strip() for tool in tools)):
        raise Refusal("bad-proposers", f"{where}: tools names {count} different tools")
    if count == 2:
        if reason is not None:
            raise Refusal("bad-proposers", f"{where}: 2 proposers ran, so reason is null")
        return [f"2 solution proposers drafted the design: {' and '.join(map(_tool_name, tools))}.", FENCE]
    if reason not in SOLO_REASONS:
        raise Refusal("bad-proposers", f"{where}: reason is one of {sorted(SOLO_REASONS)}")
    line = f"1 solution proposer drafted the design alone ({_tool_name(tools[0])}): {SOLO_REASONS[reason]}."
    # A failed proposer ran with full auto-approval, so the fence statement stands (SDD §5).
    return [line, FENCE] if reason == PROPOSER_FAILED else [line]


def _empty():
    return {"maps": [], "rounds": []}


def _view(doc_path, replace=False):
    """The document as the next round will find it."""
    doc = read_json(doc_path) if Path(doc_path).exists() else _empty()
    if replace:
        rd._drop_unanswered_round(doc, doc_path)
    return doc


def _live(doc, item, round_n):
    waiting = item["kind"] in rd.ASKING and item["state"] in ("open", "blocked", "needs_reading")
    return (waiting or rd.signature_missing(item)) and not rd._carried(doc, item, round_n)


def _cards(doc, node):
    return [(rnd["n"], item) for rnd in doc["rounds"] for item in rnd["items"] if item.get("node") == node]


def is_settled(doc, node):
    """True when the node has a card and no card of it still waits."""
    cards = _cards(doc, node)
    return bool(cards) and not any(_live(doc, item, n) for n, item in cards)


def _check_carriers(doc, items):
    """A card that carries a card of an aspect, a layer or a locked aspect stays on that node, so the node stays open."""
    nodes = {item["id"]: item.get("node") for rnd in doc["rounds"] for item in rnd["items"]}
    nodes.update({item["id"]: item.get("node") for item in items})
    reserved = _reserved_nodes()
    for item in items:
        for carried in item.get("carries") or []:
            if nodes.get(carried) in reserved and item.get("node") != nodes[carried]:
                raise Refusal("carry-node", f"item {item['id']} carries {carried}, so it must tag {nodes[carried]} too")


def _check_order(doc, items):
    asked = {node for rnd in doc["rounds"] for node in (item.get("node") for item in rnd["items"])}
    aspects_done = all(is_settled(doc, node_id("aspect", key)) for key in group_keys("aspect"))
    for item in items:
        node = item.get("node")
        for group in ("aspect", "layer"):
            sequence = [node_id(group, key) for key in group_keys(group)]
            if node in sequence:
                missed = [earlier for earlier in sequence[:sequence.index(node)] if earlier not in asked]
                if missed:
                    raise Refusal("out-of-order", f"item {item['id']}: ask {missed[0]} first; the order is fixed")
        drafting = node in {node_id(group, key) for group in ("layer", "locked") for key in group_keys(group)}
        if drafting and not aspects_done:
            raise Refusal("aspects-first", f"item {item['id']}: the draft waits until every critical aspect is settled")
        asked.add(node)


def _node_state(doc, node, items):
    if any(item.get("node") == node for item in items):
        return "focus"
    return "settled" if is_settled(doc, node) else "open"


def _design_maps(doc, items, own_maps):
    reserved = {spec["map"] for spec in GROUPS.values()}
    if own_maps is None:
        own_maps = [chart for chart in doc.get("maps") or [] if chart.get("id") not in reserved]
    elif any(isinstance(chart, dict) and chart.get("id") in reserved for chart in own_maps):
        raise Refusal("bad-round", f"the map ids {sorted(reserved)} belong to this skill")
    maps = []
    for group, spec in GROUPS.items():
        keys = group_keys(group)
        nodes = [{"id": node_id(group, key), "label": label, "state": _node_state(doc, node_id(group, key), items)}
                 for key, label in group_rows(group)]
        props = {"title": spec["title"], "nodes": nodes}
        if spec["edges"]:
            props["edges"] = [{"from": node_id(group, a), "to": node_id(group, b)} for a, b in zip(keys, keys[1:])]
        maps.append({"type": "map", "id": spec["map"], "props": props})
    return [*maps, *own_maps]


def _filled_sections(doc, sent):
    """The sent sections with the links of `section_rules.fill_links`; a stored section whose links change is sent
    too, with a change line. Refuse a broken section rule of the merged list before any write (SDD §6 I-1, I-2)."""
    preview = copy.deepcopy(doc)
    n = max((rnd["n"] for rnd in preview.get("rounds") or []), default=0) + 1
    rd._merge_entries(preview, {"sections": copy.deepcopy(sent)}, n)
    merged = section_rules.fill_links(preview["sections"])
    failures = section_rules.check_sections(merged)
    if failures:
        raise Refusal(failures[0].split(":")[0], "; ".join(failures))
    links = {entry["id"]: entry.get("links") for entry in merged}
    stored = {entry["id"]: entry for entry in doc.get("sections") or []}
    filled = [{**raw, **({"links": links[raw["id"]]} if links[raw["id"]] else {})} for raw in sent]
    sent_ids = {raw["id"] for raw in sent}
    for sid, entry in stored.items():
        if sid not in sent_ids and links[sid] != entry.get("links"):
            added = [link for link in links[sid] if link not in (entry.get("links") or [])]
            filled.append({**{key: value for key, value in entry.items() if key != "changes"}, "links": links[sid],
                           "change": {"cause": "finding", "text": f"The design build linked {', '.join(added)}."}})
    return filled, [entry["id"] for entry in merged]


def build_design_round(doc_path, session, round_input, replace=False, links=None, ticket=None):
    """Check the round against the fixed orders, then let the grill's builder write it; write nothing on a refusal.

    `links` replaces `session.links`, so the page links each ticket, change and commit reference. `ticket`, the
    read ticket, adds the ticket card to round 1 (PRD AC-036)."""
    if not isinstance(round_input, dict) or not isinstance(round_input.get("items", []), list):
        raise Refusal("bad-round", "the round input is one JSON object, and items is a list")
    doc = _view(doc_path, replace)
    items = [_tagged(raw) for raw in round_input.get("items") or []]
    _check_carriers(doc, items)
    _check_order(doc, items)
    _check_proposers_closed(doc_path, doc, items)
    if "tips" in round_input and not isinstance(round_input["tips"], dict):
        raise Refusal("bad-round", f"tips is one object: {round_input['tips']!r}")
    built = copy.deepcopy(round_input)
    if "proposers" in built:
        lines = _proposers_banner(built.pop("proposers"))
        if isinstance(built.get("banner"), dict):
            built["banner"]["settled"] = [*lines, *(built["banner"].get("settled") or [])]
    known = rd._used_ids(doc) | {item.get("id") for item in items}
    _check_driven_by(doc_path, items, known)
    degraded = []
    built["items"] = [_design_decided(item, known, degraded) for item in items]
    tips = _driven_by_tips(doc_path, items)
    if tips or "tips" in round_input or doc.get("tips"):
        built["tips"] = _merged_tips(doc, round_input, tips)
    built["maps"] = _design_maps(doc, items, round_input.get("maps"))
    order = [entry["id"] for entry in doc.get("sections") or []]
    # A version 0 or 1 page refuses sections in the shared builder, unless the round upgrades it.
    takes_sections = "schema" not in doc or rd.is_version_2(doc) or round_input.get("upgrade") is True
    if isinstance(round_input.get("sections"), list) and takes_sections:
        built["sections"], order = _filled_sections(doc, round_input["sections"])
    answer = rd.build_round_document(doc_path, session, built, ticket, replace, links)
    late = [item_id for item_id in answer["degraded"] if item_id not in degraded]
    return {**answer, "degraded": [*degraded, *late], "section_order": order}


def _entries(group, keys):
    labels = dict(group_rows(group))
    return [{"key": key, "label": labels[key]} for key in keys]


def next_step(doc, proposers=None):
    """Which aspects and layers are still to ask or to settle, and so which phase the session is in.

    `proposers` is the proposers state (`proposers_state`). Phase `proposers` stands between the aspects and the
    draft until the state records count 1 or cleanup done; a session with a draft card is past it."""
    unsettled, unasked = {}, {}
    for group in GROUPS:
        keys = group_keys(group)
        unsettled[group] = [key for key in keys if _cards(doc, node_id(group, key))
                            and not is_settled(doc, node_id(group, key))]
        unasked[group] = [key for key in keys if not _cards(doc, node_id(group, key))]
    drafted = _drafted(doc)
    if unasked["aspect"] or unsettled["aspect"]:
        phase = "aspects"
    elif not drafted and not _proposers_done(proposers):
        phase = PROPOSERS_PHASE
    elif unasked["layer"] or unsettled["layer"] or unsettled["locked"]:
        phase = "draft"
    else:
        phase = "write"
    return {"ok": True, "phase": phase,
            "aspects_to_ask": _entries("aspect", unasked["aspect"]), "aspects_open": _entries("aspect", unsettled["aspect"]),
            "layers_to_ask": _entries("layer", unasked["layer"]), "layers_open": _entries("layer", unsettled["layer"]),
            "locked_open": _entries("locked", unsettled["locked"])}


def unfinished(doc):
    """What the design gate refuses: an aspect or a layer with no card, or with a card that still waits."""
    step = next_step(doc)
    failures = [f"aspect {entry['key']} has no card" for entry in step["aspects_to_ask"]]
    failures += [f"aspect {entry['key']} is not settled" for entry in step["aspects_open"]]
    failures += [f"layer {entry['key']} has no card" for entry in step["layers_to_ask"]]
    failures += [f"layer {entry['key']} is not settled" for entry in step["layers_open"]]
    failures += [f"aspect {entry['key']} is not signed" for entry in step["locked_open"]]
    return failures


def main(argv):
    parser = Parser(add_help=False)
    parser.add_argument("verb", choices=["build", "next"])
    parser.add_argument("--doc", required=True)
    parser.add_argument("--session")
    parser.add_argument("--ticket")
    parser.add_argument("--round-input")
    parser.add_argument("--ticket-file")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    if args.verb == "next":
        return next_step(_view(args.doc), proposers_state(args.doc))
    if not (args.session and args.ticket and args.round_input):
        raise Refusal("usage", "build needs --session, --ticket and --round-input", 2)
    feature = Path(args.doc).parent.parent.name
    session = {"id": args.session, "skill": SKILL_NAME, "feature": feature, "ticket": args.ticket}
    earlier = (read_json(args.doc).get("session") or {}).get("links") if Path(args.doc).exists() else None
    ticket = read_json(args.ticket_file) if args.ticket_file else None
    linked = [link.get("key") for link in [*((ticket or {}).get("links") or []),
                                           *((ticket or {}).get("unread_links") or [])]]
    return build_design_round(args.doc, session, read_json(args.round_input), args.replace,
                              links_for([args.ticket, *linked], earlier), ticket)


if __name__ == "__main__":
    sys.exit(serve(main))

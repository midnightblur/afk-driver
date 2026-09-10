"""Round-JSON validation and normalization.

Normative contract: `LAVISH-KIT.md` (plugin root). This module is the
mechanical enforcement of it; that file is the description.

Two failure modes, deliberately different (LAVISH-KIT.md "Two failure modes"):

* A `decided_card` that fails the six-field contract **degrades** to a confirm
  card carrying a banner naming the missing fields. A decided card the human
  cannot audit must never be shown as decided, and dropping it silently hides
  a decision that was taken anyway.
* Every other violation — unknown component, duplicate item id, two current
  rounds, a missing required field on any other component — raises
  `ContractError`, which the CLI turns into a non-zero exit. A half-rendered
  page is worse than a failed render: the markdown fallback is a sanctioned
  outcome, a wrong page is not.

The one exception on the degrade path: a `decided_card` with no `decision` has
nothing to render as anything, so it fails hard like any malformed component.
"""

COMPONENTS = (
    "round_header",
    "decided_card",
    "debate_card",
    "confirm_row",
    "signoff_packet",
    "settled_card",
)

GRADES = ("repo", "spec", "pattern")

# The chain stages, in order, for the process rail. Order is the whole content:
# `done` and `upcoming` are read off the position of the round document's own
# `stage`, so no author states them and none can state them wrongly.
STAGES = ("requirements", "design", "verification", "plan", "execution",
          "smoke", "ship")
ITEM_STATES = ("open", "blocked", "settled")
ROUND_STATES = ("current", "settled")

# Required fields per component. `decided_card` is absent on purpose: its
# contract is the six fields checked by `decided_contract_gaps`, on the degrade
# path rather than the hard-failure one.
REQUIRED = {
    "round_header": ("round", "settled_last_round", "unlocks", "fork", "touches"),
    "debate_card": ("question", "options", "criteria_order", "recommended", "why",
                    "undecided_because"),
    "confirm_row": ("question", "recommended", "why", "cite"),
    "signoff_packet": ("hl_id", "aspect", "tables", "alternatives", "blast_radius", "risks"),
    "settled_card": ("decision", "round", "by", "evidence"),
}

# Fields whose empty value is legal because "none" is an answer: an empty list
# says the round unlocks nothing, which is different from forgetting to say.
# `alternatives` is absent on purpose — it is a list on a decided card and
# prose on a sign-off packet, so each states its own shape.
LIST_FIELDS = ("settled_last_round", "unlocks", "touches", "parked",
               "blast_radius", "risks", "tables")

# Optional fields per component, beside the required ones above. Together with
# `COMMON_ITEM` and the three key sets below these close the document: anything
# else is a typo, and a typo that renders is a field the author thinks they
# wrote. `depends_on` is legal on every card but a decided one, which carries
# its own inside `scope`.
OPTIONAL = {
    "round_header": ("target", "size_note", "parked", "links", "groups",
                     "re_audit"),
    "decided_card": ("context", "provisional_on"),
    "debate_card": ("context", "third_paradigm"),
    "confirm_row": ("context", "alternatives"),
    "signoff_packet": (),
    "settled_card": ("audit",),
}

# `group` is legal on every card: the round groups its cards by the concern
# they settle, and a settled card keeps the group it was decided under.
COMMON_ITEM = ("component", "id", "state", "fresh", "group")

GROUP_KEYS = ("id", "title", "after", "layout")

# How a group lays its members out. `cards` is the default and the only shape
# every component fits; `table` is one row per item, and only a `confirm_row`
# is row-shaped (see `_bind_layout`).
LAYOUTS = ("cards", "table")
TABLE_LAYOUT = "table"
DOCUMENT_KEYS = ("schema", "purpose", "feature", "rounds", "spec_dir", "stage")
ROUND_KEYS = ("round", "state", "items", "header")

# The six decided-card contract fields, in render order (C-1 … C-6).
DECIDED_CONTRACT = ("decision", "alternatives", "evidence", "why_beat", "reverse", "scope")


class ContractError(Exception):
    """A violation the renderer refuses to render around."""


def _reject_unknown(label, mapping, known):
    """Refuse any key outside `known`, naming it.

    A key the renderer does not read is a key the author believes they wrote:
    `contex` renders a card with no explanation and no complaint, and the
    author only finds out in front of the human. Same class as a half-render —
    the failure nobody is told about is the expensive one.
    """
    unknown = sorted(k for k in mapping if k not in known)
    if unknown:
        raise ContractError("%s: unknown field %s (known: %s)"
                            % (label, ", ".join(repr(k) for k in unknown),
                               ", ".join(sorted(known))))


def _empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict)):
        return len(value) == 0
    return False


def decided_contract_gaps(item, known_ids=None):
    """Names of the six contract fields this decided card cannot satisfy.

    Empty list = presentable as decided. Two id checks make the card auditable
    rather than merely filled in: `why_beat.runner_up_id` must name an id in
    `alternatives[]`, and every `scope.depends_on` id must name an item that
    exists in the artifact. A reference to nothing reads as a fact and is not
    one.
    """
    gaps = []
    for field in DECIDED_CONTRACT:
        if _empty(item.get(field)):
            gaps.append(field)
    if "evidence" not in gaps:
        evidence = item["evidence"]
        if (not isinstance(evidence, dict)
                or evidence.get("grade") not in GRADES
                or _empty(evidence.get("cite"))
                or _empty(evidence.get("sentence"))):
            gaps.append("evidence")
    if "why_beat" not in gaps:
        why = item["why_beat"]
        if (not isinstance(why, dict)
                or _empty(why.get("sentence"))
                or _empty(why.get("runner_up_id"))):
            gaps.append("why_beat")
        else:
            alt_ids = {a.get("id") for a in item.get("alternatives") or []
                       if isinstance(a, dict)}
            if why["runner_up_id"] not in alt_ids:
                gaps.append("why_beat")
    if "scope" not in gaps:
        scope = item["scope"]
        if not isinstance(scope, dict) or "depends_on" not in scope:
            gaps.append("scope")
        elif known_ids is not None and _unknown_ids(scope.get("depends_on"), known_ids):
            gaps.append("scope")
    return sorted(set(gaps))


def _unknown_ids(ids, known_ids):
    """Referenced ids that name nothing in the artifact."""
    if not isinstance(ids, list):
        return ["<not a list>"]
    return sorted(str(i) for i in ids if i not in known_ids)


def required_mark(item):
    """Does an unmarked card count as unanswered rather than silently accepted?

    Every answerable card, without exception. Silence is not agreement: a
    decision the human never marked is a decision they never made, whatever
    grade of evidence stands behind it. A card that is checkable in one
    click-through still costs one click to accept, and that click is the whole
    difference between a record of agreement and an assumption of it.
    """
    return item["component"] in ("debate_card", "confirm_row",
                                 "signoff_packet", "decided_card")


def _degrade(item, gaps):
    """Turn an unauditable decided card into a confirm card that says so."""
    if _empty(item.get("decision")):
        raise ContractError(
            "item %r: decided_card has no `decision` — nothing to render as anything"
            % item.get("id"))
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    why = item.get("why_beat") if isinstance(item.get("why_beat"), dict) else {}
    return {
        "component": "confirm_row",
        "id": item["id"],
        "state": item.get("state"),
        "fresh": item.get("fresh"),
        # The group travels with the card. A degrade that dropped it would put
        # the card in no group, and a grouped page renders groups — so the
        # question would vanish at the exact moment it needs asking.
        "group": item.get("group"),
        "question": item["decision"],
        "context": item.get("context"),
        # The degraded card asks the one question its gaps leave standing.
        "recommended": "accept",
        "why": why.get("sentence") or "",
        "cite": evidence.get("cite") or "",
        "alternatives": [a for a in item.get("alternatives") or [] if isinstance(a, dict)],
        "degraded_from": "decided_card",
        "degraded_gaps": gaps,
    }


def _require_fields(component, item, label):
    for field in REQUIRED[component]:
        if field in LIST_FIELDS:
            if item.get(field) is None:
                raise ContractError("%s: required field %r is missing (use [] for none)"
                                    % (label, field))
            if not isinstance(item[field], list):
                raise ContractError("%s: field %r must be a list" % (label, field))
            continue
        if _empty(item.get(field)):
            raise ContractError("%s: required field %r is missing or empty" % (label, field))


def _check_item(item, round_state, seen_ids):
    if not isinstance(item, dict):
        raise ContractError("every item must be a JSON object, got %s" % type(item).__name__)
    component = item.get("component")
    if component not in COMPONENTS:
        raise ContractError("unknown component %r (known: %s)"
                            % (component, ", ".join(COMPONENTS)))
    if component == "round_header":
        raise ContractError("round_header belongs on a round's `header`, not in `items`")
    item_id = item.get("id")
    if not isinstance(item_id, str) or _empty(item_id):
        raise ContractError("component %s has no `id`" % component)
    if item_id in seen_ids:
        raise ContractError("duplicate item id %r — item ids are unique per artifact" % item_id)
    seen_ids.add(item_id)

    state = item.get("state") or ("settled" if round_state == "settled" else "open")
    if state not in ITEM_STATES:
        raise ContractError("item %r: state %r not one of %s"
                            % (item_id, state, ", ".join(ITEM_STATES)))
    if (state == "settled") != (component == "settled_card"):
        raise ContractError(
            "item %r: a settled item is a settled_card and a settled_card is settled — "
            "got component %s in state %s" % (item_id, component, state))
    item["state"] = state
    if item.get("fresh") is None:
        item["fresh"] = round_state == "current" and state != "settled"

    label = "item %r (%s)" % (item_id, component)
    known = set(COMMON_ITEM)
    known.update(REQUIRED.get(component, ()))
    known.update(OPTIONAL.get(component, ()))
    if component != "decided_card":
        known.add("depends_on")
    else:
        known.update(DECIDED_CONTRACT)
    _reject_unknown(label, item, known)

    if component == "decided_card":
        # The six-field verdict waits for `_resolve_ids`: `scope.depends_on`
        # may name an item this pass has not reached yet.
        return item

    _require_fields(component, item, label)
    if component == "debate_card":
        options = item["options"]
        option_ids = [o.get("id") for o in options if isinstance(o, dict)]
        if len(option_ids) != len(options):
            raise ContractError("%s: every option is an object with an `id`" % label)
        if len(option_ids) < 2:
            raise ContractError("%s: a debate needs >=2 live alternatives" % label)
        if any(_empty(o) for o in option_ids) or len(set(option_ids)) != len(option_ids):
            raise ContractError("%s: option ids must be present and unique" % label)
        if item["recommended"] not in option_ids:
            raise ContractError("%s: recommended %r names no option"
                                % (label, item["recommended"]))
    return item


def _resolve_ids(item, known_ids):
    """Second pass: every id a card points at names something in the artifact.

    Runs once the whole id set is known, so a card may point forward — at a
    later item in its own round, or at a later round.
    """
    component = item["component"]
    if component == "decided_card":
        gaps = decided_contract_gaps(item, known_ids)
        return _degrade(item, gaps) if gaps else item
    missing = _unknown_ids(item.get("depends_on"), known_ids) if item.get("depends_on") else []
    if missing:
        raise ContractError("item %r: `depends_on` names %s, which no item in this artifact "
                            "carries" % (item["id"], ", ".join(missing)))
    return item


def _check_groups(groups, number):
    """Declared groups, in an order that is already a dependency order.

    The list order is the render order, so a group listed before one it comes
    `after` would put a dependent above its parent — navigability rule 2 read
    backwards. Rejecting that here means the renderer never has to sort, and
    the author sees the cycle instead of a page that quietly reorders their
    round.
    """
    if not isinstance(groups, list) or not groups:
        raise ContractError("round %d header: `groups`, when stated, is a non-empty list"
                            % number)
    seen = []
    for group in groups:
        if not isinstance(group, dict):
            raise ContractError("round %d header: every group is a JSON object" % number)
        label = "round %d group %r" % (number, group.get("id"))
        _reject_unknown(label, group, set(GROUP_KEYS))
        for field in ("id", "title"):
            if _empty(group.get(field)):
                raise ContractError("%s: required field %r is missing or empty"
                                    % (label, field))
        gid = group["id"]
        if gid in seen:
            raise ContractError("%s: duplicate group id" % label)
        layout = group.get("layout")
        if layout is not None and layout not in LAYOUTS:
            raise ContractError("%s: `layout` %r is not one of %s"
                                % (label, layout, ", ".join(LAYOUTS)))
        after = group.get("after") or []
        if not isinstance(after, list):
            raise ContractError("%s: `after` must be a list of group ids" % label)
        for parent in after:
            if parent == gid:
                raise ContractError("%s: a group cannot come after itself" % label)
            if parent not in seen:
                raise ContractError(
                    "%s: comes after %r, which is not declared before it — list groups in "
                    "dependency order, parents first" % (label, parent))
        seen.append(gid)
    return seen


def _bind_groups(items, groups, number):
    """Every answerable card in a grouped round names one of the groups.

    Half a round grouped is worse than none: the ungrouped cards land in no
    section, so the group count on the header stops describing the page. A
    round either groups its live cards or declares no groups at all — and a
    `group` on a card in an ungrouped round names nothing, which is the same
    class of defect as any other reference to nothing.
    """
    live = [i for i in items if i.get("state") != "settled"]
    if groups is None:
        stray = [i["id"] for i in live if i.get("group") is not None]
        if stray:
            raise ContractError(
                "round %d: %s carry a `group`, but the header declares none — declare the "
                "groups or drop the field" % (number, ", ".join(repr(i) for i in stray)))
        return
    known = {g["id"] for g in groups}
    for item in live:
        if item.get("group") is None:
            raise ContractError(
                "round %d: item %r names no `group`, and this round declares %d of them"
                % (number, item["id"], len(known)))
        if item["group"] not in known:
            raise ContractError(
                "round %d: item %r is in group %r, which the header does not declare "
                "(declared: %s)" % (number, item["id"], item["group"],
                                    ", ".join(sorted(known))))


def group_layout(group):
    """How this group lays its members out. Absent reads as `cards`.

    Read, never written: normalizing the field onto the author's own group
    object would edit the document the caller handed in.
    """
    return group.get("layout") or "cards"


def _bind_layout(items, groups, number):
    """A table group holds only `confirm_row` members.

    A row is one question needing exactly one mark, which is the whole of a
    confirm card. Every other component carries more than a row can hold: a
    `decided_card` has a six-field contract plus a narrative body, so forcing
    it into a cell either truncates the record or makes the row unreadable —
    and the record is the reason the card is allowed to exist. A `debate_card`
    is a criteria grid, and a `signoff_packet` is tables; neither is row-shaped
    either.

    Runs after the degrade pass, so a `decided_card` that lost its contract has
    already become a `confirm_row` and passes here — the same question in a
    weaker form, which is exactly what a row asks.
    """
    if not groups:
        return
    tables = {g["id"] for g in groups if group_layout(g) == TABLE_LAYOUT}
    if not tables:
        return
    for item in items:
        if item.get("state") == "settled" or item.get("group") not in tables:
            continue
        if item["component"] != "confirm_row":
            raise ContractError(
                "round %d: item %r is a %s in group %r, which lays out as a table — a "
                "table row holds one question and one mark, so only confirm_row fits"
                % (number, item["id"], item["component"], item["group"]))


def _bind_re_audit(items, ids, number):
    """Every re-audited id is a live card in this round.

    The strip exists to say a decision went unmarked and is therefore not
    applied. That claim is only true while the card is on the page to be
    marked: an id naming a settled card would say the opposite of the record,
    and an id naming nothing would ask the human to re-audit a card they
    cannot reach.
    """
    if ids is None:
        return
    if not isinstance(ids, list):
        raise ContractError("round %d header: `re_audit` must be a list of item ids"
                            % number)
    live = {i["id"] for i in items if i.get("state") != "settled"}
    settled = {i["id"] for i in items if i.get("state") == "settled"}
    for item_id in ids:
        if item_id in live:
            continue
        if item_id in settled:
            raise ContractError(
                "round %d: `re_audit` names %r, which is settled in this round — a card "
                "that carries a mark is not unanswered" % (number, item_id))
        raise ContractError(
            "round %d: `re_audit` names %r, which this round does not present — an "
            "unmarked card is re-asked, not just reported" % (number, item_id))


def independent_groups(groups):
    """Group ids nothing gates: the ones the human may take in any order.

    Rule 1 asks the header to say which groups are independent of each other.
    That is derivable — a group with an empty `after` waits for nothing — so no
    author writes it and no author gets it wrong.
    """
    return [g["id"] for g in groups if not (g.get("after") or [])]


def _check_header(header, number):
    if not isinstance(header, dict):
        raise ContractError("round %d: the current round needs a `header` (round_header)"
                            % number)
    # `component: round_header` is legal here and does nothing: the header is
    # addressed by position, but the contract calls it a component, so an author
    # writes the tag. Legal and wrong-valued are different — a tag naming another
    # component means the author put the wrong object here.
    _reject_unknown("round %d header" % number, header,
                    set(REQUIRED["round_header"]) | set(OPTIONAL["round_header"])
                    | {"component"})
    if header.get("component") not in (None, "round_header"):
        raise ContractError("round %d header: `component` says %r; a round's header is a "
                            "round_header" % (number, header.get("component")))
    _require_fields("round_header", header, "round %d header" % number)
    if header.get("groups") is not None:
        _check_groups(header["groups"], number)
    if header.get("round") != number:
        raise ContractError("round %d header says round %r" % (number, header.get("round")))
    target = header.get("target")
    if target is not None and (not isinstance(target, int) or isinstance(target, bool)
                               or target < 1):
        raise ContractError("round %d header: `target`, when stated, is a positive integer"
                            % number)


def load(doc):
    """Validate and normalize a round document; return it ready to render."""
    if not isinstance(doc, dict):
        raise ContractError("the round document must be a JSON object")
    if doc.get("schema") != 1:
        raise ContractError("unsupported `schema` %r — this renderer speaks schema 1"
                            % doc.get("schema"))
    _reject_unknown("document", doc, DOCUMENT_KEYS)
    for field in ("feature", "purpose", "rounds"):
        if _empty(doc.get(field)):
            raise ContractError("document: required field %r is missing or empty" % field)
    stage = doc.get("stage")
    if stage is not None and stage not in STAGES:
        raise ContractError("document: `stage` %r is not a chain stage (%s)"
                            % (stage, ", ".join(STAGES)))
    rounds = doc["rounds"]
    if not isinstance(rounds, list):
        raise ContractError("document: `rounds` must be a list")
    current = [r for r in rounds if isinstance(r, dict) and r.get("state") == "current"]
    if len(current) != 1:
        raise ContractError("exactly one round carries state `current`, found %d" % len(current))

    seen_ids = set()
    seen_numbers = set()
    normalized = []
    for rnd in rounds:
        if not isinstance(rnd, dict):
            raise ContractError("every round must be a JSON object")
        _reject_unknown("round %r" % rnd.get("round"), rnd, ROUND_KEYS)
        state = rnd.get("state")
        if state not in ROUND_STATES:
            raise ContractError("round state %r not one of %s"
                                % (state, ", ".join(ROUND_STATES)))
        number = rnd.get("round")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise ContractError("round `round` must be a positive integer, got %r" % number)
        if number in seen_numbers:
            raise ContractError("duplicate round number %d" % number)
        seen_numbers.add(number)
        round_id = "R-%d" % number
        if round_id in seen_ids:
            raise ContractError("round id %s collides with an item id" % round_id)
        seen_ids.add(round_id)

        header = rnd.get("header")
        if state == "current":
            _check_header(header, number)

        items = rnd.get("items")
        if items is None:
            items = []
        if not isinstance(items, list):
            raise ContractError("round %d: `items` must be a list" % number)
        checked = [_check_item(dict(i) if isinstance(i, dict) else i,
                               state, seen_ids)
                   for i in items]
        if state == "current":
            _bind_groups(checked, header.get("groups"), number)
            _bind_re_audit(checked, header.get("re_audit"), number)
        normalized.append({"round": number, "id": round_id, "state": state,
                           "header": header, "items": checked})

    for rnd in normalized:
        rnd["items"] = [_resolve_ids(i, seen_ids) for i in rnd["items"]]
        # Layout membership waits for the degrade pass above: a decided card
        # that fails its contract is a confirm_row by the time it is placed.
        if rnd["state"] == "current":
            _bind_layout(rnd["items"], (rnd["header"] or {}).get("groups"),
                         rnd["round"])

    normalized.sort(key=lambda r: r["round"])
    out = dict(doc)
    out["rounds"] = normalized
    return out

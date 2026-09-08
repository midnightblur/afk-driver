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

GRADES = ("repo", "spec")
ITEM_STATES = ("open", "blocked", "settled")
ROUND_STATES = ("current", "settled")

# Required fields per component. `decided_card` is absent on purpose: its
# contract is the six fields checked by `decided_contract_gaps`, on the degrade
# path rather than the hard-failure one.
REQUIRED = {
    "round_header": ("round", "settled_last_round", "unlocks", "fork", "touches"),
    "debate_card": ("question", "options", "criteria_order", "recommended", "why"),
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
    "round_header": ("target", "size_note", "parked", "links"),
    "decided_card": ("context", "provisional_on"),
    "debate_card": ("context", "third_paradigm"),
    "confirm_row": ("context", "alternatives"),
    "signoff_packet": (),
    "settled_card": ("audit",),
}

COMMON_ITEM = ("component", "id", "state", "fresh")
DOCUMENT_KEYS = ("schema", "purpose", "feature", "rounds", "spec_dir")
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
        normalized.append({"round": number, "id": round_id, "state": state,
                           "header": header, "items": checked})

    for rnd in normalized:
        rnd["items"] = [_resolve_ids(i, seen_ids) for i in rnd["items"]]

    normalized.sort(key=lambda r: r["round"])
    out = dict(doc)
    out["rounds"] = normalized
    return out

#!/usr/bin/env python3
"""Deterministic plan validator — the mechanical subset of
skills/afk/to-subtasks/VALIDATION.md. This docstring is the canonical doc and
the owning home of every rule below; VALIDATION.md points here.

Usage: python3 validate_plan.py <plan-dir>        (Windows: py -3 validate_plan.py <plan-dir>)

Input: a plan/ directory — PLAN.md + rank-ordered NNNN-slug.md subtask
contracts (grammar: SUBTASK-CONTRACT.md). A sibling ../VERIFICATION-PLAN.md,
when present, drives the (g) parity checks. Trial greps resolve `## Produces`
file paths against the enclosing repo root (nearest ancestor with .git);
without one they are skipped.

Checks + rule ids (one finding line per hit: `{file}: {RULE}: {detail}`):

(a) Contract graph — every `## Consumes` line `- {PRODUCER-ID} {file}#{anchor}`:
  A-UNKNOWN-PRODUCER  producer id is no subtask in this plan (orphan consumer)
  A-FORWARD           producer rank >= consumer rank (forward/circular ref)
  A-NOT-PRODUCED      {file}#{anchor} absent from the producer's `## Produces`
  A-COLLISION         same {file}#{anchor} produced by >1 subtask
  A-MAT-DISAGREE      `[materialized]` on producer bullet XOR consumer line

(b) Anchor quality — every `## Produces` `{grep-anchor}`:
  B-GENERIC           anchor is a forbidden generic token; the list's one home:
                      class interface void function def method struct enum type record
  B-SHORT             anchor shorter than 12 chars
  B-AMBIGUOUS         file exists and anchor greps >=2 times (would fail-open)
  B-MAT-UNRESOLVED    `[materialized]` bullet whose file is missing or whose
                      anchor doesn't grep exactly once (stub absent/ambiguous).
                      The stub module's test-compile stays with the emitter.
  SYNTAX              bullet doesn't parse as `{file}#{anchor} — {contract}`

(e) Tier mandates — every subtask's `## Verification` table:
  E-STATIC            no `static` row
  E-TIER-E2E          Scope matches `-ui/` but no `e2e/browser` row
  E-TIER-API          Scope matches `controller` but no `api` row
  E-TIER-INTEGRATION  Scope matches `-entities/` or jms|listener|messaging
                      but no `integration` row
  (This table is the Scope-glob -> mandated-tier mapping's one home. Command
  runnability and runtime-effect Acceptance coverage stay with the emitter.)

(g) Gate shape — PLAN.md + sibling VERIFICATION-PLAN.md:
  G-NO-GATE           neither `## Feature smoke gate` nor `... (minimal)` section
  G-MINIMAL-WITH-PLAN VERIFICATION-PLAN.md exists but only the minimal gate does
  G-FULL-WITHOUT-PLAN full gate section with no VERIFICATION-PLAN.md
  G-PHANTOM-BUILD     NNNN-smoke-* subtask its modality's scenarios don't warrant
  G-BUILD-MISSING     a modality has scenarios but no NNNN-smoke-{e2e|api} subtask
  G-BLOCKEDBY         a smoke build subtask's `## Blocked by` misses an
                      implementation subtask (all except smoke-* and sync-harness)
  G-PARITY-UI/API     gate-table row count per modality != VERIFICATION-PLAN.md
                      scenario count (deferred API placeholder counts 0)

(h) Review policy — PLAN.md header + optional `## Review` contract sections:
  H-POLICY            PLAN.md `> Review policy:` value is neither lean nor full
  H-POLICY-VALUE      a contract `policy:` value is neither lean nor full
  H-OPT-IN-UNKNOWN    an `opt-in:` name is outside the deferrable-concern set
                      (set + semantics: lockstep copy of
                      skills/afk/review/SKILL.md "Gate policy")
  H-REVIEW-LINE       a `## Review` line is neither `policy: …` nor `opt-in: …`

Exit: 0 clean · 1 findings · 2 parse error (plan dir / PLAN.md / subtask file unreadable).
Checks (c) acceptance citations, (d) seam coverage, (f) scope sanity are
LLM judgment — deliberately not here (VALIDATION.md keeps them).
"""
import os
import re
import sys

FORBIDDEN_TOKENS = {"class", "interface", "void", "function", "def", "method",
                    "struct", "enum", "type", "record"}
MIN_ANCHOR_LEN = 12
# Scope-glob -> mandated tier (tier matched by prefix so `e2e/browser` == `e2e`).
TIER_MANDATES = [
    (re.compile(r"-ui(/|$)", re.I), "e2e", "E-TIER-E2E"),
    (re.compile(r"controller", re.I), "api", "E-TIER-API"),
    (re.compile(r"-entities(/|$)", re.I), "integration", "E-TIER-INTEGRATION"),
    (re.compile(r"jms|listener|messaging", re.I), "integration", "E-TIER-INTEGRATION"),
]
POLICY_TOKENS = {"lean", "full"}
# Deferrable concerns: lockstep copy — owned by skills/afk/review/SKILL.md "Gate policy".
DEFERRABLE = {"code-quality", "claude-md-compliance", "design-quality",
              "resilience", "logic-correctness"}
SUBTASK_RE = re.compile(r"^(\d{4})-([a-z0-9][a-z0-9-]*)\.md$")
ID_RE = re.compile(r"\b\d{4}-[a-z0-9][a-z0-9-]*\b")
EMDASH = "—"


def die(msg):
    print(f"validate_plan: parse error: {msg}", file=sys.stderr)
    sys.exit(2)


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        die(f"cannot read {path}: {e}")


def sections(text):
    """Map '## Heading' (comment-stripped) -> body text. Last wins on dupes."""
    out, name, buf = {}, None, []
    for line in text.splitlines():
        if line.startswith("## "):
            if name is not None:
                out[name] = "\n".join(buf)
            name = re.sub(r"<!--.*?(-->|$)", "", line[3:]).strip()
            buf = []
        elif name is not None:
            buf.append(line)
    if name is not None:
        out[name] = "\n".join(buf)
    return out


def bullets(body):
    return [ln.strip()[2:].strip() for ln in (body or "").splitlines()
            if ln.strip().startswith("- ")]


def split_anchor(ref):
    """'{file}#{anchor} [— contract]' -> (file, anchor) or None."""
    ref = ref.split(f" {EMDASH} ")[0].strip()
    if "#" not in ref:
        return None
    path, anchor = ref.split("#", 1)
    path, anchor = path.strip(), anchor.strip()
    return (path, anchor) if path and anchor else None


def strip_marker(line):
    if line.endswith("[materialized]"):
        return line[: -len("[materialized]")].strip(), True
    return line, False


def table_rows(body):
    """First markdown table in body -> (header_cells, [row_cells, ...])."""
    lines = [ln.strip() for ln in (body or "").splitlines()]
    rows, header = [], None
    for ln in lines:
        if ln.startswith("|"):
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if header is None:
                header = cells
            elif all(re.fullmatch(r":?-+:?", c) for c in cells if c):
                continue
            else:
                rows.append(cells)
        elif header is not None:
            break
    return header or [], rows


def repo_root(start):
    cur = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        nxt = os.path.dirname(cur)
        if nxt == cur:
            return None
        cur = nxt


def main():
    if len(sys.argv) != 2:
        die("usage: validate_plan.py <plan-dir>")
    plan_dir = os.path.abspath(sys.argv[1])
    if not os.path.isdir(plan_dir):
        die(f"not a directory: {plan_dir}")
    plan_md = os.path.join(plan_dir, "PLAN.md")
    if not os.path.isfile(plan_md):
        die(f"missing PLAN.md in {plan_dir}")

    findings = []

    def flag(fname, rule, msg):
        findings.append(f"{fname}: {rule}: {msg}")

    # ---- load subtasks in rank order -------------------------------------
    names = sorted(n for n in os.listdir(plan_dir) if SUBTASK_RE.match(n))
    subtasks = []  # (id, rank, sections, fname)
    for n in names:
        m = SUBTASK_RE.match(n)
        subtasks.append((n[:-3], int(m.group(1)), sections(read(os.path.join(plan_dir, n))), n))
    by_id = {sid: (rank, secs, fname) for sid, rank, secs, fname in subtasks}
    root = repo_root(plan_dir)

    # ---- (b) anchors + produces index ------------------------------------
    produced = {}  # (file, anchor) -> [(subtask-id, materialized)]
    for sid, rank, secs, fname in subtasks:
        for raw in bullets(secs.get("Produces")):
            line, mat = strip_marker(raw)
            ref = split_anchor(line)
            if ref is None:
                flag(fname, "SYNTAX", f"unparseable ## Produces bullet: {raw!r}")
                continue
            path, anchor = ref
            produced.setdefault(ref, []).append((sid, mat))
            if anchor.lower() in FORBIDDEN_TOKENS:
                flag(fname, "B-GENERIC", f"anchor {anchor!r} is a forbidden generic token")
            if len(anchor) < MIN_ANCHOR_LEN:
                flag(fname, "B-SHORT", f"anchor {anchor!r} shorter than {MIN_ANCHOR_LEN} chars")
            if root:
                target = os.path.join(root, *path.split("/"))
                exists = os.path.isfile(target)
                count = read(target).count(anchor) if exists else 0
                if mat and count != 1:
                    flag(fname, "B-MAT-UNRESOLVED",
                         f"[materialized] anchor {anchor!r} greps {count}x in {path}"
                         + ("" if exists else " (file missing)"))
                elif exists and count >= 2:
                    flag(fname, "B-AMBIGUOUS", f"anchor {anchor!r} greps {count}x in {path}")

    for (path, anchor), owners in produced.items():
        if len({sid for sid, _ in owners}) > 1:
            flag("PLAN.md", "A-COLLISION",
                 f"{path}#{anchor} produced by {', '.join(sid for sid, _ in owners)}")

    # ---- (a) contract graph ----------------------------------------------
    for sid, rank, secs, fname in subtasks:
        for raw in bullets(secs.get("Consumes")):
            line, mat = strip_marker(raw)
            m = re.match(r"(\d{4}-[a-z0-9][a-z0-9-]*)\s+(.*)", line)
            ref = split_anchor(m.group(2)) if m else None
            if not m or ref is None:
                flag(fname, "SYNTAX", f"unparseable ## Consumes line: {raw!r}")
                continue
            pid = m.group(1)
            if pid not in by_id:
                flag(fname, "A-UNKNOWN-PRODUCER", f"consumes from {pid}, not a subtask in this plan")
                continue
            if by_id[pid][0] >= rank:
                flag(fname, "A-FORWARD", f"consumes from {pid}, not earlier in rank order")
            owners = produced.get(ref, [])
            if not any(osid == pid for osid, _ in owners):
                flag(fname, "A-NOT-PRODUCED", f"{ref[0]}#{ref[1]} not in {pid}'s ## Produces")
            elif any(osid == pid and omat != mat for osid, omat in owners):
                flag(fname, "A-MAT-DISAGREE",
                     f"[materialized] disagrees with {pid}'s bullet for {ref[0]}#{ref[1]}")

    # ---- (e) tier mandates ------------------------------------------------
    for sid, rank, secs, fname in subtasks:
        _, rows = table_rows(secs.get("Verification"))
        tiers = {r[0].strip("` ").lower() for r in rows if r and r[0].strip("` ")}
        if not any(t.startswith("static") for t in tiers):
            flag(fname, "E-STATIC", "## Verification has no static row")
        scope = [ln.split(" #")[0].strip() for ln in bullets(secs.get("Scope"))]
        for pattern, tier, rule in TIER_MANDATES:
            hits = [g for g in scope if pattern.search(g)]
            if hits and not any(t.startswith(tier) for t in tiers):
                flag(fname, rule, f"Scope {hits[0]!r} mandates a {tier} row; none declared")

    # ---- (g) gate shape ---------------------------------------------------
    plan_text = read(plan_md)
    plan_secs = sections(plan_text)
    full = next((v for k, v in plan_secs.items()
                 if k.startswith("Feature smoke gate") and "(minimal)" not in k), None)
    minimal = next((v for k, v in plan_secs.items()
                    if k.startswith("Feature smoke gate (minimal)")), None)
    vp_path = os.path.join(os.path.dirname(plan_dir), "VERIFICATION-PLAN.md")
    vp = read(vp_path) if os.path.isfile(vp_path) else None

    if full is None and minimal is None:
        flag("PLAN.md", "G-NO-GATE", "neither smoke gate section present — a plan never ships gate-less")

    smoke_ids = {"e2e": [s[0] for s in subtasks if s[0].endswith("-smoke-e2e")],
                 "api": [s[0] for s in subtasks if s[0].endswith("-smoke-api")]}

    if vp is None:
        if full is not None:
            flag("PLAN.md", "G-FULL-WITHOUT-PLAN",
                 "full gate section but no sibling VERIFICATION-PLAN.md")
        for mod in ("e2e", "api"):
            for sid in smoke_ids[mod]:
                flag(f"{sid}.md", "G-PHANTOM-BUILD", "build subtask without a VERIFICATION-PLAN.md")
    else:
        vp_secs = sections(vp)
        ui_rows = len(table_rows(vp_secs.get("UI Journeys"))[1])
        api_body = vp_secs.get("API Scenarios")
        deferred = any(ln.strip().startswith(">") and "Deferred" in ln
                       for ln in (api_body or "").splitlines())
        api_rows = 0 if (api_body is None or deferred) else len(table_rows(api_body)[1])

        if full is None:
            flag("PLAN.md", "G-MINIMAL-WITH-PLAN",
                 "VERIFICATION-PLAN.md exists but PLAN.md carries only the minimal gate")
        else:
            header, rows = table_rows(full)
            lower = [h.lower() for h in header]
            mcol = lower.index("modality") if "modality" in lower else None
            if mcol is None:
                flag("PLAN.md", "G-PARITY-UI", "gate table has no Modality column")
            else:
                gate_ui = sum(1 for r in rows if len(r) > mcol and r[mcol] == "ui-e2e")
                gate_api = sum(1 for r in rows if len(r) > mcol and r[mcol] == "api")
                if gate_ui != ui_rows:
                    flag("PLAN.md", "G-PARITY-UI",
                         f"gate has {gate_ui} ui-e2e rows; VERIFICATION-PLAN.md has {ui_rows} UI journeys")
                if gate_api != api_rows:
                    flag("PLAN.md", "G-PARITY-API",
                         f"gate has {gate_api} api rows; VERIFICATION-PLAN.md has {api_rows} API scenarios")

        for mod, count in (("e2e", ui_rows), ("api", api_rows)):
            if count > 0 and not smoke_ids[mod]:
                flag("PLAN.md", "G-BUILD-MISSING",
                     f"VERIFICATION-PLAN.md has {mod} scenarios but no NNNN-smoke-{mod} subtask")
            if count == 0:
                for sid in smoke_ids[mod]:
                    flag(f"{sid}.md", "G-PHANTOM-BUILD",
                         f"NNNN-smoke-{mod} subtask but no {mod} scenarios in VERIFICATION-PLAN.md")

        impl_ids = {s[0] for s in subtasks
                    if not (s[0].endswith("-smoke-e2e") or s[0].endswith("-smoke-api")
                            or s[0].endswith("-sync-harness"))}
        for sid in smoke_ids["e2e"] + smoke_ids["api"]:
            blocked = set(ID_RE.findall(by_id[sid][1].get("Blocked by") or ""))
            missing = sorted(impl_ids - blocked)
            if missing:
                flag(f"{sid}.md", "G-BLOCKEDBY",
                     f"## Blocked by misses implementation subtask(s): {', '.join(missing)}")

    # ---- (h) review policy -------------------------------------------------
    m = re.search(r"^>\s*Review policy:\s*([^\s<]+)", plan_text, re.M)
    if m and m.group(1).lower() not in POLICY_TOKENS:
        flag("PLAN.md", "H-POLICY", f"Review policy {m.group(1)!r} is neither lean nor full")
    for sid, rank, secs, fname in subtasks:
        for ln in (secs.get("Review") or "").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            key, _, val = ln.partition(":")
            key, val = key.strip().lower(), val.split(f" {EMDASH} ")[0].strip()
            if key == "policy":
                if val.lower() not in POLICY_TOKENS:
                    flag(fname, "H-POLICY-VALUE", f"policy {val!r} is neither lean nor full")
            elif key == "opt-in":
                for name in [n.strip() for n in val.split(",") if n.strip()]:
                    if name not in DEFERRABLE:
                        flag(fname, "H-OPT-IN-UNKNOWN",
                             f"opt-in {name!r} is not a deferrable concern")
            else:
                flag(fname, "H-REVIEW-LINE", f"unparseable ## Review line: {ln!r}")

    # ---- report -----------------------------------------------------------
    for line in findings:
        print(line)
    print(f"validate_plan: {'clean' if not findings else str(len(findings)) + ' finding(s)'}"
          f" — {len(subtasks)} subtask(s) in {plan_dir}")
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()

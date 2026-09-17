# Grill log — research-enhancement

## Solution grill

Scope of this grill (orchestrator ruling, 2026-09-15): human-locked sign-offs only; every other layer is settled from `MERGED-PLAN.md` and the requirement ADRs. No `/afk:investigate` ledger was run; premises rest on afk-reader line anchors against origin/main d8ca9b4.

- Locked: L1 inherited — one committed plugin tree for every harness; subprocess dispatch is foreground, no daemon (gap acknowledged: no INV ledger; anchors PROVIDERS.md:5,23-24)
- Locked: L2 two skills `/afk:research`, `/afk:consult`; one dispatcher script; provider member verbs in `hooks/lib/providers/<name>.sh`; run-level exit codes reuse the adapter answer shape (gap acknowledged: anchors ADAPTERS.md:29-34, claude.sh:3-23, codex.sh:3-25)
- Locked: L3 files under the spec folder only; raw streams in scratch with expiry; no database; schema field `1` on every JSON (gap acknowledged: PRD catalog C4)
- Locked: L4 subscription-only auth gate; allowlisted child environment; staged-evidence egress; `no_training` and `credits` declarations; budgets in turns plus wall-clock deadline (gap acknowledged: ADR-0002, 0003, 0005)
- Locked: L5 research report, participant job, consultation run and judge reservation as the four stateful objects; invariants I-1..I-8 with one guardian each (gap acknowledged: PRD AC-012..AC-017)
- Locked: L6 one independent round then one challenge round; dispatcher writes `state.json` atomically; resume is read-only jobs only (gap acknowledged: ADR-0004)
- Locked: L7 modules per PRD Implementation Decisions table; callers point at the utility, the utility never names a caller (gap acknowledged: CLAUDE.md downstream-blind law)
- Locked: L8 dispatcher as one deterministic runner with failure classes FC-1..FC-12; judge as a fresh reserved instance per the review verify-pass precedent (gap acknowledged: skills/afk/review/SKILL.md:144-146)
- Locked: L9 every seam row `extends`, none `reworked`; rows listed in the HL-6 packet (gap acknowledged: anchors verified by afk-reader, no INV ledger)

Round 1 page: `GRILL-SOLUTION-ROUND.html` (source `GRILL-SOLUTION-ROUND.json`), sent 2026-09-15 through the orchestrator relay. Answers received 2026-09-15 verbatim from the page form via the relay: `dc-advisory accept`, `dc-no-extensions accept`, `hl-1 sign`, `hl-2 sign`, `hl-3 sign`, `hl-4 sign`, `hl-5 sign`, `hl-6 sign`, `cf-retain-raw accept`, `cf-deadline m45`. No round 2 needed.

- HL-1 Persistence (spec-folder files, JSON records) → signed 2026-09-15 "hl-1 sign" — covers §4: research/consult file set, evidence.json, result.json, state.json field tables, retention, raw-stream scratch rule
- HL-2 Callable surfaces (skills, dispatcher commands, provider verbs) → signed 2026-09-15 "hl-2 sign" — covers §3: /afk:research, /afk:consult, dispatch_harness run/resume/probe, provider member verbs, existing-caller verdicts (all compatible)
- HL-3 Authorization and data scoping → signed 2026-09-15 "hl-3 sign" — covers §5: actor matrix with both-side enforcement, staging directory, allowed/denied paths, env allowlist, no_training declaration
- HL-4 Lifecycle and invariants → signed 2026-09-15 "hl-4 sign" — covers §6: research/job/run/judge state sets, invariants I-1..I-8 with guardians
- HL-5 Irreversible and outward side effects → signed 2026-09-15 "hl-5 sign" — covers §7: effects E-1..E-6 (staged evidence egress, sanitized queries, subscription draw, raw-stream expiry, process kill, CLAUDE.md priority write)
- HL-6 Change to existing behaviour (seam rows) → signed 2026-09-15 "hl-6 sign" — covers §14: every listed seam row `extends`, none `reworked`; premises on reader anchors, ledger gap acknowledged (user made no objection; /afk:investigate runs on the seams before /afk:to-subtasks)

- Settled: consultation is advisory, never changes a gate verdict or a human decision (ADR-0007) · decided-by agent R-1 · accepted 2026-09-15 · spec: ADR-0007 cites MERGED-PLAN A4 (:26), A7 (:29), D2 (:49) · reverse: if two pilot features show every supported disposition confirmed by the gate, let it pre-fill the finding list, never the verdict
- Settled: no new review concern, no new evidence grades, no counter-search route (ADR-0008) · decided-by agent R-1 · accepted 2026-09-15 · repo: schema.py:31 GRADES, INVESTIGATION.md:110-114, review SKILL.md:41 · reverse: add one `spec` sub-label if readers cannot tell research claims from PRD quotes
- Settled: `consultation.dispatch.retain_raw_days` default 7 · decided-by agent R-1 · accepted 2026-09-15 · spec: MERGED-PLAN A5 raw streams expire; PRD AC-029 · reverse: change the default in CONFIG.md, no data migrates
- Settled: `consultation.dispatch.deadline_minutes` default 45 (human picked alternative `m45` over the recommended 20) · decided-by human R-1 · accepted 2026-09-15 · spec: PRD FC-8, AC-022 · reverse: change the default in CONFIG.md
- Open: ADR-0007 and ADR-0008 accepted by the human; Claude Reviewer's citation audit (ADR-AUDIT.md) may still reopen them

Seam investigations (run after R-1, per the human's no-objection on the ledger gap; ledgers under `investigations/`):
- INV-001 `debate_card` field set: partial (5 classes lack an enumeration method; no `investigation:` block). Anchor correction for the HL-6 row: `schema.py:46-48` is REQUIRED; the OPTIONAL edit site is `schema.py:69`, the renderer site `components.py:423-475`. Design unchanged.
- INV-002 config `TOP_LEVEL`: closed-with-frontier. New facts for the SDD: participant names differing only by `-`/`_`/`.`/case collide in the shell view; plugin must ship before a consuming repo adds the blocks; `CONFIG.md` drift test covers `CHILD_KEYS` blocks only.
- INV-004 registry surfaces: partial (same no-method classes). Gate-enforced same-commit set: both manifests, `providers/codex/agents/afk-afk-researcher.toml`, CLAUDE.md + README.md mentions, LANGUAGE.md pointer in each new SKILL.md and agent file.
- Plugin defect found by INV-001/002/004: `merge_fragments.py` folds seed placeholders as conflicts; workaround disclosed in each REPORT.md. Candidate for `/afk:report-issue` (not filed: plan artifacts only).

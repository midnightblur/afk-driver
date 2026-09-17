# PROPOSAL-claude — agent team topology + multi-model for the afk plugin

Author: planner-claude, 2026-09-15. Evidence ids (`PL-nn`, `HR-nn`, …) point at `FACTS-claude.md`. Claims without an id are design choices. "inferred" marks a conclusion not observed. The prior agreed design (`handoff-P1aHuF.md`) is challenged where stated.

## 0. Summary

- **Topology** = one config key, three values: `native` (today, default), `team`, `managed`. Roles, not agents, are the unit: contact, manager, planner, builder, reviewer, referee. Built-in patterns are role sets with lifecycle + provider rules; users add their own in `.afk/teams/`.
- **Transport** = a fifth adapter family, `agent` (kinds `headless`, `herdr`, `1devtool`, `claude-team`), verbs `spawn / send / wait / read / close / list / probe`. `headless` is the reference kind and needs nothing installed. Terminal tools add visibility only; content always moves through files.
- **Provider** (claude, codex) is orthogonal to transport. Launch recipes + the availability probe live in `hooks/lib/providers/<name>.sh` next to the harness detection that is already there (PL-24).
- **Knowledge store** = `{spec-dir}/knowledge/FACTS.jsonl`, append-only, written only through `scripts/afk-fact.py`, rendered to `FACTS.md`, with `status`, `evidence`, `producer`, `expires` on every row and a deterministic re-verify pass. Spawn prompts carry a filtered digest; agents log facts before they are closed.
- **Lifecycle** = each role declares `lifespan: turn | phase | feature`. Phase agents are compacted into the store, verified, then closed. A roster ledger records every spawn/close so a new contact session can recover the team.
- **Debate** = trigger-gated, file-based, inside the existing settle loop (SP-12); default off. Cross-model reviewer is the first, cheapest gate.
- **Opt-in** = no `team:` / `providers:` block → zero new behaviour. Both blocks are independent.
- **Phase 1** = env probe + provider probe + fact store + `headless` kind + cross-model second-opinion reviewer + `/afk:setup` opt-in rows for herdr. Everything else builds on it.

## a. Topology model and built-in patterns

### Options considered

| Option | What | Verdict |
|---|---|---|
| A. Keep one session, add cross-model headless turns | No team; orchestrator spawns `codex exec` / `claude -p` for single roles | Necessary base (multi-model without team, goal 4) but not sufficient for durable planners |
| B. Claude agent teams only | Use the experimental teammates feature (CN-02) | Rejected as the only path: Claude-only, experimental flag, one team per session, no nested teams, Codex harness has no equivalent |
| C. Terminal-tool teams only (herdr / 1DevTool) | Panes as agents | Rejected as the only path: neither tool is present for every user; herdr needs user-level hooks (EV-04) |
| D. Role-based topology over a transport family, with A as the default kind | Roles + patterns in config; transport chosen by env | **Recommended** — one abstraction, every environment, default preserved |

### Recommended model

`team.topology` ∈ `native` (default) | `team` | `managed`.

- `native`: exactly today. Every spawn stays the harness's own subagent call (SP-21). No transport family loaded.
- `team`: the plugin spawns and closes agents through the `agent` adapter family per the chosen pattern.
- `managed`: the human runs the agents. The plugin only publishes work items + the knowledge digest to files and reads results from the same files; it never spawns or closes. Gives goal 6's "user-managed agents" with zero transport code.

**Roles** (fixed vocabulary, glossary-owned):

| Role | Owns | Tier (PL-29) | Default lifespan |
|---|---|---|---|
| contact | the human conversation; never spawned; never delegated (PL-32) | frontier | feature |
| manager | pattern execution, roster, compaction, merges; never drafts or reviews | frontier | feature (default = the contact itself) |
| planner | grill briefs, PRD/SDD/plan drafts, critiques | frontier | phase |
| builder | one subtask, own worktree (SP-01 unchanged) | implementation | turn |
| reviewer | one concern or one second opinion | frontier | turn |
| referee | adjudication of disputes (SP-12/13 unchanged) | frontier | turn |

**Built-in patterns** (files under `teams/<pattern>.yaml` at plugin root — a registry dir like `adapters/`):

| Pattern | Roles spawned | Where it plugs in | Note |
|---|---|---|---|
| `solo` | none | — | alias of `topology: native` |
| `second-opinion` | reviewer × 1, provider ≠ builder's | review settle loop, on trigger | phase-1 pattern |
| `planner-duo` | planner × 2 (different providers when available), referee = contact | plan gates (grill-solution / to-subtasks) | the pattern running this research |
| `pipeline` | manager + builder per subtask + reviewer per concern | autopilot | keeps autopilot sequential (SP-02); only reviewer fan-out is parallel |

User patterns: `.afk/teams/<name>.yaml` (durable, committed or local per PL-11) or `--pattern @inline.yaml` for one-shot. Same schema as the built-ins; `scripts/afk-team.py validate` checks it. Pattern schema fields: `roles[]{role, provider: auto|claude|codex, tier, lifespan, count, sandbox: read-only|worktree-write|yolo-in-worktree, needs_history: bool}`, `gates[]{gate, trigger, rounds_max, escalate_to}`.

Challenge to the prior design: no separate "manager agent" by default. A second flagship session that only relays adds cost and a hop; the contact session is already the orchestrator in every skill today. `manager` becomes a spawnable role only for the `pipeline` pattern when the human opts in.

## b. Agent lifecycle

Policy per role, executed by the manager:

1. **Spawn** only when a pattern step names the role and no idle agent with the same role + provider + cwd + `needs_history=true` is on the roster. Reuse is allowed only for `needs_history` roles; every other role gets a fresh agent (matches the review doctrine: fresh per round, SP-12).
2. **Turn** lifespan: one headless run; nothing to kill; the output file is the result.
3. **Phase** lifespan: alive until the gate closes (planners until the design is agreed). Close protocol, in order: manager sends the compaction brief → agent appends its facts via `afk-fact add` and writes a handoff (`KS-16` shape) → manager runs `afk-fact verify --producer <handle>` → all rows verified or explicitly `inferred` → `close`. A failed verify keeps the agent alive for one repair round, then closes it anyway with rows marked `unverified` (never silent loss).
4. **Feature** lifespan: contact and (if spawned) manager. Session loss is covered by the roster ledger, not by keeping processes alive.
5. **Silence**: arm `hooks/stall-watchdog.sh` (PL-33) per phase agent on its output dir; on exit 3/4 → `read` the agent, mark `parked(timeout)` in the roster, close.
6. **History is cheap to keep, expensive to run**: because herdr exposes the session id (HR-13) and headless runs print it (CN-04), a closed agent's transcript remains resumable (`claude --resume`, `codex exec resume`, HR-14). So the rule is: close the process at phase end; resume the *session* only if a later step needs its full history. Tokens are spent only when resumed.

Roster ledger `plan/team/ROSTER.jsonl` (append-only, event-sourced like the lesson ledger KS-10): `{ts, event: spawned|compacted|closed|parked, handle, role, provider, model, transport, session_id, pane_id?, cwd, brief_path}`. Writer: `scripts/afk-team.py`. Reader: the contact on session start (`afk-team status` → what is alive, what to resume) — the recovery the memory note asks for.

## c. Knowledge store

### Options considered

| Option | Verdict |
|---|---|
| Markdown table per agent (this FACTS file) | Readable, but no stable ids, no merge, no re-verify → prototype only |
| Reuse the coverage ledger (KS-03..07) | Right ideas (claims with kind, line_hash, counter-checks) but investigation-shaped; too heavy per fact |
| JSONL ledger + rendered digest, sole writer script | **Recommended** — same pattern as lessons (KS-10) and coverage (KS-06), deterministic-first |

### Format

`{spec-dir}/knowledge/FACTS.jsonl` (survives `/afk:gc`, KS-17). One JSON object per line:

```
{ "id": "f-<sha1(claim)[:8]>", "event": "added|verified|refuted|expired|superseded",
  "ts", "producer": {"handle","role","provider","model","session_id"},
  "area": ["transport","herdr"], "claim": "...",
  "evidence": [ {"kind":"path","path":"hooks/lib/adapter.sh","line":29,"line_hash":"…"},
                {"kind":"command","cmd":"claude auth status","exit":0,"excerpt":"loggedIn:true"},
                {"kind":"url","url":"…","excerpt":"…"},
                {"kind":"fact","id":"f-…"} ],
  "status": "verified|inferred|unverified|refuted",
  "expires": {"kind":"file|commit|version|date|session|never","value":"…"},
  "supersedes": "f-…" }
```

Rules: `id` derives from the claim (dedup like KS-05); `added` carries the full payload, later events carry only `id/ts/producer/status/note`; last event wins on read; nobody edits a prior line. A claim whose only evidence is another agent's statement is `unverified` by construction. A `path` evidence row is `verified` only with a `line_hash` (KS-06 mechanism, reused).

### Producer flow

- Every spawned role's brief ends with: "Before finishing, run `afk-fact add` for each fact you established (claim, evidence, status, area, expires)." The digest tier and lite runner are exempt (they return evidence files, the caller logs).
- `/afk:investigate` on closure emits one `added` row per load-bearing claim (KS-05) with `evidence: {kind:"inv", id:"INV-NNN"}` — the deep record stays in COVERAGE.json, the store carries the pointer. This gives "dig further": the fact links to its investigation.
- Grill Settled rows (KS-12) and `plan/DECISIONS.md` (KS-01) stay where they are: decisions are not facts. A fact row may cite a decision id as evidence.

### Verification

- `afk-fact verify [--producer h|--area a|--all]`: re-checks every `path` (hash), `command` (re-runs read-only commands only, marked `safe: true` at add time), `fact` (target exists and is not refuted), `expires` (file changed / commit moved / version differs / date passed) → emits `verified` or `expired` events. Deterministic, no model.
- Agent verification on consume: a consumer that relies on an `inferred` or `unverified` fact must either upgrade it with evidence (`afk-fact verify --id … --evidence …`) or cite it as inferred in its own artifact. Refutation is an event with evidence, never a deletion.
- `/afk:retro` mines refuted/expired rates per producer role and provider (same mining shape as KS-15).

### Retrieval

- `afk-fact digest --area <tags> [--status verified,inferred] [--max N]` renders a compact markdown table. Spawn templates (SP-04's `SUBAGENT-PROMPT.md` and the new team briefs) carry a `{KNOWLEDGE_DIGEST}` placeholder filled by area tags the pattern step names, injected the way `hooks/lesson-digest.sh` injects lessons (KS-10).
- Consumer rule in every brief: "Do not re-derive a `verified` fact; cite its id. Dig further from it. Log what you add."
- `FACTS.md` is regenerated by `afk-fact render` (human view; never hand-edited).

This ledger (`FACTS-claude.md`) shows the column set works; what it lacks — stable ids, hashes, events — is exactly what the script adds.

## d. Transport abstraction and env auto-detection

### Family `agent` (fifth adapter family, ADAPTERS.md procedure PL-08 plus a new "add a family" section, PL-09)

| Verb | Input JSON | Answer |
|---|---|---|
| `probe` | — | `{available: bool, reason, human_present: bool}` |
| `spawn` | `{name, role, provider, model, effort, cwd, sandbox, brief_path, env}` | `{handle, session_id, pane_id?, pid?}` |
| `send` | `{handle, text|brief_path, wait: bool, timeout_ms}` | `{state}` |
| `wait` | `{handle, until[], timeout_ms}` | `{state}` |
| `read` | `{handle, lines?}` | `{output_path}` (always a file, per DELEGATION return contract PL-31) |
| `close` | `{handle, keep_session: bool}` | `{closed: bool, session_id}` |
| `list` | — | roster-shaped rows |

Selection: `.afk/config.yaml` `agent: auto|headless|herdr|1devtool|claude-team|none` (default `none` = family never loaded). `auto` resolves through the env probe below. Per-user override lives in `~/.afk/config.yaml` (PL-12).

| Kind | spawn | send | wait | read | close | Needs |
|---|---|---|---|---|---|---|
| `headless` (reference) | `claude -p --session-id U --output-format json --max-turns/--max-budget-usd …` or `codex exec --json -o FILE -C cwd …` (CN-03, CX-01); durable Claude variant `claude --bg` (CN-05) | new turn = `claude -p --resume U` / `codex exec resume`; bg = `claude attach`-less `--resume` | process exit / `claude agents --json` status | output file | nothing to kill; `claude rm` for bg | CLIs only |
| `herdr` | `pane split --cwd --no-focus` + `agent start --kind -- ARGS` (HR-01..05) | `agent prompt --wait` (HR-06) | `agent wait --until` (HR-08) | `agent read` → file (HR-11) + the agent's own result file | `pane close` (HR-12); session id kept from `agent list` (HR-13) | herdr + its per-CLI integration hooks (HR-10) |
| `1devtool` | `run --to --cwd --model --json` or `team start --manifest-stdin` (DT-02, DT-07) | `team send` / `link send` (DT-05) | `collect` (DT-06) | collected result | `stop --close-terminals` (DT-04) | app running + attributed terminal for team ops (DT-11) |
| `claude-team` | teammate spawn via the Agent-teams feature (CN-02) | SendMessage | TaskCompleted / idle | mailbox | shutdown request | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, Claude harness only |

Design rules: briefs and results are files; the prompt text is "read `<brief_path>`; write `<result_path>`; end with `OUTCOME:`" (HR-21 justifies this for Codex on Windows). `spawn` on a pane-based kind must poll `wait --until idle` before the first `send` (HR-02). A `blocked` state (HR-09) is never auto-answered: the kind returns `blocked` and the manager surfaces it to the human (HR-06 text; CN-10 dialogs).

Sandbox per role: builder `yolo-in-worktree` (`--dangerously-skip-permissions` / `--dangerously-bypass-approvals-and-sandbox` only when `cwd` is a worktree the plugin created; refuse on the main checkout or any branch matching a `protected` list); planner/reviewer/referee `read-only` (`-s read-only`, `--permission-mode` default). Codex peers on herdr that must call `herdr` back need the bypass (HR-22) — so on herdr, Codex roles talk back through files + the manager's `wait`, never through `herdr agent prompt`.

### Env auto-detection (`scripts/afk-env.py`, deterministic, JSON out)

| Signal | Test | Meaning |
|---|---|---|
| harness | existing `afk_provider_detect` (PL-24) | claude / codex / unknown |
| inside herdr | `HERDR_ENV=1` and `HERDR_PANE_ID` set and `herdr status` exit 0 (HR-18, HR-20) | herdr kind usable, human-present |
| inside 1DevTool | `1devtool-agent whoami` → `session:true` (DT-11); shim present but `session:false` → app present, team ops unavailable | 1devtool kind usable (attributed) / run-only |
| child session | `CLAUDE_CODE_CHILD_SESSION=1` (CN-08, inferred) or `parent_tool_use_id` in stream (CN-09) | this session is itself a spawned agent → never spawn a team (nesting cap PL-30) |
| plain terminal | none of the above | headless only |
| attended | `CLAUDE_CODE_SESSION_ATTENDED=1` (CN-07) | lavish/human-present rules apply |

`auto` precedence: explicit config > herdr (if inside herdr and attended) > 1devtool (if attributed) > headless. Result cached per session in `AFK_CFG_*` shell view (PL-13).

## e. Provider availability probe

Installed ≠ usable (DT-10 shows 1DevTool stops at "installed"). Four rungs, each cheaper than the next, run by `scripts/afk-providers.py probe [--provider p] [--refresh]`:

| Rung | claude | codex | Cost |
|---|---|---|---|
| 0 binary + version | `claude --version` | `codex --version` (≥ O1's floor, PL-37) | ms |
| 1 login | `claude auth status` JSON `loggedIn` (CN-12) | `codex login status` exit 0 (CX-03); `codex doctor` (CX-05) | ~1 s |
| 2 live turn, cheapest model | `claude -p "Reply OK" --max-turns 1 --model haiku --no-session-persistence --bare --output-format json` (CN-13: 9 s) | `codex exec --ephemeral -s read-only --skip-git-repo-check -m <cheapest> "Reply OK"` (CX-04: 20 s) | seconds; run once per day or after a failure |
| 3 tier model check | one turn per tier model named in PROVIDERS.md (PL-25), on demand only, when a pattern asks for that tier | seconds each |

Answer per provider: `absent | installed | logged-in | usable | degraded(reason)` plus `models_ok[]`, `probed_at`, `expires` (24 h for rung 2/3; rung 0/1 re-run every session start). Cache: `~/.afk/providers.json` (machine layer, PL-12). Quota/auth failures at rung 2 (non-zero exit, error text) set `degraded` with the excerpt as evidence — a fact row in the store's `provider` area. A pattern role with `provider: auto` picks the first `usable` provider in the pattern's preference list; `provider: codex` with codex `degraded` → the role falls back to the harness provider and the run logs a `decision(D-n)` (two-way door, KS-01) unless the pattern marks the role `strict`.

## f. Opt-in and default-preserving guarantee

- Config: no `agent:` key → family not loaded (PL-04 path never reached); no `team:` key → `topology: native`; no `providers:` key → single provider = the harness. The three keys are independent: `team` with one provider works (every role `provider: auto` resolves to the harness); `providers.cross_model: true` without `team` works (only headless turns from the single session, pattern `second-opinion`).
- Every new MANIFEST row is `[opt-in]` (PL-35): herdr binary (H-tier row, auto fix = download the standalone release, HR-24), herdr integrations (`herdr integration status`, HR-10), 1DevTool shim, provider probe cache. `/afk:setup` shows them in the Step 3 election (PL-36); declined = `skipped (user choice)`.
- No new hooks by default; the shared hook subset (PL-21) is untouched. Child completion stays "spawning call return or watchdog exit" (CN-15).
- Distribution law (PL-27): herdr's user-level hook files are herdr's, installed by `herdr integration install`, never by the plugin tree.
- CAPABILITIES row `agent_transport`: optional; degradation = "run `topology: native`". A gate test under `hooks/tests/` runs the existing probes with no `team`/`agent`/`providers` keys and asserts byte-identical `afk-config.py effective` output.

## g. Fit with existing mechanisms

| Mechanism | Change |
|---|---|
| ADAPTERS.md / adapter.sh | fifth family `agent`; `AFK_CFG_AGENT`; new section "Adding a family" (PL-09); answer shapes unchanged (PL-04) |
| CONFIG.md / afk-config.py | blocks `agent:` (kind), `team:` (`topology`, `pattern`, `protected-branches`, `max-agents`), `providers:` (`prefer[]`, `cross_model`, `probe-ttl-hours`); enum rows per PL-08 |
| PROVIDERS.md / hooks/lib/providers/*.sh | tier table (PL-25) gains a "cheapest probe model" column; new functions `afk_<p>_launch_headless`, `afk_<p>_probe`, `afk_<p>_resume`; the pin-delivery rule (PL-26) holds — a headless spawn passes the tier's model explicitly because no agent definition travels across processes (documented exception) |
| DELEGATION.md | new section "Out-of-session agents": same must-delegate triggers and return contract (PL-31); nesting cap counts external agents; a child session never spawns a team |
| CAPABILITIES.md | rows `agent_transport` (optional), `cross_session_messaging` (optional, Claude only, CN-06) |
| MANIFEST.md | rows T1 herdr, T2 herdr integrations, T3 1DevTool shim, T4 provider cache; all `[opt-in]` |
| autopilot (SP-01..05) | unchanged loop; when `topology: team` + `pipeline`, the per-subtask spawn goes through `agent spawn` with the same `SUBAGENT-PROMPT.md` brief + `{KNOWLEDGE_DIGEST}`; parking stays status-agnostic |
| execute Step 10 / preflight PF-3 (SP-06, SP-19) | settle loop unchanged; reviewer side may be an external agent of another provider when a trigger fires; referee stays the executing session (SP-12) |
| review SKILL (SP-09..11) | trigger table gains a `second-opinion` column; `class` enum and verdict set untouched (lockstep respected) |
| grill-solution / to-subtasks | optional plan-gate step "planner-duo" when `team.pattern` names it; output = merged draft + debate files; human still signs off (HUMAN-SIGNOFF lockstep untouched) |
| investigate (SP-18, KS-03) | emits fact rows on closure; tracer briefs carry the digest |
| retro | mines fact events + debate trigger yield (KS-15 shape) |
| gc | leaves `knowledge/`; deletes `plan/team/` with `plan/` |
| GLOSSARY.md | terms: topology, pattern, role names, roster, fact store, transport kind |
| REPORTING.md | new status lines `TEAM:` (spawn/close) follow the plain-terms rule (PL-41: roster ids exist on disk before they are named) |

## h. Debate and cross-model gates

Keep the prior design's mechanics (independent draft → numbered objections marked blocking/advisory → converge → stop when no blocking objection and both write reasoned AGREE → per-tier round cap → escalate), with three corrections:

1. **Live inside the settle loop**, not beside it. The review gate already has fresh reviewers, a referee, dispute adjudication, an information diet and a 10-round cap (SP-12/13). A cross-model round = a reviewer of the other provider added to the roster of that round. No second loop.
2. **Trigger-gated, default off.** Triggers reuse the review trigger-table shape (SP-11): plan gate — new ADR, migration, public contract change, security/tenancy code, > N subtasks; review gate — `blocking` finding, low reviewer confidence, diff > N lines, second fix loop. Each fired trigger is logged to the outcomes file (KS-15) so `/afk:retro` can drop triggers that never changed a verdict.
3. **Cascade by open points, not by rounds.** Tier 1 (sol vs opus) drafts and critiques; tier 2 (astra + fable) rules only on points still open, fed both positions by file path. Prices unverified — the tier table stays a config default, not doctrine, until checked.

Files: `plan/debate/<gate>/round-N-<handle>.md`; terminal messages carry only "read <path>, write <path>". Referee = the gate's orchestrating session; never a model of either side when a second provider is usable.

## i. Risks and open questions for the human

| # | Risk / question | Evidence |
|---|---|---|
| 1 | herdr state detection depends on herdr-installed user hooks; if absent, `wait` sees `unknown` forever | HR-10, EV-04 |
| 2 | Codex sandbox blocks herdr calls; Codex peers must communicate by file | HR-22 |
| 3 | Builders in yolo mode: confirm the protected-branch list and that worktrees created by the plugin are the only yolo cwd | b. sandbox rule |
| 4 | New-worktree dialogs (trust, project `.mcp.json`, Chrome) block interactive spawns; headless is immune; interactive Claude spawns need `enableAllProjectMcpServers` or per-project pre-approval + `--no-chrome` | CN-10, CN-11 |
| 5 | Claude agent teams are experimental and Claude-only; keep as a kind, not the base | CN-02 |
| 6 | 1DevTool team ops need an attributed terminal; from an unattributed shell only `run` works. Is the desktop app always running for 1DevTool users? | DT-11 |
| 7 | Cost of rung-2 probes (9–20 s each) — accept a 24 h cache? | CN-13, CX-04 |
| 8 | Manager model: default = contact session (Claude). Spawn a separate manager only for `pipeline`? | a. |
| 9 | Round caps and trigger thresholds (N subtasks, N diff lines) — set as config defaults; which values? | h. |
| 10 | Should the human see each agreed plan before builders start? Recommend yes (HUMAN-SIGNOFF lockstep already requires it for the SDD) | g. |
| 11 | Store location `{spec-dir}/knowledge/` survives gc; is repo-committed knowledge wanted, or gitignored like the lesson ledger? | KS-10, KS-17 |
| 12 | `CLAUDE_CODE_CHILD_SESSION` semantics are inferred; verify before using it as the "never spawn a team" guard | CN-08 |

## j. Phased delivery

| Phase | Deliverable | Proves |
|---|---|---|
| **1 (smallest useful)** | `scripts/afk-env.py`, `scripts/afk-providers.py probe`, `scripts/afk-fact.py` + `knowledge/` format doc, adapter family `agent` with kind `headless` only, config blocks (all default-off), review trigger `second-opinion` (reviewer of the other provider via headless), MANIFEST `[opt-in]` rows incl. herdr install offer, CAPABILITIES rows, gate test for byte-identical defaults | goals 3, 4, 5, 7; multi-model without a team |
| 2 | kind `herdr`, roster ledger + lifecycle (compact → verify → close), pattern `planner-duo` at the plan gate, `afk-team status` recovery; dogfood on this feature | goals 1, 2, 6 with a terminal tool |
| 3 | kind `1devtool` (after one executed spawn/kill probe, DT-17), `claude-team` kind, user-defined patterns, `pipeline` pattern in autopilot, retro mining of trigger yield and fact refutation rates | goals 6, 8; cost tuning |

Phase 1 touches no existing spawn path; the first behavioural change a default user could see is none.

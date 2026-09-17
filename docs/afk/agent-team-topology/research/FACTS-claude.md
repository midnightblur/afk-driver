# FACTS-claude — knowledge ledger (planner-claude, 2026-09-15)

Prototype of the goal-3 store. One row per fact. `status`: verified = evidence re-checkable now; inferred = conclusion from evidence, not observed; unverified = read in a doc, not exercised. `expires-when` names the condition that invalidates the row (a file edit, a version change, a session end), never a guess.

Evidence paths are relative to the plugin worktree `C:\Users\mvu\PersonalProjects\afk-driver-agent-teams` at commit `d8ca9b4` unless absolute. Raw probe output: scratchpad `herdr-help.txt` (1399 lines, not in the repo). Subagent digests fed rows PL/SP/KS/HR/DT/CN; rows EV/CX/AU come from commands this session ran. Bounded live probes run: one `claude -p` turn (haiku, session `9c539e8f…`, exited) and one `codex exec` turn (read-only sandbox, exited). No pane, agent, team or task was created or killed.

## PL — plugin internals the feature must fit

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| PL-01 | Adapter layout is `adapters/<family>/<kind>/{adapter.json, CONTRACT.md, entry}` | ADAPTERS.md:7-10 | verified | ADAPTERS.md edit |
| PL-02 | Dispatch API: `afk_adapter family verb [json]`, `afk_adapter_kind family`, `afk_adapter_dir family` | hooks/lib/adapter.sh:9-11; ADAPTERS.md:15-19 | verified | adapter.sh edit |
| PL-03 | Kind selection reads env `AFK_CFG_<FAMILY>` (config export), not the YAML | hooks/lib/adapter.sh:29-35 | verified | adapter.sh edit |
| PL-04 | Unknown kind or missing dir → exit 2 naming `.afk/config.yaml`; unknown verb → `{"unsupported":true}` exit 3; runtime missing → exit 4 | hooks/lib/adapter.sh:40-51,55-104; ADAPTERS.md:29-38 | verified | adapter.sh edit |
| PL-05 | `adapter.json` `runner.type` is `instruction` (returns `{"instruction":file,"verb":verb}` for the agent to follow) or an executable entry (`.py` via python, else bash) | hooks/lib/adapter.sh:55-117 | verified | adapter.sh edit |
| PL-06 | `build-gate` is the one family selected as a list (`build-gates:`); its kinds are sourced into the caller (`afk_bg_<kind>_discover/_run`), except `worktree-provision` which runs as a subprocess | hooks/lib/adapter.sh:120-171; ADAPTERS.md:108-130 | verified | adapter.sh edit |
| PL-07 | Existing families + kinds: tracker{jira,github-issues,none}, forge{gitlab,github,none}, notes{repo-files,obsidian,notion}, build-gate{maven,npm} | ADAPTERS.md:42-135; `ls adapters/` | verified | adapters/ tree change |
| PL-08 | Adding a kind = 4 steps: adapter files; enum row in CONFIG.md + `scripts/afk-config.py`; register rows in `skills/afk/setup/MANIFEST.md`; README parity row + probe under `hooks/tests/`. `hooks/skill-registry-gate.sh` enforces | ADAPTERS.md:137-148 | verified | ADAPTERS.md edit |
| PL-09 | Adding a family has no written procedure; the family list is stated in ADAPTERS.md, `CONFIG.md` and `hooks/lib/adapter.sh` (family → `AFK_CFG_*` key) | ADAPTERS.md:42-135 (four `##` family sections, no "add a family" section) | inferred (absence) | ADAPTERS.md edit |
| PL-10 | Sole config reader is `scripts/afk-config.py` (`effective --json`, `get`, `validate`, `export-shell`, `resolve`) | CONFIG.md:9-13,236-244 | verified | CONFIG.md edit |
| PL-11 | Discovery order: `$AFK_CONFIG` → `.afk/config.local.yaml` (gitignored) → `.afk/config.yaml` → `~/.afk/config.yaml` → built-in defaults; layers deep-merge | CONFIG.md:20-32 | verified | CONFIG.md edit |
| PL-12 | A machine-level `~/.afk/config.yaml` layer exists → per-user transport/provider preferences have a home without touching the repo | CONFIG.md:20-32 | verified | CONFIG.md edit |
| PL-13 | Shell view: scalar → `AFK_CFG_<PATH>`, list → `_COUNT` + `_0..n`, `AFK_CFG_LOADED=1`, loaded once per Stop by `hooks/lib/config.sh` | CONFIG.md:236-244 | verified | CONFIG.md edit |
| PL-14 | Supported YAML subset: block maps/lists, plain/quoted scalars, comments, int/float/bool/null. Refused: flow maps/lists, anchors, block scalars, tabs, multi-doc, duplicate keys | CONFIG.md:71-79 | verified | afk-config.py edit |
| PL-15 | Top-level blocks: schema, toolkit-version, tracker, forge, notes, build-gates, jira, github-issues, gitlab/github, git, repo-files, obsidian, notion, artifacts, maven, npm, verification, repo-hooks, setup, worktree, investigation, report-issue, developer | CONFIG.md:83-107 | verified | CONFIG.md edit |
| PL-16 | No block for models, providers, agents or teams exists; every unknown child key is refused by dotted path | CONFIG.md:83-116 | verified | CONFIG.md edit |
| PL-17 | `developer:` map is per-machine, resolved by `afk-config.py resolve <key>`, never committed | CONFIG.md:107 | verified | CONFIG.md edit |
| PL-18 | `repo-hooks` lets a consuming repo add SessionStart/PreToolUse/Stop hooks by JSON; run by `hooks/run-hook.py` | CONFIG.md:157-167 | verified | CONFIG.md edit |
| PL-19 | Capability names: skills, plugin_hooks, hook_shell_match, hook_project_dir, custom_agents, agent_tool_allowlist, parallel_agents, continuation, nesting, model_tiers, plugin_mcp, plugin_job_dir, question_cards, design_push, issue_egress, reload | CAPABILITIES.md:5-22 | verified | CAPABILITIES.md edit |
| PL-20 | Rule: a missing required capability stops the skill; a missing optional one degrades per its row | CAPABILITIES.md:3 | verified | CAPABILITIES.md edit |
| PL-21 | Shared hook events: SessionStart, PreToolUse, Stop only. SubagentStop/Notification are outside the shared subset | CAPABILITIES.md:26 | verified | CAPABILITIES.md edit |
| PL-22 | Every hook command form is `python "${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.py" plugin|repo <handler.sh>` | CAPABILITIES.md:33 | verified | CAPABILITIES.md edit |
| PL-23 | Two harnesses: claude (`.claude-plugin/plugin.json`) and codex (`.codex-plugin/plugin.json`) | PROVIDERS.md:9-13 | verified | PROVIDERS.md edit |
| PL-24 | Harness detection: `AFK_PROVIDER` override → `afk_<name>_detect` per provider; claude = `CLAUDE_PLUGIN_ROOT` or `CLAUDECODE` set (priority 20); codex = `PLUGIN_ROOT` set (priority 10); lowest priority number wins; tie → ambiguous | hooks/lib/provider.sh:18-42; hooks/lib/providers/claude.sh:3-9; codex.sh:3-9 | verified | provider.sh edit |
| PL-25 | Model tiers per provider: frontier = `opus` / `gpt-5.6-sol` high–xhigh; implementation = `claude-opus-4-8` pinned / `gpt-5.6-terra` medium; digest = `sonnet` / `gpt-5.6-terra` low; deterministic = `haiku` via afk-runner-lite / `gpt-5.6-terra` low | PROVIDERS.md:55-64 | verified | PROVIDERS.md edit |
| PL-26 | The implementation-tier pin travels through the agent definition (`afk-implementor`), never a spawn-time model argument | PROVIDERS.md:65; skills/afk/autopilot/SKILL.md:35 | verified | PROVIDERS.md edit |
| PL-27 | Distribution law: the committed tree is inert until a harness enable flag names it; never commit `.agents/`, `.codex/` except `.agents/plugins/marketplace.json` | PROVIDERS.md:39-45 | verified | PROVIDERS.md edit |
| PL-28 | Credentials fallback chain (Jira) already spans exported vars → `~/.claude.json` → `~/.codex/config.toml` | PROVIDERS.md:75-77 | verified | PROVIDERS.md edit |
| PL-29 | DELEGATION tiers map to roles: frontier (grilling, planning, review adjudication, adversary, afk-tracer, plugin edits), implementation (afk-implementor), digest (afk-reader/afk-runner), deterministic (afk-runner-lite) | DELEGATION.md:45-49 | verified | DELEGATION.md edit |
| PL-30 | Spawn rules: independent children in one message; background spawn to overlap human think-time; named agent types first; nesting cap 3 levels, helpers do not spawn | DELEGATION.md:24-30 | verified | DELEGATION.md edit |
| PL-31 | Return contract: terse tail `OUTCOME: <ok|fail|blocked> — <line>`, body ≤ ~30 lines, every claim cited `file:line` or command + exit code, bulk evidence to a file | DELEGATION.md:63-69 | verified | DELEGATION.md edit |
| PL-32 | Never delegate: the human conversation, conversation synthesis, single-writer stamps, accumulated-nuance loops | DELEGATION.md:17-20 | verified | DELEGATION.md edit |
| PL-33 | Stall watchdog `hooks/stall-watchdog.sh`: `--path`, `--stale-min` (20), `--cap-min` (90), `--poll-sec` (60), `--label`; exit 3 stale, 4 cap, 2 usage; never 0. Armed for any child that may run > ~15 min | hooks/stall-watchdog.sh:10-28; DELEGATION.md:34-39 | verified | stall-watchdog.sh edit |
| PL-34 | Agent definitions: afk-implementor (model `claude-opus-4-8`, no tools line), afk-reader (sonnet), afk-runner (sonnet), afk-runner-lite (haiku), afk-tracer (opus) | agents/*.md:2-6 | verified | agents/ edit |
| PL-35 | MANIFEST register entry = Needed by / Probe (exit 0 healthy) / Fix (`auto:` or `human:`) / Notes; tags `[deferred]`, `[opt-in]` (miss = `opt-in available`, never `missing`) | skills/afk/setup/MANIFEST.md:8-31 | verified | MANIFEST.md edit |
| PL-36 | `/afk:setup` offers optional items as a multi-select election at Step 3; declined → `skipped (user choice)`; `base` tier adds workstation section W | skills/afk/setup/SKILL.md:15-27,68-83 | verified | setup/SKILL.md edit |
| PL-37 | Codex rows O1–O8 already exist (binary+login O1 min 0.152.0, hooks O2, marketplace O3, hook trust O4, agent TOML stubs O5, …) | MANIFEST.md:499-605 | verified | MANIFEST.md edit |
| PL-38 | `herdr`, `1devtool`, `onedevtool` appear nowhere in the plugin outside `docs/` | `grep -ri` over repo excluding docs/: 0 hits | verified | any plugin edit naming them |
| PL-39 | FRESHNESS same-commit rule: dependency change → MANIFEST row; surface change → every registry-named surface; contract change → all lockstep files | FRESHNESS.md:9-21 | verified | FRESHNESS.md edit |
| PL-40 | LANGUAGE.md §3 binds every runtime artifact: every sentence a fact, complete over short, one fact one home, tables for parallel structure, formats are contracts | LANGUAGE.md:38-49 | verified | LANGUAGE.md edit |
| PL-41 | REPORTING.md: an enumerated-item id is legal only if its catalogue is already on disk | REPORTING.md:31 | verified | REPORTING.md edit |

## SP — where subagents are spawned today

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| SP-01 | Autopilot spawns one fresh subagent per subtask from `SUBAGENT-PROMPT.md`; sizing by `## Complexity`: mechanical → general-purpose child at digest tier; standard → afk-implementor; complex → afk-implementor at high effort; never frontier | skills/afk/autopilot/SKILL.md:33-35 | verified | autopilot/SKILL.md edit |
| SP-02 | Autopilot is sequential by design: one subtask, one worktree, one app instance; never parallel | skills/afk/autopilot/SKILL.md:42 | verified | autopilot/SKILL.md edit |
| SP-03 | The parent reads the child's verdict from the spawning call's own result; it never waits on a completion notification | skills/afk/execute/SKILL.md:135; SUBAGENT-PROMPT.md:41 | verified | execute/SKILL.md edit |
| SP-04 | Placeholders in spawn prompts: `{WORKFLOW_SKILLS_DIR}`, `{WORKFLOW_HOOKS_DIR}`, `<main-checkout>`; the child ends with one `OUTCOME:` line | skills/afk/autopilot/SUBAGENT-PROMPT.md:5-41 | verified | SUBAGENT-PROMPT.md edit |
| SP-05 | Park handling is status-agnostic: any non-success outcome parks the subtask and its dependents; a silent child is `parked(timeout)` by the watchdog | skills/afk/autopilot/SKILL.md:38-40 | verified | autopilot/SKILL.md edit |
| SP-06 | Execute delegates: Step 1 fallback reads → afk-reader; Step 8 long tiers → afk-runner; Step 10 → `/afk:review` (fresh subagent per concern); Step 10.5 → `/afk:adversary` in a fresh session blind to the diff | skills/afk/execute/SKILL.md:39,67,71,89 | verified | execute/SKILL.md edit |
| SP-07 | DRIVEN mode: no human pause, decisions via DECISIONS.md, commit/push pre-authorized, tiers hard | skills/afk/execute/SKILL.md:27-33 | verified | execute/SKILL.md edit |
| SP-08 | Status set (Step 13): success, test_fail/build_fail, review_fail, adversary_fail, adversary_unrun, blocked_by, needs_decision, timeout, other, + cited-mode design_conflict/contract_mismatch/produces_drift | skills/afk/execute/SKILL.md:113-125 | verified | execute/SKILL.md edit |
| SP-09 | Review: one fresh read-only subagent per concern (11 concerns), all in one message; verdicts clean/advisory/blocking; class enum correctness, spec, compliance, smell, scope, test, design, pattern-debt, product-debt | skills/afk/review/SKILL.md:12,43-59,118-140,176-181 | verified | review/SKILL.md edit |
| SP-10 | Gate policy: `full` = six always-on concerns + trigger table; `lean` = spec-fidelity, scope-and-impact, test-veracity, rest deferred to the feature gate | skills/afk/review/SKILL.md:67-68 | verified | review/SKILL.md edit |
| SP-11 | Review triggers are a table keyed on diff facts (the pattern the debate triggers can reuse) | skills/afk/review/SKILL.md:47-59 | verified | review/SKILL.md edit |
| SP-12 | Settle loop: roles Implementor / Reviewer side (fresh per round, never persistent) / Referee (the gate orchestrator); rounds review → filter → fix-or-dispute → adjudicate (one fresh subagent per disputed finding) → close; hard cap 10 rounds | skills/afk/review/SETTLEMENT.md:6-19,29 | verified | SETTLEMENT.md edit |
| SP-13 | Adjudicator information diet: finding JSON + implementor rationale + diff path + contract/spec + CLAUDE.md chain, nothing more; no subagent prompt carries round number, cap, or the settled ledger | skills/afk/review/SETTLEMENT.md:17,50-52 | verified | SETTLEMENT.md edit |
| SP-14 | Verify pass: one fresh skeptic subagent per design-level finding ≥ medium, briefed to refute | skills/afk/review/SKILL.md:146 | verified | review/SKILL.md edit |
| SP-15 | Adversary: verdicts clean / findings / env_unreachable / tainted; classes correctness, spec, authz, robustness; must not read diff, tests, findings, commits | skills/afk/adversary/SKILL.md:17-38 | verified | adversary/SKILL.md edit |
| SP-16 | Grills spawn afk-reader digests in the background before the first question and per round (think-time overlap) | skills/afk/grill-requirements/SKILL.md:14-16; ROUND.md:52 | verified | grill files edit |
| SP-17 | `/afk:bug` runs Publisher/Fixer/Retester as subagents; only the main session writes `state.json`; refuses to dispatch in driven context | skills/afk/bug/SKILL.md:30-46 | verified | bug/SKILL.md edit |
| SP-18 | `/afk:investigate` spawns afk-tracer per partition, a delta tracer on uncovered nodes, and a blind counter-search tracer told to use a different method | skills/utils/investigate/SKILL.md:49 | verified | investigate/SKILL.md edit |
| SP-19 | Preflight PF-3 reruns the settle loop feature-wide; stalemate → `park(PF-3: review_stalemate)` | skills/afk/preflight/SKILL.md:85-116 | verified | preflight/SKILL.md edit |
| SP-20 | No skill spawns a child under another model provider, and no cross-model debate mechanism exists; "codex" hits are harness support, "debate" hits are grill question classes | grep over skills/, hooks/, root *.md | verified (absence) | any skill edit |
| SP-21 | Every spawn today is the harness's own subagent call (Agent tool on Claude; "parallel agent spawns" on Codex); no skill starts an external process as an agent | PROVIDERS.md:25; SP-01…SP-19 | verified (absence) | any skill edit |

## KS — existing knowledge-like stores

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| KS-01 | `plan/DECISIONS.md`: `## D-{n}` + date/decided-by, Options, Chosen, Supersedes, To reverse; append-only; two-way-door test (reversible, clear winner with cited evidence, inside authority) | DECISIONS.md:9-34 | verified | DECISIONS.md edit |
| KS-02 | Readers: every executor before a slice; the orchestrator's end-of-run report lists each D-{n}. Lives and dies with `plan/` | DECISIONS.md:40-42 | verified | DECISIONS.md edit |
| KS-03 | Coverage ledger = `COVERAGE.json` + `REPORT.md` under `{spec-dir}/investigations/INV-NNN-slug/`; single writer `/afk:investigate`; tracers return fragments | INVESTIGATION.md:138-140; skills/utils/investigate/LEDGER-FORMAT.md:9-18; SKILL.md:10 | verified | LEDGER-FORMAT.md edit |
| KS-04 | `COVERAGE.json` keys: run, boundaries, nodes, queries, claims, counter_checks | LEDGER-FORMAT.md:22 | verified | LEDGER-FORMAT.md edit |
| KS-05 | `claims[]` rows carry `kind` = fact / inference / unverified, `load_bearing`, `supporting_nodes`, `citations`; stable id `c-<sha1(text)[:8]>` | LEDGER-FORMAT.md:187-195,270-273 | verified | LEDGER-FORMAT.md edit |
| KS-06 | `nodes[]` carry `line_hash` = first 12 hex of SHA1 of the line bytes, so a node survives edits above it — an existing staleness mechanism | LEDGER-FORMAT.md:114 | verified | LEDGER-FORMAT.md edit |
| KS-07 | `counter_checks[]` (deterministic or agent) target claims; verdict closed / closed-with-frontier / partial computed only by the validator | LEDGER-FORMAT.md:197-205,237-246 | verified | LEDGER-FORMAT.md edit |
| KS-08 | No dedup/reuse rule: a closed investigation is not consulted before a new one; `/afk:execute` "re-takes the ground" of the `(INV-NNN)` a seam cites | skills/afk/to-subtasks/SKILL.md:64; INVESTIGATION.md full read | verified (absence) | INVESTIGATION.md edit |
| KS-09 | No store defines an `expires` field; `verified/inferred` status exists only in the coverage ledger claims | grep `expires|expiry|staleness` over *.md: prose hits only | verified (absence) | any format edit |
| KS-10 | Lesson ledger `<main-checkout>/.claude/lessons/LEDGER.jsonl`: append-only JSONL, sole emitter `hooks/lesson-append.sh`, sole parser `hooks/lesson-digest.sh`, last-event-wins fold; classes missed-instruction … wrong-design; events opened/applied/verified/rejected/filed/superseded | skills/afk/lessons/LEDGER-FORMAT.md:7-104; hooks/lesson-digest.sh:65-71 | verified | LEDGER-FORMAT.md edit |
| KS-11 | The appender is best-effort (exit 0 always); a failed append is a stderr note | skills/afk/lessons/CAPTURE.md:94-95 | verified | CAPTURE.md edit |
| KS-12 | `GRILL-LOG.md`: one `##` per grill skill; Settled rows carry `decided-by agent R-{n} · accepted {date} · {grade}: {evidence} · reverse: {clause}` | skills/afk/grill-requirements/GRILL-LOG-FORMAT.md:9-33 | verified | GRILL-LOG-FORMAT.md edit |
| KS-13 | `plan/JOURNAL.md` line = `{YYYY-MM-DD HH:mm} \| {writer} \| {subject} \| {event} — {plain terms}`; writers execute, autopilot, smoke-test, preflight, understand | skills/afk/to-subtasks/JOURNAL-FORMAT.md:20-37 | verified | JOURNAL-FORMAT.md edit |
| KS-14 | `INDEX.md` rows are owned per skill (row-ownership map); absent artifacts stay `—` | skills/afk/to-prd/INDEX-FORMAT.md:7-21 | verified | INDEX-FORMAT.md edit |
| KS-15 | `plan/review/*.outcomes.json` = `{"r-001": "fixed" \| "dismissed(reason)" \| "deferred"}`; `/afk:retro` mines the same shape | skills/afk/review/SKILL.md:142 | verified | review/SKILL.md edit |
| KS-16 | Handoff doc = goal, current state, next steps, artifact pointers; references by path, never duplicated content | skills/utils/handoff/SKILL.md:11-15 | verified | handoff/SKILL.md edit |
| KS-17 | `plan/` is deleted whole by `/afk:gc` after merge; the spec folder (PRD/SDD/investigations) survives | CLAUDE.md "Section ownership invariants" Lifespan; KS-03 path | verified | gc/SKILL.md edit |

## HR — herdr as a transport (0.9.0)

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| HR-01 | Spawn is two steps: `herdr pane split [PANE] --direction right\|down [--cwd PATH] [--env K=V] [--no-focus]` then `herdr agent start <NAME> --kind <KIND> --pane <ID> [--timeout MS] [-- AGENT_ARG...]`; no single spawn verb | herdr-help.txt "pane split --help", "agent start --help" | verified | herdr version ≠ 0.9.0 |
| HR-02 | `agent start` returns only after the agent is detected and ready; blocked at startup → `agent_not_ready`; default timeout 30 s, max 300 s | `herdr --skill` line 201; agent start --help | verified | herdr version ≠ 0.9.0 |
| HR-03 | The initial prompt is not a start flag; send it after start with `herdr agent prompt <TARGET> <TEXT> --wait` | agent start --help "next: herdr agent prompt …" | verified | herdr version ≠ 0.9.0 |
| HR-04 | Agent kinds: pi, claude, codex, gemini, cursor, devin, agy, cline, omp, mastracode, opencode, copilot, kimi, kiro, droid, amp, grok, hermes, kilo, qodercli, qwen, maki, muse | agent start --help `[possible values: …]` | verified | herdr version ≠ 0.9.0 |
| HR-05 | Extra CLI flags reach the agent through `-- AGENT_ARG…` (e.g. `-- -m gpt-5.6-sol -c model_reasoning_effort=high`); herdr adds no permission-bypass flag of its own | agent start --help; handoff-P1aHuF.md:24 (worked in the source session); grep yolo/dangerously in help = 0 | verified (flag passthrough) / inferred (no default bypass) | herdr version ≠ 0.9.0 |
| HR-06 | Send: `herdr agent prompt <TARGET> <TEXT> [--wait] [--until idle\|working\|blocked\|done\|unknown]* [--timeout MS]`; rejected with `agent_blocked` if the agent sits at an approval/question UI; `agent_prompt_stalled` if no working/blocked state within 5 s | agent prompt --help | verified | herdr version ≠ 0.9.0 |
| HR-07 | `--wait` tracks lifecycle state, not turns: if the agent is already working, the active turn's end may satisfy it | agent prompt --help last sentence | verified | herdr version ≠ 0.9.0 |
| HR-08 | Wait: `herdr agent wait <TARGET> [--until STATE]* [--timeout MS]`; default matches idle, done or blocked; no timeout = indefinite | agent wait --help | verified | herdr version ≠ 0.9.0 |
| HR-09 | States: `idle`/`done` = ready for input (done = unseen completion); `blocked` = approval or question UI recognised; `unknown` = present but unclassified, not proof of completion | `herdr --skill` line 135 | verified | herdr version ≠ 0.9.0 |
| HR-10 | State for claude/codex comes from herdr-installed hooks: `~/.claude/hooks/herdr-agent-state.ps1` (SessionStart hook in user settings.json, integration v9) and `~/.codex/herdr-agent-state.ps1` (v8), which call `herdr pane report-agent … --state …` | `herdr integration status`; settings.json hooks; script header | verified | `herdr integration` reinstall |
| HR-11 | Read: `herdr agent read <TARGET> [--source visible\|recent\|recent-unwrapped\|detection] [--lines N] [--format text\|ansi]` — a terminal snapshot, not a transcript | agent read --help | verified | herdr version ≠ 0.9.0 |
| HR-12 | Close: `herdr pane close <pane_id>`; no `pane kill` or `agent stop` verb exists | pane close --help; `pane kill --help` falls through to the command list | verified | herdr version ≠ 0.9.0 |
| HR-13 | `herdr agent list` JSON carries per pane: `agent`, `agent_status`, `name`, `pane_id`, `cwd`, `interactive_ready`, and `agent_session.value` = the harness's own session id (Claude UUID, Codex thread UUID) | `herdr agent list` output this session (e.g. pane w5:p2 → `833e367f-…`, this session) | verified | herdr version ≠ 0.9.0 |
| HR-14 | Because HR-13 exposes the Claude session id, a closed pane's history can be resumed later with `claude --resume <id>` (headless or interactive) | HR-13 + CN-08 | inferred | either side changes |
| HR-15 | Notifications: pane → human only, `herdr notification show <title> [--body] [--position] [--sound none\|done\|request]`; no pane-to-pane notify | notification --help | verified | herdr version ≠ 0.9.0 |
| HR-16 | Pane-to-pane messaging = `agent prompt` (typed text arrives as a user turn); Codex → Claude worked in the source session | handoff-P1aHuF.md:25-26 | verified (source session) | herdr version ≠ 0.9.0 |
| HR-17 | Worktrees: `herdr worktree create [--workspace ID \| --cwd PATH] [--branch NAME] [--base REF] [--path PATH] [--label] [--no-focus] [--trust-repository]`, plus list/open/remove; opens the worktree as a new workspace | worktree create --help; `--skill` line 274 | verified | herdr version ≠ 0.9.0 |
| HR-18 | Env inside a pane: `HERDR_ENV=1`, `HERDR_PANE_ID` (w5:p2), `HERDR_TAB_ID` (w5:t1), `HERDR_WORKSPACE_ID` (w5), `HERDR_SOCKET_PATH`, `HERDR_BIN_PATH`; detection recipe in the skill guide is `test "${HERDR_ENV:-}" = 1` | `env \| grep HERDR` this session; `--skill` line 89 | verified | herdr version ≠ 0.9.0 |
| HR-19 | Addressing: `w<N>:p<N>` panes, `w<N>:t<N>` tabs, `w<N>` workspaces; ids are server-scoped and never reused; parse ids from JSON, never predict | `--skill` lines 121,143-145,167,272 | verified | herdr version ≠ 0.9.0 |
| HR-20 | All control commands return JSON; server errors are JSON on stderr exit 1; syntax errors exit 2; `herdr api snapshot` dumps the live session, `herdr api schema` the socket API | `--skill` lines 121,278; api --help; `herdr api snapshot` ran | verified | herdr version ≠ 0.9.0 |
| HR-21 | Prompt-size submit delay grows for Codex on Windows; large briefs should go by file, prompt carries the path | `--skill` line 209 | verified | herdr version ≠ 0.9.0 |
| HR-22 | Codex's default sandbox blocks `herdr` socket calls (PermissionDenied) and asks approval per call; a Codex peer that must talk back needs `--dangerously-bypass-approvals-and-sandbox` or an approval per message | handoff-P1aHuF.md:27 | verified (source session) | codex version ≠ 0.154.0 |
| HR-23 | herdr ships no first-run flag; config `onboarding = false` in `%APPDATA%\herdr\config.toml` suppresses its own onboarding | config.toml read; help grep | verified | herdr version ≠ 0.9.0 |
| HR-24 | herdr is a plain executable (`~/.herdr/packages/standalone/releases/<ver>/herdr.exe`), self-updating (`herdr update`), with a headless `herdr server` mode and SSH `--remote` | `Get-Command herdr`; `herdr --help` | verified | herdr version ≠ 0.9.0 |
| HR-25 | Live team right now: contact w5:p1 (claude, idle), planner-claude w5:p2 (this session), planner-codex w5:p3 (codex, working); stale peers w2:p1/w2:p3 (core-services) and w4:p1 | `herdr agent list` | verified | end of this session |

## DT — 1DevTool as a transport

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| DT-01 | Shim `~/.1devtool/bin/1devtool-agent-v9.cmd` runs the desktop app's Electron binary as Node (`ELECTRON_RUN_AS_NODE=1 "C:\Program Files\1DevTool\1DevTool.exe" …\dist\cli\1devtool-agent.cjs`) | shim contents | verified | 1DevTool update |
| DT-02 | Spawn: `1devtool-agent run --to=<agent> --prompt-stdin [--cwd DIR] [--model ID] [--terminal] [--json]` → `runId` (headless) or `runId`+`teamId` (`--terminal`) | ~/.claude/skills/1devtool-orchestrator/SKILL.md:71,131-165; help line 119 | unverified (doc, not executed) | 1DevTool update |
| DT-03 | Write-category runs auto-provision a git worktree unless `--shared-cwd` | orchestrator SKILL.md:147-151 | unverified (doc) | 1DevTool update |
| DT-04 | Kill: `stop --team=<id>\|--swarm=<id> [--close-terminals\|--finish-running]`; `terminal close --id` refuses live orchestration seats | help lines 13-15,80-81; SKILL.md:208-210 | verified (help text) | 1DevTool update |
| DT-05 | Send: `team send --team --to=<memberId> --submission-id=<uuid> --prompt-stdin`; `link send --to=<terminalId>` for linked terminals | help lines 32,40,52 | verified (help text) | 1DevTool update |
| DT-06 | Wait/collect: `collect --run=<id> [--timeout]`, `collect --swarm`; `run` and `run --terminal --wait` block until done; `resolve --run --outcome=done\|error\|cancelled` settles "needs confirmation" | help lines 67-78; SKILL.md:98,125,162-166,200-207 | verified (help text) | 1DevTool update |
| DT-07 | Team = hierarchical named members with roles/prompts via `team start --manifest-stdin` `{clientRequestId, members:[{role,target,prompt,substrate}]}`; swarm = flat isolated workers with one `brief`, no inter-worker messaging; headless workers limited to codex, claude, cursor | SKILL.md:78-123,255-260 | unverified (doc) | 1DevTool update |
| DT-08 | Hierarchy: `report --prompt-stdin [--blocked] [--wait]` to one manager, `whoami` shows seat/manager/subordinates; links need in-app human approval | SKILL.md:180-234,330-358 | unverified (doc) | 1DevTool update |
| DT-09 | Agent kinds: claude, codex, gemini, kimi, agy, cline, amp, opencode, qwen, grok, hermes, cursor, pi, omp, kiro, devin, aider | help line 84 | verified | 1DevTool update |
| DT-10 | `list --json` reports codex and claude as `unverified` with resolved exe paths, others `not-found` — "installed" only, no login check | `1devtool-agent-v9.cmd list --json` | verified | machine change |
| DT-11 | Needs the desktop app and an attributed terminal: from this Bash session `whoami` → `{"session":false,"message":"not a 1DevTool session"}`, `team capabilities` → "No compatible 1DevTool instance owns the calling terminal"; attribution is PTY ancestry, not an env var; `run`, `list`, `terminal *` work unattributed | commands run; help lines 86-92 | verified | 1DevTool update |
| DT-12 | 1DevTool injects the permission-bypass flag per target itself; callers must not pass `--dangerously-*`/`--yolo` | help lines 94-99; SKILL.md:212-217 | verified (help text) | 1DevTool update |
| DT-13 | Routing table = markdown table `Category \| Delegate to \| Model \| Substrate \| Notes` inside the user-level skill; on this machine plan/implement/test/docs/research/debug → codex, review → claude | orchestrator SKILL.md:289-317 | verified | skill file edit |
| DT-14 | `tasks_*` MCP tools are a human-dispatched task queue, not an agent spawner; optional, never blocks direct prompts | ~/.claude/skills/1devtool-tasks/SKILL.md:13-124 | verified | skill file edit |
| DT-15 | State on disk: `~/.1devtool/{bridges/<instance>.json (host/port/pid), orchestration/{control,runs,runtime}, state/{agent-models.json,cli-registry.json}, mcp-bridge-port}` | `ls ~/.1devtool` | verified | 1DevTool update |
| DT-16 | No `ONEDEV*`/`1DEV*`/`DEVTOOL*` env var in this session; detection from inside a 1DevTool terminal must use `whoami` (`session:true`) | env dump; DT-11 | verified (this session) / inferred (spawned terminals not inspected) | 1DevTool update |
| DT-17 | Answer to goal 8: 1DevTool can spawn (`run`, `team start`) and kill (`stop --close-terminals`) agents like herdr, but only from an app-attributed terminal for team ops; unattributed `run` still works | DT-02, DT-04, DT-11 | inferred (not executed) | first executed probe |

## CN — Claude-native options (Claude Code 2.1.272)

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| CN-01 | Agent tool subagents: fresh context (non-fork) or full inheritance (fork); foreground or background with completion notification; `isolation: worktree`; resumable via SendMessage; nesting depth 3 (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`) | code.claude.com/docs/en/sub-agents.md | verified (docs) | Claude Code release |
| CN-02 | Agent teams (experimental, `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`): teammates are separate Claude Code instances, own model each, SendMessage mailbox, graceful shutdown by name; one team per session, no nested teams, no background subagents from teammates | code.claude.com/docs/en/agent-teams.md | verified (docs) | Claude Code release |
| CN-03 | Headless: `claude -p` exits 0/1, `--output-format json\|stream-json`, `--json-schema`, `--max-turns`, `--max-budget-usd`, `--model`, `--effort`, `--permission-mode`, `--allowedTools`, `--append-system-prompt`, `--agents <json>`, `--bare`, `--no-session-persistence`, `--session-id <uuid>`, `--resume <id>`, `--fork-session`, `-w/--worktree` | `claude --help` this session | verified | Claude Code release |
| CN-04 | A `-p` run prints `session_id` in its init event; the same id resumes later, headless or interactive, from any directory | `claude -p … --output-format json` output (`"session_id":"9c539e8f-…"`); docs headless.md | verified | Claude Code release |
| CN-05 | Background sessions: `claude --bg [--resume id]` returns immediately and prints an id; `claude agents --json [--cwd PATH] [--all]` lists sessions `{pid,cwd,kind,startedAt,sessionId,name,status}`; `claude attach\|logs\|stop\|rm <id>`; `stop` keeps the conversation, `rm` deletes session + worktree | `claude --help`, `claude agents --help`, `claude agents --json` output | verified | Claude Code release |
| CN-06 | Cross-session messaging: every session has a name (`afk-driver-agent-teams-d5`); ListAgents shows peer sessions on this machine with idle/busy; SendMessage addresses them by name; socket `CLAUDE_CODE_MESSAGING_SOCKET` + token env vars | ListAgents output; env dump | verified | Claude Code release |
| CN-07 | Env a child sees: `CLAUDECODE=1`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_ENTRYPOINT=cli`, `CLAUDE_PID`, `CLAUDE_EFFORT`, `CLAUDE_CODE_SESSION_ATTENDED=1`, `CLAUDE_CODE_CHILD_SESSION=1` | env dump this session | verified | Claude Code release |
| CN-08 | `CLAUDE_CODE_CHILD_SESSION=1` marks a session started under another Claude session (this one was started by the contact agent) | env dump; not documented | inferred | Claude Code release |
| CN-09 | Hooks: SubagentStart/SubagentStop/Notification exist; TeammateIdle/TaskCreated/TaskCompleted for teams; stream-json subagent messages carry `parent_tool_use_id` | docs hooks-guide.md, agent-teams.md, headless.md | verified (docs) | Claude Code release |
| CN-10 | First-run dialogs: `-p` shows no trust dialog and no per-server MCP approval; interactive sessions ask per project path; `enableAllProjectMcpServers` / `enabledMcpjsonServers` (settings or per-project in `~/.claude.json`) pre-approve; `--no-chrome` disables the Chrome integration prompt | `claude --help` lines 164-173; docs settings-reference.md; `~/.claude.json` keys | verified | Claude Code release |
| CN-11 | Cause of the contact agent's dialogs: the worktree path has no `projects` entry in `~/.claude.json` (no `hasTrustDialogAccepted`, empty `enabledMcpjsonServers`), and this repo ships a project `.mcp.json` (server `tracker`); `cachedChromeExtensionInstalled=true` with `claudeInChromeDefaultEnabled=false` explains the Chrome prompt | `~/.claude.json` read; `.mcp.json` read | verified (state) / inferred (causation) | dialogs accepted once |
| CN-12 | Auth probe: `claude auth status` → JSON `{loggedIn, authMethod:"claude.ai", apiProvider:"firstParty"}` exit 0; `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`) serve unattended runs | command output; docs authentication.md | verified | Claude Code release |
| CN-13 | Live probe cost: `claude -p "Reply with exactly: OK" --max-turns 1 --model haiku --output-format json` took 9.1 s wall, exit 0, in this cwd | timed run this session | verified | machine/network change |
| CN-14 | Model aliases: best, fable, opus, sonnet, haiku, opusplan, `*[1m]`; full ids `claude-fable-5-1`, `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5`; effort low/medium/high/xhigh/max/ultracode via `--effort` | docs model-config.md | verified (docs) | model release |
| CN-15 | The plugin's harness-shared hook set (PL-21) excludes SubagentStop, so a child-finished trigger must be a script exit (watchdog) or the spawning call's return, not a hook | PL-21 + CN-09 | inferred | CAPABILITIES.md edit |

## CX — Codex CLI as a provider (codex-cli 0.154.0)

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| CX-01 | Headless: `codex exec [PROMPT\|-] -m MODEL -s read-only\|workspace-write\|danger-full-access [-C DIR] [--worktree] [--json] [-o FILE] [--ephemeral] [--skip-git-repo-check] [--dangerously-bypass-approvals-and-sandbox]`; `codex exec resume <id>` / `fork <id>` | `codex exec --help` | verified | codex version ≠ 0.154.0 |
| CX-02 | Session ops: `codex agents` (sessions on the app-server daemon), `codex queue --thread <uuid\|name> --message TEXT` (send to a running session), `codex resume`, `codex fork`, `codex app-server daemon` | `codex --help`, `codex queue --help` | verified | codex version ≠ 0.154.0 |
| CX-03 | Auth probe: `codex login status` → "Logged in using ChatGPT" exit 0 | command output | verified | logout |
| CX-04 | Live probe: `codex exec --skip-git-repo-check -s read-only "Reply with exactly: OK"` took 19.6 s, exit 0, printed `OK`, 18,541 tokens; SessionStart and Stop hooks fired (hooks feature stable, enabled) | timed run; `codex features list` (`hooks stable true`) | verified | machine/network change |
| CX-05 | `codex doctor` exists (installation, config, auth, runtime health) — a candidate one-shot availability probe | `codex --help` | verified (existence) | codex version ≠ 0.154.0 |
| CX-06 | Model slugs in the source session: gpt-6-astra, gpt-5.6-sol, gpt-5.6-terra, gpt-5.6-luna, gpt-5.5 (`codex debug models`) | handoff-P1aHuF.md:23 | unverified (not re-run) | model release |
| CX-07 | Sandbox modes read-only / workspace-write / danger-full-access; `-a/--ask-for-approval` policy; `--approve-for-me` routes approvals through automatic review | `codex --help` lines 88-115 | verified | codex version ≠ 0.154.0 |

## EV — environment detection facts (this machine)

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| EV-01 | A Claude session inside herdr sees both `HERDR_*` and `CLAUDE*` vars; a plain terminal sets neither `HERDR_ENV` nor 1DevTool attribution | env dump; DT-16 | verified | herdr/Claude release |
| EV-02 | Three harness/terminal layers are separable: harness (CLAUDECODE / PLUGIN_ROOT, PL-24), terminal tool (HERDR_ENV; 1DevTool `whoami`), provider CLIs (`claude`, `codex` on PATH) | PL-24, HR-18, DT-11, `--version` runs | verified | any release |
| EV-03 | Peer Claude sessions visible from here: 11 interactive sessions, 2 in this worktree (`afk-driver-agent-teams-ef` = contact w5:p1 session `96c58aef…`, `-d5` = this) | ListAgents; `claude agents --json --cwd` | verified | sessions end |
| EV-04 | herdr's user-level Claude hook (HR-10) lives outside the plugin's opt-in boundary: a plugin feature must not depend on it being installed; `herdr integration status` is the probe | HR-10; PROVIDERS.md:39-45 | inferred | herdr integration change |

# Adversary report — 0013-provider-layer-codex

- Date: 2026-10-21
- Target: `cli:C:/Users/mvu/PersonalProjects/afk-driver-agent-teams` (plan decision D-40: the running system is the plugin's documents, agent files and command-line gates)
- System under attack: `PROVIDERS.md` section "Model tiers", fallback paragraph (line 138), and the 5 Codex agent stubs `providers/codex/agents/afk-afk-*.toml`, in an archive copy of HEAD
- Verdict: `findings` — 19 scenarios probed; 0 critical, 0 high, 1 medium, 3 low

## Method and deviations

| Item | What ran | Deviation from the brief |
|---|---|---|
| HEAD copy | `git -c core.autocrlf=false archive HEAD \| tar -x` into a scratch folder | The plain `git archive` copy came out with CRLF line ends (local autocrlf), so a second copy keeps the committed bytes |
| Tier gate (native check L) | The gate's own embedded Python scan (`hooks/native-contract-gate.sh` lines 58-770, extracted verbatim), run with the copy as the plugin directory | The session's protected-branch guard refused `git add` in the scratch copy. Without a git repository, `bash hooks/native-contract-gate.sh` exits 0 at line 793 before any check runs, so a direct run proves nothing |
| Codex probes | `codex exec --json --skip-git-repo-check -s read-only -C <copy> "<prompt>"`, codex-cli 0.163.0, scratch `CODEX_HOME` per scenario holding resolved stub copies | The session's permission classifier denied `--dangerously-bypass-approvals-and-sandbox`. The read-only sandbox was enough, because each child only replies with fixed text. Each copied `auth.json` was deleted after its run; none remain |

## Findings (most severe first)

### F1 — medium — spec — with team topology off, the substitute model has no way to run

- Promise: "The rule works whether team topology is on or off" (contract `## Acceptance`, PRD AC-002); the equivalent is "the same tier row in another harness column" (SDD §8 row "Model equivalence").
- Observed: a harness cannot run the model in the other harness column. The rule sentence (PROVIDERS.md:138) names no way to reach another harness when no team runs.
- Repro (Codex session, Claude Code column cell of any tier):
  ```
  CODEX_HOME=<scratch home with auth.json> codex exec --json --skip-git-repo-check -s read-only -m opus -C <copy> "Reply with the exact text OK." < /dev/null
  ```
  - Actual: exit 1, `turn.failed` with status 400: `The 'opus' model is not supported when using Codex with a ChatGPT account.`
  - Expected: a single-model role on a failed provider continues on the other column's model, with team topology on or off.
- Inference: with team topology on, a pane or headless agent of the other harness can run that model. With it off, only the active harness's own subagents exist (`GLOSSARY.md` "Transport": "With none available, a pattern runs on the harness's own subagents"). The sentence's first clause ("if that harness cannot drive it, use the nearest capability-compatible model") then points back to the failed provider. The contract `## Goal` puts the run-time pick in the team skill. No document in my allowed reading names the topology-off route: unverified, because other skills were outside the information diet.

### F2 — low — robustness — a missing or duplicate stub name silently brings back "unknown agent type", and no gate notices

- Promise: "after the rename a skill's spawn of `afk-reader` no longer fails as an unknown agent type" (SDD §9b row "Codex agent lookup"). The contract states "no gate reads the name field" (SDD §14 row "Codex agent stubs' name field"), so this finding states what that posture costs; the slice holds to it.
- Repro A (name line removed from `afk-afk-reader.toml`):
  - Gate scan on the mutated copy: exit 0, no problem lines.
  - Codex: spawn `afk-reader` gives `unknown agent_type 'afk-reader'`; spawn `afk-runner` still gives `CHILD-OK`. Codex writes no warning about the nameless file at startup (stderr holds only the router error).
- Repro B (`afk-afk-runner.toml` name set to `afk-reader`, a duplicate):
  - Gate scan: exit 0.
  - Codex: spawn `afk-reader` resolves to the reader body (child rollout holds `agents/afk-reader.md`); spawn `afk-runner` gives `unknown agent_type 'afk-runner'`. The runner role disappears with no message.
- Expected for a lifted check: a stub whose `name` differs from its Agent table row (PROVIDERS.md:147-153) is refused, the same way check L refuses a model that differs from its tier cell.

### F3 — low — spec — the park report loses two of its three named fields, and the wait term changes

- Promise: "Beyond the provider's wait horizon the run parks and writes a dated report naming the provider, the role and the time it parked" (PRD AC-023).
- Observed (PROVIDERS.md:138): "a wait past the provider's limit parks the run with a dated report". The sentence does not name the provider or the role in the report. It writes "limit" where the PRD writes "wait horizon", in a sentence that also says "quota check", so a reader can take "limit" as a quota limit (`LANGUAGE.md` §2: one term, one meaning).
- Repro: `sed -n '138p' PROVIDERS.md | grep -o -E 'limit|horizon|dated report[^;.]*'` gives `limit` and `dated report instead of continuing in a reduced shape`; `horizon` is absent.
- Expected: the sentence keeps "wait horizon" and the three report fields, or points at the home that owns the report shape.

### F4 — low — spec — a substitute in the Codex CLI column gets no effort value

- Promise: the equivalent model is "the same tier row in another harness column", found by a read of the tier map (SDD §8 row "Model equivalence").
- Observed: the tier row has 3 cells after the tier name (PROVIDERS.md:140): `Claude Code`, `Codex CLI`, `Codex effort`. The sentence says to take the cell "where that cell names a model". It does not say to take the `Codex effort` cell with it. A Claude Code role that moves to the Codex CLI column has no stated effort, and every stub carries one (`model_reasoning_effort`, checked by check L).
- Repro: read PROVIDERS.md:138 and :140-145; no part of :138 names effort.
- Expected: the sentence takes the whole tier row (model and effort) of the other harness.

## Scenarios that held

| # | Promise | Scenario | Result |
|---|---|---|---|
| 1 | Check L gives 0 problems (SDD §14 "`Model tiers` table") | Gate scan on the HEAD copy | exit 0 |
| 2 | Check L still reads the tables | Reader stub `model` set to `gpt-wrong` | exit 2: `afk-afk-reader.toml: model expected 'gpt-5.6-terra' (tier Digest)` |
| 3 | Check L reads tier rows after the new sentence | Digest Codex cell set to `gpt-x` | exit 2: reader and runner stubs flagged |
| 4 | No gate reads the name field (as declared) | Name line removed; name changed | exit 0 both |
| 5 | Sentence holds no column bar, no `##` start, no ticket-shaped or model-name token | grep of line 138 | 0 bars, 0 headings, 0 tokens |
| 6 | Spawn by skill name (SDD §9b) | Codex spawn `afk-reader` | `CHILD-OK`; child `agent_role` `afk-reader`, model `gpt-5.6-terra`, effort `medium` (Digest row) |
| 7 | Old doubled name is gone | Codex spawn `afk-afk-reader` | `unknown agent_type 'afk-afk-reader'` |
| 8 | Filenames stay `afk-afk-*.toml` | `ls providers/codex/agents/` | 5 files, all `afk-afk-*.toml`; each `name` is the skill name |
| 9 | Single-model role continues on another column (AC-022) | Text of :138 | Stated |
| 10 | Debate role waits (AC-022) | Text of :138 | Stated |
| 11 | No other column names a model | Text of :138 | Waits; stated |
| 12 | The substitute's provider fails too | Text of :138 | Waits; stated |
| 13 | No check before a call (AC-020) | Text of :138 | Stated; the sentence adds no step before a call |
| 14 | Ordered against the in-harness fallback | Text of :138 | "After that fallback" |
| 15 | No reduced shape (AC-023) | Text of :138 | Stated |

## Not reported (hypotheses without a runtime repro)

- PROVIDERS.md:159 lets a simple slice run on `sonnet` instead of the Implementation cell. The sentence does not say which tier row is "the same tier row" for such a spawn: Implementation or Digest.
- PRD AC-002 names 2 switches. The sentence names team topology only. With multi-model off, a cross-provider substitute gives a role to a second provider; the sentence does not say whether that is allowed.
- Pre-existing, outside the slice: `bash hooks/native-contract-gate.sh` outside a git repository exits 0 with no output (line 793), which reads as a pass.

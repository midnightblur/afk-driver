# Converge brief — round 3

You are a fresh planner. The two planners who did rounds 1 and 2 are closed. Their knowledge is on disk in this folder. You work only from these files; that is a deliberate test that the knowledge survives the closed agents. Read `CLAUDE.md` at the repo root first — it is binding. Follow `LANGUAGE.md` §3 for artifact prose.

## Inputs (this folder)

`BRIEF.md` (the human's goals), `FACTS-claude.md`, `FACTS-codex.md`, `PROPOSAL-claude.md`, `PROPOSAL-codex.md`, `CRITIQUE-claude.md` (Claude side's objections to the Codex proposal), `CRITIQUE-codex.md` (Codex side's objections to the Claude proposal). Also `../GRILL-LOG.md` (human rulings so far; a human ruling is final, never re-argue it).

## Your side

- `debater-fable` speaks for `PROPOSAL-claude.md` and must answer every objection in `CRITIQUE-codex.md` section A.
- `debater-astra` speaks for `PROPOSAL-codex.md` and must answer every objection in `CRITIQUE-claude.md` section a.

Speaking for a side means owning its reasons, not winning. Concede when the objection is right.

## Step 1 — `RESPONSE-<side>.md` (side = `claude` or `codex`)

One row per objection raised against your side:

| obj | verdict: accept / reject / compromise | reason + fact ids | resulting position, one sentence |

Then one row per open dispute in the list below, with your side's final position and the fact ids it rests on. Re-check any fact you lean on if it is cheap to check; record what you ran.

Open disputes:
1. Availability probe: may the default check spend a real generation call?
2. Topology values: does a strict single-agent value exist beside today's behaviour?
3. A provider the user named fails: fall back to another provider, or stop?
4. Phase 1 scope: the smallest first delivery.
5. Knowledge store: spec folder only, or also a cross-feature catalog? Does it survive `/afk:gc`?
6. What "verified" means for a stored fact: evidence still checks, or the conclusion re-confirmed?
7. The `hierarchy` pattern: built in now, or deferred?

Reply in your terminal with one line: `STEP1 <path>`. Then wait.

## Step 2 — `VERDICT-<side>.md`

When the contact agent says "step 2", read the other side's `RESPONSE-*.md`. For every objection and every dispute, write one row:

| id | AGREE / DISAGREE-FINAL | the agreed position, or both final positions | reason |

- AGREE needs a reason. A bare AGREE is invalid.
- DISAGREE-FINAL means further discussion cannot settle it: the choice rests on a value, a cost trade, or a policy only the human can set. Name that value in one sentence. A disagreement that more evidence could settle is not final — name the check that would settle it instead.

Step 2 adds one dispute that step 1 did not have. Give it a row in your VERDICT file like any other dispute:

8. Usage limits: the human wants agents that detect a provider's usage limit, save state, learn the reset time, and resume on their own after the reset, with no human watching. Facts: `FACTS-quota.md`. Rule on what the plugin must promise (detect, park, wake, resume, or re-route to another provider) and where it must stop and ask the human.

Reply in your terminal with one line: `STEP2 <path>`.

## Rules

- Write only your own two files in this folder. No plugin source edits, no commits, no pushes.
- Probes: read-only commands freely. Anything that starts an agent must be bounded, trivial, and cleaned up.
- Every file you write must be cited by name in your own VERDICT file.

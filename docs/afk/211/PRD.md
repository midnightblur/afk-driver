# PRD — 211: /afkv2:dogfood

## Problem Statement

The developer uses afkv2 for real work in another repository. During that work, the developer finds that afkv2 needs a new capability, or that an existing one does not work the way they want. Today an afkv2 change must be released, reinstalled and loaded in a new session before the developer can use it in real work. So the developer stops the main work to build the change, and can try and refine it only after a release.

## Solution

`/afkv2:dogfood` opens an **afkv2 agent** in a side pane next to the developer's session of the real work (the **main agent**). The afkv2 agent builds the afkv2 change in parallel, in a worktree of the plugin's source repository. The developer talks to it directly in its pane. The main work never waits for it.

Each time the change reaches a **milestone**, the afkv2 agent sends a **milestone note** to the main agent: what changed, where the changed files are, and how to use them. The main agent applies the change ad hoc, at once, with no release, no reinstall and no reload. It tells the developer what it applied and how to try it. The developer tries the change in the real work and gives feedback in either pane. The afkv2 pane stays open and takes new asks until the main work is done.

Terms (`afkv2/GLOSSARY.md`): afkv2 agent, main agent (dogfood), milestone, milestone note, apply ad hoc, earliest convenience.

## Catalog

How each kind of afkv2 change applies in the main session.

| Id | Change kind | How the main agent applies it |
|----|-------------|-------------------------------|
| CK-1 | a changed or new skill | reads the skill instructions from the worktree and follows them in place of the installed copy, for the rest of its session |
| CK-2 | a changed or new script of a skill | runs it from the worktree, through the skill instructions of CK-1 |
| CK-3 | a change to the core behaviors | reads the changed text and follows it as a session instruction |
| CK-4 | a change to a hook or to the hook registration | best effort: it may not apply in this session; the main agent tells the developer so |

## User Stories

1. As a developer, I want to ask for an afkv2 change from my work session and keep working, so that the main work never waits for the plugin work.
2. As a developer, I want each milestone applied in my work session at once and told how to try it, so that I can use the change in real work before any release.
3. As a developer, I want to give feedback on a trial in either pane, so that the afkv2 agent refines the change with the evidence of the trial.
4. As a developer, I want to give a new ask while the afkv2 pane runs, so that one pane serves every afkv2 need of the main work.
5. As a developer, I want the pane to wrap up when the main work is done, so that no plugin work is lost and no pane stays open.

## Acceptance Criteria

Start and refusals:

- [ ] AC-001 The developer runs `/afkv2:dogfood` with an ask in a main session inside herdr, with the source line in the install record → a new pane opens beside the main pane, and an afkv2 agent starts in it on a plugin worktree with the ask.
- [ ] AC-002 The main session is outside herdr (the herdr environment flag is not 1, or herdr is not on the path) → the skill starts nothing and tells the developer the reason and the repair: start herdr and run the skill again.
- [ ] AC-003 The install record has no source line → the skill starts nothing and names `/afkv2:setup` as the fix.
- [ ] AC-004 The main session already has an afkv2 pane open → a new ask goes to that afkv2 agent; no second pane opens.
- [ ] AC-005 The afkv2 agent runs at the implementor role of the model routing (ticket 204) once that routing exists; until then it runs as Claude Opus at the highest effort with full auto-approval.

Setup:

- [ ] AC-006 `/afkv2:setup` finds a likely plugin source checkout → it suggests that path and asks the developer to confirm it or type another path; setup finds none → it asks for a path.
- [ ] AC-007 The developer confirms or types a path that is a main checkout of the plugin's source repository → setup writes the source line with that path to the install record.
- [ ] AC-008 The developer gives a path that is a linked worktree, or not a checkout of the plugin's source repository → setup writes no source line and says why.

The work in the afkv2 pane:

- [ ] AC-009 A small ask runs through `/afkv2:small-change` in the afkv2 pane; an ask that needs a feature runs through `/afkv2:grill-requirements` and the medium lane.
- [ ] AC-010 Small asks of one pane session share 1 branch and 1 Draft change into the plugin's integration branch; the Draft change gives each ask its own section.
- [ ] AC-011 An ask that needs the medium lane gets its own branch.
- [ ] AC-012 A new ask arrives while an earlier ask is not yet at a milestone → the afkv2 agent queues it, tells the developer in its pane, and starts it when the earlier ask reaches its milestone.
- [ ] AC-013 The afkv2 agent writes nothing in the work repository and never merges a change.

Milestone notes:

- [ ] AC-014 The afkv2 agent judges a committed change usable for 1 named purpose → it sends a milestone note to the main agent at once, as a prompt, without asking the developer. (unverified premise: text typed into a working Claude or Codex agent is queued until the turn ends; Ctrl+Enter sends it at once)
- [ ] AC-015 Every milestone note names at least 1 changed file by its worktree path, how to use the change, and each part of the change that is of kind CK-4.
- [ ] AC-016 The afkv2 agent knows that work the main agent already did under the old text would come out differently → the note names that delta.
- [ ] AC-017 The afkv2 agent sends prompts only to the main agent's pane, never to another pane.

Apply in the main session:

- [ ] AC-018 The main agent receives a milestone note → it applies each change at once by its kind in the catalog, without asking the developer, and tells the developer what it applied and how to try it.
- [ ] AC-019 The note changes a skill that the main agent is running → from receipt on, the main agent follows the new text for the rest of that skill run, and says so.
- [ ] AC-020 Work the main agent already did under the old text would come out differently under the new text → the main agent redoes that delta at once, without asking, and tells the developer what it redid.
- [ ] AC-021 A note holds a change of kind CK-4 → the main agent tells the developer that this part is best effort and may not apply in this session.
- [ ] AC-022 The main agent writes no plugin file.
- [ ] AC-023 A received note names no worktree path or no way to use the change → the main agent applies nothing from it and asks the afkv2 agent for a complete note.
- [ ] AC-024 The applied changes last only for the main session; the installed plugin does not change.

Feedback:

- [ ] AC-025 The developer gives feedback on a trial in the main pane → the main agent sends it to the afkv2 agent with the evidence it saw (errors, output).
- [ ] AC-026 The developer gives feedback in the afkv2 pane → the afkv2 agent takes it with no step from the main agent.

The end:

- [ ] AC-027 The developer tells the main agent that the main work is done → the main agent asks the afkv2 agent to wrap up; the afkv2 agent commits, pushes each Draft change and reports the open asks; then the main agent closes the afkv2 pane.
- [ ] AC-028 After the wrap-up, the worktrees and branches stay; nothing is deleted.
- [ ] AC-029 The afkv2 pane stays open after each milestone and each result, until the wrap-up of AC-027.

## Worked examples

### WE-01 — frequent: a clearer step in a skill

| Step | Data | Result |
|------|------|--------|
| Ask | in the core-services work, the developer tells the main agent: "step 4 of small-change is unclear" | the main agent sends the ask to the afkv2 agent; the main work goes on |
| Build | the afkv2 agent edits step 4 of the small-change skill in its worktree, commits | milestone |
| Note | "changed: `<worktree>/afkv2/skills/small-change/SKILL.md` step 4; use it at your next small change" | queued until the main agent's turn ends |
| Apply | the main agent receives it | "applied the small-change update; your next small change uses it" |

### WE-02 — edge: a second ask while the first is half built

| Step | Data | Result |
|------|------|--------|
| Ask 1 | "add a link to the ticket on the review page" | the afkv2 agent works on it |
| Ask 2 | "the gc refusal text is unclear", while ask 1 has no milestone | the afkv2 agent queues ask 2 on the same branch and tells the developer in its pane |
| Milestone 1 | ask 1 committed and usable | note to the main agent; the afkv2 agent starts ask 2 |

### WE-03 — risky: a milestone changes the skill the main agent runs right now

| Step | Data | Result |
|------|------|--------|
| State | the main agent is at step 6 of a small change; steps 1 to 5 ran under the old text | — |
| Note | the new text changes how step 3 writes the test plan, and changes a hook | queued until the current turn ends |
| Apply | the main agent receives it | it follows the new text from now on, redoes the test plan of step 3 by the new text at once, and tells the developer what it redid; it says the hook part is best effort and may not apply in this session |

## Access & validation policy

| Capability | Permitted | Denied | Data scope | Validation |
|------------|-----------|--------|------------|------------|
| Start the skill, end the pane | developer | — (everyone in the session may) | unscoped | refuses outside herdr; refuses without the source line |
| Build the afkv2 change | afkv2 agent | main agent | the afkv2 agent's plugin worktree | writes nothing in the work repository; never merges |
| Send milestone notes | afkv2 agent | prompting any pane but the main agent's | the main agent's pane | each note names at least 1 worktree path and 1 way to use it; a CK-4 part says best effort |
| Apply a milestone | main agent | writing any plugin file | reads the plugin worktree only | applies only a note with a worktree path and a way to use it |
| Give feedback | developer, in either pane | — | unscoped | — |

## Implementation Decisions

- Ad hoc apply with no release, reinstall or reload: [ADR-0001](adr/requirements/0001-ad-hoc-apply-no-reload.md).
- The latest instruction always wins, and the main agent redoes the delta without asking: [ADR-0002](adr/requirements/0002-latest-instruction-wins.md).
- 1 branch per pane session for small asks: [ADR-0003](adr/requirements/0003-one-branch-per-pane-session.md).
- The afkv2 agent sends the note as a plain prompt; it queues until the main agent's turn ends, and the developer may send it at once with Ctrl+Enter.
- The skill reuses the existing lanes for the build. It adds only the pane, the milestone note and the apply.
- Setup gains the source line of the install record: detect, suggest, ask.
- The pane outlives each result, an exception to the herdr playbook rule that closes a pane once its result is read; the skill states the exception.
- afkv2 changes favour instructions over scripts, so most changes apply ad hoc (owner: "we prioritize instructions instead of scripts").

## Testing Decisions

- A good test drives the real entry point: the skill in a herdr session with a real main pane and a real afkv2 pane.
- The queue of a prompt typed into a working agent is proven live on both Claude and Codex, because the grill took it as the developer's fact.
- Setup's source line: detect, suggest, confirm, type, and the worktree and wrong-repository refusals.
- The note check of AC-015 and AC-023 is a script with unit tests.
- Prior art: the proposer engine opens panes and starts agents; the herdr playbook holds the pane commands.

## Out of Scope

- The release, the merge and the version bump of the afkv2 change: the developer's normal ship path.
- An automated plugin reinstall or reload for a hook change: worked out case by case by the developer and the agents.
- A manual path outside herdr.
- Cleanup of the worktrees and branches after a merge: `/afkv2:gc`.

## Further Notes

- herdr types a prompt into a working agent and refuses only one that shows a dialog (herdr 0.9.5).
- Hooks, the core-behaviors text loaded at session start, and skill discovery come from the installed plugin. A main session therefore keeps the installed hooks, and a new skill is not in its skill list; the main agent uses a new skill only through the note.
- The model routing of ticket 204 is not merged; AC-005 depends on it.

Assumptions this PRD rests on:

- Text typed into a working Claude or Codex agent is queued until the turn ends; Ctrl+Enter sends it at once. (the developer's fact; to prove live)

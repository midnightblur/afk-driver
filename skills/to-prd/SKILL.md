---
name: to-prd
description: Turn the current conversation context into a PRD and publish it to the project issue tracker. Use when user wants to create a PRD from the current context.
---

This skill takes the current conversation context and codebase understanding and produces a PRD. Do NOT interview the user — just synthesize what you already know.

The issue tracker and triage label vocabulary should have been provided to you — run `/setup-matt-pocock-skills` if not.

## Backend dispatch (GitHub vs Jira+GitLab)

Detect the active backend **before** writing the PRD or touching the tracker.
Inspect the origin remote of the cwd:

```
git remote get-url origin
```

| Host substring | Backend | Tracker MCP namespace | SCM MCP namespace |
|----------------|---------|------------------------|--------------------|
| `github.com`   | GitHub  | `mcp__github__*`       | `mcp__github__*`   |
| anything else  | Jira + GitLab (legacy) | `mcp__jira__*` | `glab` CLI via the runner |

Use the tracker MCP namespace selected above for **every** issue / sub-issue
read-or-write in the rest of this skill. The shared prose below references
the picked client as the "tracker tool" — it speaks the same Markdown
vocabulary regardless of backend (Goal / Scope / Acceptance / Test command).
See SDD §3 (skills bypass the Python protocol layer and use parallel MCP
namespaces) and ADR-0001 (skill seam is the official `github/github-mcp-server`).

### GitHub backend — `to-prd` specifics

When the dispatch lands on the GitHub branch:

1. **PRD path.** Write the PRD to the per-repo configured `spec_root` from
   `.afk-driver.toml` (default `.afk/specs/{N}/PRD.md` where `{N}` is the
   parent issue number). The Nakisa `{service}/src/main/resources/specs/...`
   convention has no analogue here — the per-repo spec root replaces it.
2. **Parent issue.** If a parent issue number was passed in, edit its body
   to add or update a `## PRD` section pointing at the on-disk path (do not
   inline the PRD body — keep it on disk so future edits don't churn issue
   revisions). If **no parent issue was passed**, create a new parent issue
   first via `mcp__github__create_issue` using the PRD title as the issue
   title and the PRD's Problem Statement + Solution as the issue body, then
   continue with the `## PRD` splice into the just-created issue. Either
   path is valid — the human gates by choosing whether to pass a key
   (PRD Q12 "either").
3. **Body splice rules** mirror the Jira branch: only the `## PRD` section
   is owned by this skill; the `## Implementation Notes (auto-maintained)`
   block is owned by the AFK driver — splice the PRD section only, preserve
   everything else verbatim.

### Jira+GitLab backend — `to-prd` specifics

Follow the "AFK adaptation (core-services)" section below verbatim — that
section was written for this backend and still binds.

## Shared prose (after dispatch)

The rest of this skill uses backend-agnostic vocabulary: "tracker tool"
means whichever MCP namespace the dispatch above selected, "parent ticket"
means a Jira Enhancement / Bug or a GitHub parent issue, "PRD path" means
whatever the backend's PRD-path rule above resolved to. A reader cannot
tell which backend a PRD was authored against from the Markdown body
alone — the structure is identical.

## Process

1. Explore the repo to understand the current state of the codebase, if you haven't already. Use the project's domain glossary vocabulary throughout the PRD, and respect any ADRs in the area you're touching.

2. Sketch out the major modules you will need to build or modify to complete the implementation. Actively look for opportunities to extract deep modules that can be tested in isolation.

A deep module (as opposed to a shallow module) is one which encapsulates a lot of functionality in a simple, testable interface which rarely changes.

Check with the user that these modules match their expectations. Check with the user which modules they want tests written for.

3. Write the PRD using the template below.

<prd-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not implementation details)
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

A description of the things that are out of scope for this PRD.

## Further Notes

Any further notes about the feature.

</prd-template>

4. **Emit requirement-level ADRs.** The PRD's `## Implementation Decisions` is
   the broad list. From it, extract the subset of *behavioural* decisions that
   pass all three of (hard to reverse) AND (surprising without context) AND (a
   real trade-off with ≥2 genuine alternatives), and write each as a standalone
   ADR in the ticket-local `adr/requirements/` subfolder, sibling to the PRD —
   `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/adr/requirements/NNNN-slug.md`
   (GitHub backend: `{spec_root}/{TICKET-ID}/adr/requirements/NNNN-slug.md`).
   Numbering is local to that subfolder, starting at `0001`. Use the format in
   [ADR-FORMAT.md](./ADR-FORMAT.md). These record the *what / why* (feature
   behaviour, scope boundaries) — NOT the *how* (algorithm / pattern / tech),
   which `/afk:to-sdd` records separately under `adr/design/`. Skip this step
   entirely if no decision clears the three-part bar — most small PRDs won't.

## AFK adaptation (core-services)

When publishing a PRD that the AFK driver should be able to slice
(`/afk:to-subtasks` skill), follow these conventions:

- **PRD file location.** Write to
  `{service}/src/main/resources/specs/{year}r{release}/{ENH-ID}/PRD.md`
  for service-scoped work, or `tasks/{ENH-ID}/PRD.md` when the PRD's
  `## Service:` line is `tasks` (cross-cutting tooling). Service is auto-derived
  from the Jira project key via the driver's `project_service_map` config —
  e.g. project `P2P` maps to service `11700-payable`. `year` is the calendar
  year, `release` is the n-th release of that year (1-indexed).

- **Parent Enhancement description.** Add or update one section in the
  Enhancement description:

  ```
  ## PRD

  Full design lives in the repo at `{service}/src/main/resources/specs/{year}r{release}/{ENH-ID}/PRD.md`
  (this branch).
  ```

  **Never modify the `## Implementation Notes (auto-maintained)` block** —
  that's owned by the AFK driver and is updated as SubTasks complete. The
  splice should target the `## PRD` section only; everything else is
  preserved verbatim.

- **Linking back.** The Enhancement's `Target Branch` field should already
  reference the branch the PRD lives on (typically `MASTER` for tooling,
  the relevant release branch otherwise). The AFK driver uses this field
  to decide where to base the per-Enhancement worktree.

## Next

After the PRD is published, run **`/afk:architect-grill`** to interview the
architecture top-down across L1 → L8 layers, then **`/afk:to-sdd`** to
synthesize the SDD + ADRs. The SDD is what makes the AFK driver hands-off:
without it, downstream SubTasks slice in uncited mode (PRD-only, human-gated).
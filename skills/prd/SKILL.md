---
name: prd
description: Turn the current conversation context into a PRD and publish it to the project issue tracker. Use when user wants to create a PRD from the current context.
---

This skill takes the current conversation context and codebase understanding and produces a PRD. Do NOT interview the user — just synthesize what you already know.

The issue tracker and triage label vocabulary should have been provided to you — run `/setup-matt-pocock-skills` if not.

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

## AFK adaptation (core-services)

When publishing a PRD that the AFK driver should be able to slice
(`/afk:subtasks` skill), follow these conventions:

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
architecture top-down across L1 → L8 layers, then **`/afk:sdd`** to
synthesize the SDD + ADRs. The SDD is what makes the AFK driver hands-off:
without it, downstream SubTasks slice in uncited mode (PRD-only, human-gated).
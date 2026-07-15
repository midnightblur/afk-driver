---
name: setup
description: Set up or repair a developer's AFK-workflow environment — probes every external dependency (CLIs, MCP servers, secrets, sibling checkouts) against the manifest, fixes what it can, guides the rest. Use when installing the workflow on a machine (add `base` to also pin/provision the monorepo toolchain — git, JDK, Maven, Node/npm, Python, Docker — and workstation apps/OS config: IDEs, MySQL, Windows long paths), after a git pull changed the plugin, when a workflow skill dies on a missing tool or credential — or as `audit` to catch dependency/doc drift before shipping plugin changes.
---

# afk:setup — the workflow doctor

One idempotent skill for first-time setup **and** post-update repair: acts only
on failing probes — healthy machine → no change; after `git pull` → fixes
exactly what the pull broke. Run via the agent (this skill) or follow
[`MANIFEST.md`](MANIFEST.md) by hand — every probe/fix there is copy-pasteable.

## Branches

- **default** — check + fix the machine (below).
- **`base`** (`/afk:setup base`) — the default run **plus** every entry's
  `Base probe:` / `Base fix:` (version-pinned monorepo toolchain — git, JDK +
  Maven per `.sdkmanrc`, Node/npm per the workspace standard, Python, Docker)
  plus the base-only workstation apps & OS config (section W — IDEs, MySQL
  Server + Workbench, Windows long paths). For fresh machines or after a
  toolchain pin bump.
- **`audit`** (`/afk:setup audit`) — don't touch the machine; hunt drift between
  the plugin's artifacts and reality: [`AUDIT.md`](AUDIT.md).

## Doctor loop

1. **Load the register.** Read [`MANIFEST.md`](MANIFEST.md) — the complete
   dependency set; probe nothing outside it (a known dep missing from it is a
   FRESHNESS.md violation — flag it, then probe it anyway).
2. **Probe everything.** Run every entry's `Probe:` — `sh:` probes from the
   core-services repo root, `agent:` probes in-session. Under `base`, also run
   every `Base probe:` where present — a version miss there is `missing/broken`
   even when the plain probe passes, and its fix is the entry's `Base fix:`.
   Batch independent probes. Classify each: `ok` · `missing/broken` · `deferred`
   (tagged **[deferred]**, first-use not yet reached — never a failure).
   Section **O** (OpenAI Codex CLI) has its own gating rule: O1 missing →
   the whole section reports `deferred (Codex not installed)` wholesale.
3. **Report before touching.** One table — entry id, name, status, planned
   action — so the human sees the whole picture before any install runs.
4. **Fix.**
   - `auto:` fixes — run them. Confirm first only for global installs
     (`npm i -g`, `pip install`) in an interactive session.
   - `human:` fixes — walk the human through interactively. For **secret**
     entries, follow the manifest's secrets discipline: presence checks only,
     never echo a value; you set no secret — the human places it, you re-probe.
   - No fix / fix failed — record it; never improvise an install path the
     manifest doesn't name (a manifest gap → flag per step 1).
5. **Re-probe** every entry you touched. A fix not flipping its probe to exit 0
   is not fixed.
6. **Summarize** per `REPORTING.md` (plugin root): final table (`ok` / `fixed`
   / `deferred (until <first use>)` / `needs-human: <what>`), then one
   plain-terms sentence — is the workflow runnable now, and what still blocks
   which stage.

**Done when** every non-deferred entry probes `ok`, or the remainder are
`needs-human` items named precisely (which secret, snippet, doc). Nothing else
counts as done.

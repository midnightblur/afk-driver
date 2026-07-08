---
name: setup
description: Set up or repair a developer's AFK-workflow environment — probes every external dependency (CLIs, MCP servers, secrets, sibling checkouts) against the manifest, fixes what it can, guides the rest. Use when installing the workflow on a machine, after a git pull changed the plugin, when a workflow skill dies on a missing tool or credential — or as `audit` to catch dependency/doc drift before shipping plugin changes.
---

# afk:setup — the workflow doctor

One idempotent skill for first-time setup **and** repair after updates: it acts
only on failing probes, so running it on a healthy machine changes nothing and
running it after a `git pull` fixes exactly what the pull broke. A dev can run
it via the agent (this skill) or follow [`MANIFEST.md`](MANIFEST.md) by hand —
every probe/fix there is a copy-pasteable command.

## Branches

- **default** — check + fix the machine (below).
- **`audit`** (`/afk:setup audit`) — don't touch the machine; hunt drift between
  the plugin's artifacts and reality instead: [`AUDIT.md`](AUDIT.md).

## Doctor loop

1. **Load the register.** Read [`MANIFEST.md`](MANIFEST.md) — it is the complete
   dependency set; probe nothing that isn't in it (a dep you know of that's
   missing from it is a FRESHNESS.md violation — flag it, then probe it anyway).
2. **Probe everything.** Run every entry's `Probe:` — `sh:` probes from the
   core-services repo root, `agent:` probes in-session. Independent probes run
   batched. Classify each entry: `ok` · `missing/broken` · `deferred` (tagged
   **[deferred]** and its first-use hasn't happened — never a failure).
3. **Report before touching.** One table — entry id, name, status, planned
   action — so the human sees the whole picture before any install runs.
4. **Fix.**
   - `auto:` fixes — run them. Confirm first only for global installs
     (`npm i -g`, `pip install`) in an interactive session.
   - `human:` fixes — walk the human through the steps interactively. For
     **secret** entries, follow the manifest's secrets discipline: presence
     checks only, never echo a value; you set no secret yourself — the human
     places it, you re-probe.
   - No fix / fix failed — record it; never improvise an install path the
     manifest doesn't name (that's a manifest gap → flag per step 1).
5. **Re-probe** every entry you touched. A fix that doesn't flip its probe to
   exit 0 is not fixed.
6. **Summarize** per `REPORTING.md` (plugin root): final table (`ok` /
   `fixed` / `deferred (until <first use>)` / `needs-human: <what>`), then one
   plain-terms sentence stating whether the workflow is runnable now and what,
   if anything, still blocks which stage.

**Done when** every non-deferred entry probes `ok`, or the remainder are
`needs-human` items you have named precisely (which secret, which snippet,
which doc). Nothing else counts as done.

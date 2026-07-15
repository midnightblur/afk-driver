---
name: pitch
description: Steward of the AFK pitch/field-guide page. Detects plugin changes since the snapshot commit embedded in the checked-in page source, patches the page's stale facts, and republishes the shared claude.ai artifact to its stable URL. Use when plugin changes worth documenting have landed (`/afk:pitch`), or when the FRESHNESS registry or `/afk:setup audit` flags the pitch as stale.
---

# afk:pitch — keep the pitch page true

One page, two homes, one URL:

- **Source of truth**: [`afk-pitch.html`](afk-pitch.html) (this dir) — self-contained HTML, edited here, versioned with the plugin.
- **Published copy**: claude.ai artifact `https://claude.ai/code/artifact/fc1c59af-7779-4e26-a174-0c9e396cc017` (favicon 🛰️). Republishing requires the artifact owner's account; anyone else stops after patching the source and reports that the republish is pending the owner.

The page's facts (skill counts and tables, chain diagram, gate table, review-concern counts, Jira-writer count, limitations/WIP list, footer snapshot date) describe the plugin **as of one commit** — the snapshot marker near the top of the source:

```
<!-- afk-pitch-snapshot commit={SHA} date={YYYY-MM-DD} … -->
```

`commit` is the plugin HEAD the page's facts were last digested from. The marker advances only when the page is actually patched and republished.

## Process

1. **Read the marker** from `afk-pitch.html`. Missing/malformed → refuse with what's broken; never guess a baseline.
2. **Digest the gap.** `git log --stat {marker-SHA}..HEAD -- {plugin dir}`; delegate the read to an `afk-reader` subagent per `DELEGATION.md` (plugin root): which changes alter something the page states — skills added/renamed/removed, chain-shape edits, gate/agent changes, new or retired limitations, WIP items shipped or abandoned.
3. **Nothing page-worthy** → report `no_change` and stop. Leave the marker; re-digesting an already-inspected range is cheap and an unmoved marker never hides anything.
4. **Patch the source.** Every count on the page is re-derived empirically at patch time (count the manifest's `skills` array, the hooks dir, the agents dir) — never taken from the digest's prose. Update the affected sections, the footer snapshot date, and the marker (`commit` = current HEAD, `date` = today). A shipped WIP item moves from the limitations list into full coverage; don't leave both.
5. **Republish** via the Artifact tool with `url:` set to the URL above — same URL, in-place update. Keep the favicon.
6. **Commit** the patched source as its own docs-only commit on the current branch (normal repo branch rules apply). The pitch's own commit is self-referential and correctly reads as `no_change` on the next run.

## When to run

Manually maintained — there is no automatic trigger. The FRESHNESS registry (plugin root `FRESHNESS.md`) names this skill steward of the pitch row and states when a refresh is due: the skill set, chain map, gate set, or a limitation/WIP item changed since the marker. The human invokes `/afk:pitch` when they want the page brought up to date.

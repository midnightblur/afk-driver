# CONTEXT

Project glossary. Names that appear in `runner.py`, `jira_client.py`, `gitlab_client.py`, and the architectural conversations behind them. Use these terms exactly when proposing refactors or writing tests; consistency here is what makes the codebase navigable.

For the broader architecture overview (modules, commands, conventions) see `CLAUDE.md`. CONTEXT.md is for *concepts*; CLAUDE.md is for *layout*.

---

## Section splice

Preserving foreign prose around a driver-owned block within a description. The driver writes one block; the rest of the description is human-owned and must round-trip byte-identical.

Two splice sites today:
- **Jira parent description** — `## Implementation Notes (auto-maintained)` block on the parent Enhancement.
- **GitLab MR description** — the SubTask checklist block on the AFK Draft MR.

Distinct from **SubTask round-trip** (`subtask_template.py`), where the driver owns the *entire* SubTask description and there is no foreign prose to preserve. Don't bundle them — splice and round-trip are different problems and should not share an abstraction.

## Marker pair

The sentinel boundary that identifies a section splice block.

- **Plaintext (GitLab MR description)** — HTML comments: `<!-- afk:{name}:start -->` … `<!-- afk:{name}:end -->`.
- **ADF (Jira parent description)** — paragraph nodes whose text is the bare identifier wrapped in an inline-code mark (ADF has no comment node). Renders in Jira UI as visible monospaced `afk:{name}:start` / `afk:{name}:end`. Visible-but-recognizable is the deliberate trade: humans see them, learn to leave alone, strict mode catches accidental deletions.

The `{name}` is the splice block's identity (`notes`, `subtasks`, …). The `marker_id_text(name)` helper returns the bare identifier strings; each format wraps them differently.

### Heading inside the markers

The splicer is format-only — it owns marker-finding and outside preservation, nothing else. Anything decorative (an H2 header for human navigation, a leading note paragraph) lives **inside the marker region**, owned by the caller's `block_nodes` payload. Callers re-render the decoration on every splice; idempotency holds because identical input → identical output.

Concretely, the Jira Implementation Notes block is rendered as:

```
[afk:notes:start]
[## Implementation Notes (auto-maintained)]   ← H2, decorative, owned by caller
[bulletList of (KEY) text]
[afk:notes:end]
```

Renaming or deleting the H2 does not break the splicer — markers are the only identification.

## Strict mode

Splicer behavior when the marker pair is absent in the input content.

- **Default (`create_if_missing=False`)** — raise `SectionMarkerMissing`. Catches "human deleted the markers" and "ADF migration ate the sentinel."
- **Permissive (`create_if_missing=True`)** — append a fresh marker pair + block at the document end.

Callers choose per call. Implementation Notes always uses permissive (parent issues exist before AFK touches them; no first-publish signal). MR description splice uses strict (driver creates the MR with markers; their absence later is anomalous).

# ADAPTERS.md — the four adapter families

A skill asks for a VERB of a FAMILY. The configuration decides which KIND
answers. No skill names a binary, and no skill names a kind.

```
adapters/<family>/<kind>/adapter.json   machine-readable registry entry
adapters/<family>/<kind>/CONTRACT.md    verbs, config keys, documented degradation
adapters/<family>/<kind>/<entry>        the implementation adapter.json names
```

Dispatch from bash:

```bash
. "$AFK_PLUGIN_ROOT/hooks/lib/adapter.sh"
afk_adapter forge change-view '{"id":"123"}'
afk_adapter_kind tracker          # the configured kind
afk_adapter_dir  notes            # the selected adapter directory
```

`adapter.json` carries `family`, `kind`, `name`, `operations[]`,
`runner {type, entry}` and `configKeys[]`. `skill-registry-gate.sh` cross-checks
every entry against the directory on disk, the verb list in `CONTRACT.md`, the
schema in `CONFIG.md`, and the register rows in `skills/afk/setup/MANIFEST.md`,
so an adapter cannot be half-added.

## Answer shapes

| Situation | Answer | Exit |
|---|---|---|
| verb succeeded | the family's normalized object | 0 |
| verb is not part of this kind | `{"unsupported": true, "reason": "…"}` | 3 |
| kind selected, runtime missing | `{"unavailable": true, "reason": "…"}` | 4 |
| family or kind cannot be resolved | message naming `.afk/config.yaml` | 2 |

A missing OPTIONAL capability answers `unsupported`. A missing REQUIRED
capability fails before any side effect. A selected adapter whose runtime is
absent answers `unavailable` — never a silent skip.

## tracker

Nine operations, the same nine on every kind: `tracker_get`, `tracker_search`,
`tracker_create`, `tracker_edit`, `tracker_comment`, `tracker_transition`,
`tracker_transitions`, `tracker_attachments`, `tracker_changelog`.
`mcp-servers/tracker/server.py` registers exactly these and routes each to the
selected kind's `api.py` `call(operation, payload)`. The registration lives in
`.mcp.json` / `.mcp.codex.json` under the server name `tracker`, and passes the
plugin root rather than searching for it.

A publishing script that needs more than the nine — the ADF body machinery, the
attachment upload — reaches the selected kind through `scripts/tracker_api.py`,
which fails with the missing names and the configuration key when the configured
tracker does not carry them.

| Kind | Notes |
|---|---|
| [`jira`](adapters/tracker/jira/CONTRACT.md) | REST + ADF bodies + the media-services round trip for inline images |
| [`github-issues`](adapters/tracker/github-issues/CONTRACT.md) | `gh api`; states are labels, parent is a tracking issue, attachments are comment URLs |
| [`none`](adapters/tracker/none/CONTRACT.md) | every operation `unsupported`; skills write through `notes` instead |

## forge

`change-view`, `change-diff`, `change-create-draft`, `change-ready`,
`change-reviewers`, `change-update-body`, `change-comment`, `change-state`,
`change-close`, `change-fetch`, `thread-list`, `thread-reply`, `thread-resolve`,
`ci-status`, `ci-wait`, `auth-status`.

Normalized object: `id`, `url`, `title`, `state`, `draft`, `source`, `target`,
`pipeline.status`. A forge's own field names never leave the adapter — a skill
that read `iid` would break the day the repository moved.

`ci-wait` is the one verb with an exit-code contract, because a caller routes on
it rather than on a body: 0 the pipeline succeeded, 1 it failed or was cancelled,
2 the budget ran out while it kept running (parking is not cancelling), 3 the
status was unreadable three times running — a fault, never a verdict.

The three `thread-*` verbs carry a review conversation: list the threads, reply
inside one, resolve one. A kind that cannot resolve answers `unsupported` with
the reason, and the referee leaves the thread open — visible — rather than
resolving the wrong one.

| Kind | Notes |
|---|---|
| [`gitlab`](adapters/forge/gitlab/CONTRACT.md) | `glab`; inline comments are DiffNotes carrying the change's diff refs |
| [`github`](adapters/forge/github/CONTRACT.md) | `gh` |
| [`none`](adapters/forge/none/CONTRACT.md) | every verb `unsupported`, exit 3; skills stop with that reason |

## notes

`note-create`, `note-read`, `note-update`, `note-delete`, `note-link`, and
`resolve <workId> [service]` which renders the folder for a work item.

| Kind | Notes |
|---|---|
| [`repo-files`](adapters/notes/repo-files/CONTRACT.md) | Markdown under `repo-files.spec-dir`; the canonical store |
| [`obsidian`](adapters/notes/obsidian/CONTRACT.md) | the same tree inside `obsidian.vault`, plus a wikilink index |
| [`notion`](adapters/notes/notion/CONTRACT.md) | pages under `notion.parent-page-id` through the Notion MCP; local files stay canonical |

`repo-files` and `obsidian` store the same tree and differ only in where it is
rooted and how a link is written, so both state those two things and source the
family implementation in [`adapters/notes/common.sh`](adapters/notes/common.sh).

`notion` is the one kind whose runner type is `instruction` rather than `cli`:
its tools live in an agent session, not in a script. Dispatch answers
`{"instruction": "<file>", "verb": "<verb>"}` and the agent performs the verb
from that file. Any kind of any family may declare `instruction` the same way.

## build-gate

`gate-discover` (which gates the changed set needs), `gate-run <name>`, and for
Maven `app-start`. A gate function exits 0 to pass and 2 to block, with its
findings on stderr. `build-gates` selects which adapters load; the key absent
means no build gates.

This family is the one a repository selects a LIST of, so dispatch is by kind:
`afk_build_gate_discover` asks every selected kind what the change set needs and
`afk_build_gate_run <kind> <name>` runs one. Both SOURCE the kind's `gates.sh`
into the caller's process — a gate reads the shared change set, pass cache and
metrics the commit runner already built, and re-deriving them per gate is the
subprocess cost the single-process runner exists to avoid.

| Kind | Gates |
|---|---|
| [`maven`](adapters/build-gate/maven/CONTRACT.md) | compile, format, lock, app-start, mutation |
| [`npm`](adapters/build-gate/npm/CONTRACT.md) | lint |

## Adding a kind

1. `adapters/<family>/<kind>/adapter.json` + `CONTRACT.md` + the entry file.
2. Add the kind to its enum in `CONFIG.md` and in `scripts/afk-config.py`.
3. Add a register row in `skills/afk/setup/MANIFEST.md` for the runtime it needs.
4. Add a row to the parity table in `README.md` and a probe under `hooks/tests/`.

`skill-registry-gate.sh` fails until all four exist.

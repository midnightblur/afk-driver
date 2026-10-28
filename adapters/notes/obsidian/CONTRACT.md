# notes/obsidian — capability contract

The same Markdown tree as [`repo-files`](../repo-files/CONTRACT.md), in the
checkout's spec folder, linked with wikilinks so an Obsidian graph sees the
links. Agent working files stay in the repository whatever app is chosen.

Entry: `notes.sh`, which states this kind's link form and sources the family
implementation in [`../common.sh`](../common.sh).

## Verbs

`resolve`, `note-create`, `note-read`, `note-update`, `note-delete` and
`note-link` — the same six as `repo-files`, with the same payloads, the same
answer fields and the same `dir` and `path`. One difference: `note-link`
answers a wikilink — `[[PRD|text]]` — not a Markdown link.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | the verb ran |
| 2 | the verb could not resolve what it needed; the message names the key or the path |
| 3 | not a verb of this family |

## Configuration keys read

- `notes` — the developer's note-taking app, from the machine file
- `repo-files.spec-dir` — the path template, as for `repo-files`

`obsidian.vault` (machine file) names the developer's own vault. This kind
does not read it: no agent working file goes to the vault.

## Runtime

`git` and Python 3, as for `repo-files`. Obsidian itself need not be running.

## Documented degradation

None beyond `repo-files`: run outside a git checkout, the kind refuses with
exit 2.

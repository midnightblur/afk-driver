# notes/obsidian — capability contract

The same Markdown tree as [`repo-files`](../repo-files/CONTRACT.md), rooted
inside `obsidian.vault` so the vault indexes it, and linked with wikilinks so
the vault's graph sees the links.

Entry: `notes.sh`, which states this kind's root and link form and sources the
family implementation in [`../common.sh`](../common.sh).

## Verbs

`resolve`, `note-create`, `note-read`, `note-update`, `note-delete` and
`note-link` — the same six as `repo-files`, with the same payloads and the same
answer fields. Two differences:

- `dir` and `path` are under `obsidian.vault`, not under the repository.
- `note-link` answers a wikilink — `[[PRD|text]]` — not a Markdown link.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | the verb ran |
| 2 | the verb could not resolve what it needed; the message names the key |
| 3 | not a verb of this family |
| 4 | `obsidian.vault` names a directory that is not on this machine |

## Configuration keys read

- `notes`
- `obsidian.vault` — the vault directory, absolute
- `repo-files.spec-dir` — the path template inside the vault, so a note keeps
  the same relative place in either store

## Runtime

Python 3. Obsidian itself need not be running: the vault is a directory of
Markdown files, and this kind writes the files.

## Documented degradation

A vault directory that is absent (an unmounted drive, a different machine)
answers `unavailable` with the configured path, exit 4. It never falls back to
the repository — a caller that wanted the vault must know the vault was
missed.

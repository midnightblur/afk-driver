# notes/obsidian — capability contract

The same Markdown tree inside an Obsidian vault, plus a wikilink index page.

## Verbs

- `note-create`
- `note-read`
- `note-update`
- `note-delete`
- `note-link`
- `resolve`

Every verb takes its arguments as JSON on the command line or on stdin, and
answers with one JSON object on stdout. A verb this adapter does not implement
answers `{"unsupported": true, "reason": "..."}`. A verb whose runtime is
absent answers `{"unavailable": true, "reason": "..."}` — never nothing.

## Configuration keys read

- `notes`
- `obsidian.vault`
- `repo-files.spec-dir`

Secrets are never read from a configuration file. The keys above name
environment variables; the values come from the environment or the harness
credential store.

## Documented degradation

`note-link` writes a `[[wikilink]]`; a reader outside Obsidian sees the raw
text.

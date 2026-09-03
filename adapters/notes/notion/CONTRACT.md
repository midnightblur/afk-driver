# notes/notion — capability contract

Notion pages under `notion.parent-page-id`, written through the Notion MCP
tools. Local files stay canonical and are mirrored up.

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
- `notion.parent-page-id`

Secrets are never read from a configuration file. The keys above name
environment variables; the values come from the environment or the harness
credential store.

## Documented degradation

Requires a connected Notion MCP server. Selected but unavailable returns
`unavailable` with that message — never a silent skip.

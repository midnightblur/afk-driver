# notes/notion — capability contract

Notion pages under `notion.parent-page-id`, written through the Notion MCP
tools. The local files stay canonical and are mirrored up, so a Notion failure
never loses a note.

Entry: [`NOTES.md`](NOTES.md), and the runner type is `instruction`, not `cli`.
Notion is reached through MCP tools that only an agent session holds, so this
kind has no script: `afk_adapter notes <verb>` answers
`{"instruction": "<path to NOTES.md>", "verb": "<verb>"}` and the agent
performs the verb from that file.

## Verbs

The same six as [`repo-files`](../repo-files/CONTRACT.md), with the same
payloads. Each answer carries the `repo-files` fields plus a `notion` object
holding `page` and `url`.

## Configuration keys read

- `notes`
- `notion.parent-page-id` — the page every work item's page is created under
- `repo-files.spec-dir` — the local tree this kind mirrors

## Runtime

A connected Notion MCP server, plus everything `repo-files` needs (the local
copy is written first, always).

## Documented degradation

- No Notion MCP server connected → `unavailable` naming that, never a silent
  fall back to a different store.
- A verb that succeeded locally but failed on the Notion side answers with the
  local fields plus `notion.error`, so a caller can tell a mirrored note from
  an unmirrored one.
- `note-delete` archives the page rather than destroying it, because that is
  what Notion does; the answer says "archived".

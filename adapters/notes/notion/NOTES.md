# notes/notion — how the agent performs each verb

This kind has no script. Notion is reached through MCP tools that only an agent
session holds, so dispatch hands you this file and you perform the verb.

Local files stay canonical: every verb writes the repository copy through the
`repo-files` kind FIRST, then mirrors that content to Notion. A Notion failure
therefore never loses the note.

## Before any verb

1. Read `notion.parent-page-id` from `.afk/config.yaml`. Absent → stop and say
   so, naming the key; do not pick a page.
2. Check a Notion MCP server is connected. Not connected → answer
   `{"unavailable": true, "reason": "notes: notion — no Notion MCP server is
   connected"}` and stop. Never fall back silently to a different store.
3. Resolve the work item's directory:
   `bash adapters/notes/repo-files/notes.sh resolve '{"workId": "<id>"}'`.
   Its `dir` is the local tree this kind mirrors.

## Verbs

| Verb | Do this |
|---|---|
| `resolve` | Return the `repo-files` `dir` plus the Notion page id that mirrors it — the child of `notion.parent-page-id` whose title is the work id. No such child yet → report `page: null`; `note-create` makes it. |
| `note-create` | Write the file through `repo-files` first. Then create a child page of the work item's page (creating the work item page under `notion.parent-page-id` if it is the first note), titled the note's file name without `.md`, with the Markdown as its content. |
| `note-read` | Read the local file through `repo-files`. Read Notion only when the caller asks for the published copy — it is the mirror, not the source. |
| `note-update` | Update the local file through `repo-files`, then replace the mirrored page's content with the new Markdown. Never merge the two copies: the local file wins. |
| `note-delete` | Delete the local file through `repo-files`, then archive the mirrored page. Notion archives rather than destroys, and that is the intended behaviour — say "archived" in the result. Not every Notion MCP server exposes an archive or trash tool; when none is connected, answer the local `deleted: true` plus `notion.error` naming the missing tool, and say the page is still there. Never delete the page by some other means. |
| `note-link` | Return both forms: the Markdown link `repo-files` gives, and the Notion page URL of the mirror. A caller writing into a repository file uses the first; one writing into a page uses the second. |

## Answer shape

Answer with the same JSON object shape the `repo-files` kind answers with, plus
a `notion` object carrying `page` (the page id) and `url`. A verb you could not
complete on the Notion side but did complete locally answers with the local
fields plus `{"notion": {"error": "..."}}` — the caller must be able to tell a
mirrored note from an unmirrored one.

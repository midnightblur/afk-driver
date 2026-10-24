# tracker/jira — capability contract

Atlassian Jira Cloud through its REST API, with native ADF bodies and the
media-services round trip for inline attachments.

## Verbs

- `tracker_get`
- `tracker_search`
- `tracker_create`
- `tracker_edit`
- `tracker_comment`
- `tracker_transition`
- `tracker_transitions`
- `tracker_attachments`
- `tracker_changelog`
- `tracker_attach`

Every verb takes its arguments as JSON on the command line or on stdin, and
answers with one JSON object on stdout. A verb this adapter does not implement
answers `{"unsupported": true, "reason": "..."}`. A verb whose runtime is
absent answers `{"unavailable": true, "reason": "..."}` — never nothing.

## Configuration keys read

- `tracker`
- `jira.project`
- `jira.issue-types`
- `jira.transitions`
- `jira.credentials-env`

Secrets are never read from a configuration file. `jira.credentials-env` names
the environment variables; the values come from the environment, from the
`tracker` MCP registration's `env` block in the harness configuration, or from
the harness credential store. The registration was named `jira` before the
adapter split; that name counts only for afk's own entry (`is_afk_entry` in
`skills/afk/setup/scripts/tracker_registration.py`), never another server's.

## What the operations send

| Operation | Behaviour here |
|---|---|
| `tracker_create`, `tracker_comment` | the description or comment text is Markdown, sent as Atlassian Document Format (ADF) nodes: headings, lists, code blocks, links, tables |
| `tracker_create`, `tracker_edit` | a fix version that is not a version of the project is refused before any write |
| `tracker_transition` | `transition_id` is a `jira.transitions` key (the in-review key is `in-review`), a transition name or an id; one the issue does not offer is refused before any write |
| `tracker_create` with `status` | the same match, made after the create: Jira lists transitions per issue, so a miss is a `status_warning` on the created issue |
| `tracker_attach` | one upload request; each file carries its real content type. Each stored name and type is read back, and a difference is listed in `mismatches` and named in the comment. Images and videos are embedded inline, other files as attachment cards |

A refusal answers `error` and `refused: true`.

## Beyond the ten operations

`api.py` also carries the publishing machinery the Jira page format needs, which
`scripts/tracker_api.py` hands to `skills/afk/bug/scripts/publish_bug.py` and
`skills/afk/to-ticket/scripts/publish_{prd,meeting}.py`: `load_creds`, the `Jira`
REST client (multipart attachment upload and the media-UUID 303-redirect trick
inline images need), `md_to_adf_content`, `FIG_TOKEN` and `png_size`. A tracker
kind that does not offer these makes those publishers stop with the missing
names and the configuration key, never half-write a page.

`afk-python api.py --check-creds` reports whether credentials resolve, printing no
value; `--list-tools` prints the ten operation names.

`scripts/tests/test_tracker_jira.py` pins the payload shapes this machinery
produces — ADF conversion, the multipart attachment body, media-UUID extraction,
credential resolution and PNG sizing — with no network access.
`scripts/tests/test_tracker_attach.py` pins the outgoing requests of
`tracker_attach`, the ADF bodies and the refusals.

## Documented degradation

None. Every tracker verb is supported.

A payload that is not one JSON object is answered with the family's error object and exit 2, never a traceback; the shared reader is `adapters/tracker/payload.py` and `scripts/tests/test_tracker_surface.py` pins it for both tracker kinds.

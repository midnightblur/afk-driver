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
adapter split, so both names resolve.

## Beyond the nine operations

`api.py` also carries the publishing machinery the Jira page format needs, which
`scripts/tracker_api.py` hands to `skills/afk/bug/scripts/publish_bug.py` and
`skills/afk/to-ticket/scripts/publish_{prd,meeting}.py`: `load_creds`, the `Jira`
REST client (multipart attachment upload and the media-UUID 303-redirect trick
inline images need), `md_to_adf_content`, `FIG_TOKEN` and `png_size`. A tracker
kind that does not offer these makes those publishers stop with the missing
names and the configuration key, never half-write a page.

`python api.py --check-creds` reports whether credentials resolve, printing no
value; `--list-tools` prints the nine operation names.

`scripts/tests/test_tracker_jira.py` pins the payload shapes this machinery
produces — ADF conversion, the multipart attachment body, media-UUID extraction,
credential resolution and PNG sizing — with no network access.

## Documented degradation

None. Every tracker verb is supported.

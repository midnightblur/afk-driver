# forge/gitlab — capability contract

GitLab merge requests through `glab`. Inline comments post as DiffNotes with
the merge request's diff refs.

## Verbs

- `change-view`, `change-diff`, `change-fetch`, `change-state`
- `change-create-draft`, `change-ready`, `change-reviewers`, `change-update-body`,
  `change-comment`, `change-close`
- `thread-list`, `thread-reply`, `thread-resolve`
- `ci-status`, `ci-wait`
- `auth-status`


Every verb takes its arguments as JSON on the command line or on stdin, and
answers with one JSON object on stdout. A verb this adapter does not implement
answers `{"unsupported": true, "reason": "..."}`. A verb whose runtime is
absent answers `{"unavailable": true, "reason": "..."}` — never nothing.

## Configuration keys read

- `forge`
- `gitlab.remote`
- `git.base-branch`

No credential is configured for this kind: authentication is whatever the forge
CLI already established, and no configuration file holds a token.

## Notes that bite

- An INLINE comment is a DiffNote and needs the change's four diff refs
  (`base_sha`, `start_sha`, `head_sha` plus the paths). `glab mr note` has no
  flag for that, and passing `-f position[...]` form parameters posts a PLAIN
  note instead — silently. `change-comment` therefore builds the JSON body and
  posts it through the API, then VERIFIES the created note's `type` is
  `DiffNote`; anything else comes back `"ok": false` with the reason, because a
  review that believes it commented on a line and did not is worse than an error.
- On a new file `old_path` must equal `new_path` (not `/dev/null`), or the
  server rejects the position.
- `thread-list` paginates to the end. A round that read only the first page
  would re-open findings it had already settled.
- `glab mr update --description` clears the Draft flag: the new title comes back
  without its `Draft:` prefix and the change becomes reviewable. Editing a
  description is not a decision to publish, so any caller that edits one reads
  the draft state back afterwards and restores it with `glab mr update --draft`.
- Read a description as bytes, not through a pipe that guesses the encoding. On
  a Windows console the reader decodes UTF-8 as cp1252, so an em dash comes back
  as three characters; posting that text back stores the damage on the server.
  Set `PYTHONIOENCODING=utf-8` (or read the JSON as bytes) before any
  round-trip of description or note text.

## Documented degradation

None. Every forge verb is supported.

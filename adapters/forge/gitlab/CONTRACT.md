# forge/gitlab — capability contract

GitLab merge requests through `glab`. Inline comments post as DiffNotes with
the merge request's diff refs.

## Verbs

- `change-view`, `change-diff`, `change-fetch`, `change-state`
- `change-create-draft`, `change-ready`, `change-reviewers`, `change-update-body`,
  `change-comment`, `change-close`
- `thread-list`, `thread-reply`, `thread-resolve`
- `note-list`, `commit-changes`
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

The adapter tests use a stub command-line tool. They do not contact GitLab.

- A paginated read (`glab api --paginate`) prints one JSON document per page,
  not one document holding every page. `thread-list` decodes the documents in
  order and joins the arrays; a caller driving `glab` directly does the same, or
  it sees only page 1 — or, worse, reports the whole answer unreadable.
- `ci-wait` prints its result object on stdout for EVERY terminal status,
  including budget exhausted (exit 2) and unreadable (exit 3); stderr carries
  the human line only. A caller routes on the object, and an exit code alone
  does not say which pipeline, or for how long.
- A payload handed to this script as a command-line argument from a NATIVE
  Windows process (not from a shell) loses its quotes: the shell's runtime
  re-parses the command line, and the adapter then reads an unreadable payload
  and uses its defaults. Such a caller puts the payload in the environment and
  lets the shell expand it.
- An INLINE comment is a DiffNote and needs the change's four diff refs
  (`base_sha`, `start_sha`, `head_sha` plus the paths). `glab mr note` has no
  flag for that, and passing `-f position[...]` form parameters posts a PLAIN
  note instead — silently. `change-comment` therefore builds the JSON body and
  posts it through the API, then VERIFIES the created note's `type` is
  `DiffNote`; anything else comes back `"ok": false` with the reason, because a
  review that believes it commented on a line and did not is worse than an error.
- On a new file `old_path` must equal `new_path` (not `/dev/null`), or the
  server rejects the position.
- `change-comment` always sends both paths. `side: new` sends `new_line`.
  `side: old` sends `old_line`. `side: context` sends both lines.
- A rejected position can degrade to a plain note. The normal result reports
  `inline: false` and the reason.
- `require_inline: true` deletes that degraded note. A cleanup failure returns
  an error with the orphan note identifier.
- `commit-changes` reads the merge requests that contain one commit (`sha`), paginated. A failing `glab`, a non-list answer, or an entry with no `iid` is an error.
- `change-view` answers `missing: true` in its error only when `glab` says no merge request exists for the reference.
- `note-list` reads paginated merge-request notes. It removes system and inline
  notes and sorts the result oldest first. Each note carries `edited` from
  GraphQL `Note.lastEditedBy`, which is non-null exactly when GitLab calls the
  note edited, keyed by the numeric part of the note's global id.
  `lastEditedAt` is no evidence: on a note edited within one second of its
  creation it equals `createdAt`, and resolving a thread moves it. The REST
  note entity has no edit field. A failed query, or a note the query does not
  answer, is an error.
- `thread-list` paginates to the end. A round that read only the first page
  would re-open findings it had already settled.
- Each thread includes its URL, side, lines, paths, and note timestamps. Each
  note carries `edited`, read as in `note-list`.
- `change-view` and `change-fetch` return the metadata in `ADAPTERS.md`.
- `blob_base` names the source project. It is empty when that project is gone.
- `glab mr update --description` clears the Draft flag: the new title comes back
  without its `Draft:` prefix and the change becomes reviewable. Editing a
  description is not a decision to publish, so `change-update-body` reads the
  flag before the edit, checks it after, and restores it with
  `glab mr update --draft`. Its answer carries `was_draft` and
  `draft_restored`, so a caller can see that it happened. A caller driving
  `glab` directly does the same, and verifies at the END of a round: the flag
  has been observed clear again after a later push or edit.
- Text to and from the forge is UTF-8, and a console encoding is not. This
  adapter exports `PYTHONIOENCODING=utf-8` for exactly that reason: on a Windows
  terminal the default is cp1252, where an emoji in a change body raises
  UnicodeEncodeError inside the argument reader and the field arrives EMPTY,
  and an em dash read back comes out as three characters that get stored on the
  server when the text is posted again. A caller driving `glab` directly sets
  the same variable before any round-trip of description or note text.

## Documented degradation

Every forge verb is supported. A rejected line position follows the
`change-comment` rule above.

## Notes on the shared protected-branch read

Reads the project's `protected_branches`. That list also carries rules inherited from the group, marked `"inherited": true` (https://docs.gitlab.com/api/protected_branches/), so a group rule protects like a project rule. A wildcard rule comes back as the pattern, not the matching branch names.

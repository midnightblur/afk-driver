# notes/repo-files — capability contract

Markdown files inside the consuming repository, under the directory
`repo-files.spec-dir` renders for the work item. This is the canonical store:
every other notes kind mirrors this tree.

Entry: `notes.sh`, which states this kind's root and link form and sources the
family implementation in [`../common.sh`](../common.sh).

## Verbs

| Verb | Payload | Answers |
|---|---|---|
| `resolve` | the placeholder set (`workId`, `ticket`, `service`, `release`, `user`) | `kind`, `dir` (absolute), `template`, `exists` |
| `note-create` | the above plus `name`, `content` | `path`, `created` |
| `note-read` | the above plus `name` | `path`, `content` (byte for byte) |
| `note-update` | the above plus `name`, `content`, optional `mode: append` | `path`, `updated` |
| `note-delete` | the above plus `name` | `path`, `deleted` |
| `note-link` | the above plus `name`, optional `text` | `path`, `link` (Markdown) |

Every verb takes one JSON object — on the command line or on stdin — and
answers with one JSON object on stdout.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | the verb ran |
| 2 | the verb could not resolve what it needed; the message names the key or the path |
| 3 | not a verb of this family |

`name` is relative to the resolved directory. An absolute `name`, or one
containing `..`, is refused with exit 2 — a note never lands outside the work
item's directory.

## Configuration keys read

- `notes`
- `repo-files.spec-dir` — the path template, expanded with the placeholder set
  in `CONFIG.md` "Path templates"

## Runtime

`git` (the tree is rooted at the checkout) and Python 3. Run outside a git
checkout, this kind refuses with exit 2 rather than writing somewhere
arbitrary.

## Documented degradation

None. This is the canonical store.

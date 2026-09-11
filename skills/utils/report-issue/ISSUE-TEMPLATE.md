# Issue body

> **Language:** read `LANGUAGE.md` (plugin root) before writing — it binds every word of this body.

A maintainer reads the body cold, with no access to the session, the consuming repository, or its product. Each section stands alone. A section with no data reads `none captured` — never dropped.

Title: `<owning file>: <symptom in one line>`, at most 80 characters.

```markdown
## Summary
<one to three sentences: what broke or what is wrong, in plugin terms>

## Goal
<what the run was trying to do: skill, step, mode>

## Expected
<the behavior the plugin's own contract states — cite the file and section>

## Actual
<what happened instead>

## Steps to reproduce
1. <plugin-side step: a skill invocation or a script command with its flags>
2. <…; a product value is written as a placeholder: <module>, <branch>>

## Evidence
<one fenced block per item: the command, its exit code, and the last 40 lines
of output at most; OUTCOME / AUTOPILOT / REVIEW lines; hook stderr; the journal
tail from the environment JSON>

## Environment
| Field | Value |
|---|---|
| Plugin version | <plugin_version> |
| Harness | <provider> |
| OS | <os> |
| git / gh / python | <git> / <gh> / <python> |
| Adapters | tracker <tracker>, forge <forge>, notes <notes>, build gates <build_gates> |
| Fingerprint | `<fp>` |

## Suspected owner
- `<plugin-relative path>` — <why this file; label an inference as one>

<!-- afk-issue-fp:<fp> -->
```

Only plugin-side context enters the body: plugin paths, plugin commands, hook and script output, the environment table. Product code, product paths, ticket ids, and the consuming repository's name or remotes never enter it — describe their role with a placeholder instead.

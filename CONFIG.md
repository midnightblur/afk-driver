# CONFIG.md — the consuming repository's contract with AFK Toolkit

A repository tells the toolkit what it is by committing `.afk/config.yaml` at
its root. Nothing else in the repository configures the toolkit, and no file in
the toolkit names a repository path.

Read the effective configuration with the one reader; never parse the file:

```
python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" effective --json
python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" get verification.tiers.e2e.command
python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" validate
```

Bash gates source the flat export once per Stop through `hooks/lib/config.sh`
and read the fixed `AFK_CFG_*` names.

## Discovery

Highest precedence first:

| Layer | Path | Purpose |
|---|---|---|
| explicit | `$AFK_CONFIG` | a named file, for tests and one-off runs |
| local overlay | `<git root>/.afk/config.local.yaml` | gitignored, per developer; may not set `schema` |
| repository | `<git root>/.afk/config.yaml` | committed, the repository's contract |
| machine | `~/.afk/config.yaml` | per-machine defaults across repositories |
| built-in | — | the defaults below |

Layers deep-merge: a mapping merges key by key, any other value replaces. Both
files absent is a supported state — the built-in defaults apply.

## Built-in defaults

```yaml
schema: 1
tracker: none
forge: none
notes: repo-files
git:
  base-branch: auto
  branch-pattern: ''
repo-files:
  spec-dir: 'docs/afk/{workId}'
```

`build-gates` has no default: the key is absent, and absent means no build
gates run. `git.branch-pattern: ''` means the branch-name gate is off.
`git.base-branch: auto` resolves to `origin/main`, else `origin/master`, else
the branch's upstream, else `HEAD`.

## The supported YAML subset

The reader is standard-library only, so the format is a documented subset.
Anything outside it is refused with a file and line number — never guessed at.

Supported: block maps indented by two spaces; block lists written `- item`;
plain scalars; single- and double-quoted scalars; `#` comments; integers,
floats, `true`/`false`, `null`.

Refused: flow maps `{a: 1}`; flow lists `[a, b]`; anchors `&a` and aliases `*a`;
block scalars `|` and `>`; tab indentation; multiple documents; duplicate keys.

An empty list is expressed by **omitting the key**. `[]` is flow syntax and is
refused, so `build-gates` absent is the only way to say "no build gates".

## Schema

| Key | Type | Meaning |
|---|---|---|
| `schema` | int | must be `1` |
| `toolkit-version` | string | the toolkit version this repository was configured against |
| `tracker` | `jira` \| `github-issues` \| `none` | which tracker adapter answers `tracker_*` |
| `forge` | `gitlab` \| `github` \| `none` | which forge adapter answers `change-*` and `ci-*` |
| `notes` | `repo-files` \| `notion` \| `obsidian` | where narrative documents live |
| `build-gates` | list of `maven` \| `npm` | which build-gate adapters load; omit for none |
| `jira` | map | `project`, `issue-types`, `transitions`, `credentials-env` |
| `github-issues` | map | `repo`, `state-labels` |
| `gitlab` / `github` | map | `remote` |
| `git` | map | `base-branch`, `branch-pattern`, `branch-template` |
| `repo-files` | map | `spec-dir` template |
| `obsidian` | map | `vault` |
| `notion` | map | `parent-page-id` |
| `artifacts` | map | `glossary-map`, `service-map` |
| `maven` | map | `reactor-pom`, `formatter-config`, `formatter-plugin`, `default-module`, `skip-ui-flag` |
| `npm` | map | `lint`, `workspace-root` |
| `verification` | map | `tiers`, `env` |
| `repo-hooks` | string | repository-relative path to the hook manifest; default `.afk/hooks.json` |
| `setup` | map | `extra`: repository files `/afk-toolkit:setup` reads as extra register rows |

### Path templates

`repo-files.spec-dir` and `git.branch-template` expand a fixed placeholder set:
`{workId}`, `{ticket}`, `{ticket_lower}`, `{service}`, `{release}`, `{user}`.
An unknown placeholder is left alone rather than guessed.

### Verification tiers

```yaml
verification:
  tiers:
    unit:
      command: ./mvnw
      args:
        - -pl
        - "{module}"
        - --also-make
        - test
```

Skills name tier KEYS, never commands. A tier is executed as an argument
vector, never through a shell string, and only the documented placeholders
`{module}`, `{tags}`, `{env}` are expanded — so nothing a configuration file
holds can become shell syntax.

### Repository hooks

`repo-hooks` names a JSON array. Each entry has `event`
(`SessionStart` | `PreToolUse` | `Stop`), `matcher` (a regular expression
matched against the tool name, or `*`), `timeout` in seconds, and `script`, a
repository-relative path. A script that resolves outside the repository root is
refused. `hooks/run-hook.py` runs the matching entries in declaration order and
exports `AFK_PLUGIN_ROOT` to each.

## Secrets

A configuration file holds environment variable NAMES, never values.
`jira.credentials-env` lists the variables the Jira adapter reads. Values come
from the environment or the harness credential store. `.afk/config.local.yaml`
is gitignored and holds per-developer non-secret values — `tracker-assignee`,
`forge-reviewer`, `worktree-base-path`.

The subset, the discovery order and the agreement between the three views are
pinned by `scripts/tests/test_afk_config.py`; `scripts/tests/samples/monorepo-config.yaml`
is the large-repository fixture it validates.

## The shell view

`hooks/lib/config.sh` sources `afk-config.py export-shell` once per Stop and
exports:

- a scalar as `AFK_CFG_<PATH>` — `git.base-branch` becomes `AFK_CFG_GIT_BASE_BRANCH`
- a list as `AFK_CFG_<PATH>_COUNT` plus `AFK_CFG_<PATH>_0`, `_1`, …
- `AFK_CFG_LOADED=1` once the export ran

Every value is shell-quoted at export time, so a pattern containing spaces or
`;` cannot become a command.

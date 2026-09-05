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
| machine | `~/.afk/config.yaml` | per-machine defaults across repositories — the recommended home for a developer's own `developer:` block |
| built-in | — | the defaults below |

Layers deep-merge: a mapping merges key by key, any other value replaces. Both
files absent is a supported state — the built-in defaults apply.

## Starting a repository off

```sh
python scripts/afk-config.py init          # --force to replace an existing file
```

Writes a starter `.afk/config.yaml` from what the repository can answer about
itself: the forge from the origin remote's host, the build gates from a root
`pom.xml` / `package.json`, the base branch from `origin/HEAD`. Anything it
cannot read is written as a commented `TODO` rather than a plausible guess — a
wrong value that validates is harder to notice than a missing one. The file it
writes always passes `validate`. `/afk:setup` runs it for you when the file is
absent.

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
| `maven` | map | `reactor-pom` (the POM every reactor run targets), `formatter-config` (formatter profile file), `formatter-plugin` (`group:artifact:version` of the formatter plugin), `default-module` (app-start's default), `skip-ui-flag` (one argument, e.g. `-DskipUi=true`), `worktree-repo` (`isolated` \| `shared`), `worktree-seed` (`auto` \| `none` \| a path), `worktree-seed-exclude` (globs the seed skips, default `*-SNAPSHOT`) |
| `npm` | map | `lint` (lint command and its fixed arguments, split on whitespace; changed files appended), `workspace-root` (the hoisted lint workspace, also where a new worktree installs), `worktree-install` (`ci` \| `none`), `worktree-command` (argv words restoring the dependencies, default `npm ci`) |
| `verification` | map | `tiers`, `env` |
| `repo-hooks` | string | repository-relative path to the hook manifest; default `.afk/hooks.json` |
| `setup` | map | `extra`: repository files `/afk:setup` reads as extra register rows |
| `worktree` | map | what a new worktree carries over from the checkout it was cut from — `copy` (repository-relative files and directories, default `.mcp.json`, `.claude`, `.run`, `.idea`), `copy-personal` (`false` copies nothing), `copy-ignored-claude-md` (`false` skips the gitignored `CLAUDE.md` sweep). Build-system state is NOT here: each build gate provisions its own. |
| `developer` | map | per-developer values — `trackerAssignee`, `mrReviewer`, `worktreeBasePath`, `ideBinary`. Belongs in `~/.afk/config.yaml` (one file per machine) or, for a value that differs in one checkout, in that checkout's `config.local.yaml` — never the committed file, because each names a person or one machine's paths. There is no committed layer for them: `trackerAssignee` and `mrReviewer` name a person, and a committed file never does, so `/afk:setup` asks each developer for their own. Resolve with `afk-config.py resolve <key>`, which applies the developer value, then (for `worktreeBasePath` alone) a derived one; nothing resolving it means fail closed (`skills/afk/bug/CONFIG.md`). |

Every map in the table is validated one level down: a child key that is not
listed is refused, named by its full dotted path. Below that level the names
are the repository's own — a transition name, a state name, a tier name — so
they are not constrained.

### Path templates

`repo-files.spec-dir` and `git.branch-template` expand a fixed placeholder set:
`{workId}`, `{ticket}`, `{ticket_lower}`, `{service}`, `{release}`, `{user}`.
An unknown placeholder is left alone rather than guessed.

### Worktree provisioning

`scripts/create-worktree` copies what `worktree.copy` names, then runs
`scripts/worktree-provision`, which asks every selected build gate to provision
the new worktree for itself. What each one does, and the keys it reads, is in
its own `adapters/build-gate/<kind>/CONTRACT.md`.

Provisioning is recorded in the worktree's git admin directory, never in its
tree, so it never appears in `git status` and never blocks `git worktree
remove`. A second run does nothing; a run against a worktree that already has
the state adopts it instead of redoing it, which is how a worktree made before
this existed is brought forward. `--force` redoes it; `--skip-build-gate <kind>`
leaves one alone.

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
refused. What the launcher does with a handler it cannot run is pinned by
`scripts/tests/test_run_hook.py`. `hooks/run-hook.py` runs the matching entries in declaration order and
exports `AFK_PLUGIN_ROOT` to each. A declared handler this checkout cannot run
is a configuration error: on `Stop` and `PreToolUse` the launcher blocks the
turn and names the entry, so a gate cannot go missing quietly.

## Secrets

A configuration file holds environment variable NAMES, never values.
`jira.credentials-env` lists the variables the Jira adapter reads. Values come
from the environment or the harness credential store. A developer's own
non-secret values live under `developer:` in `~/.afk/config.yaml`, or in the
gitignored `.afk/config.local.yaml` when one checkout needs a different value.

The subset, the discovery order, the child keys of every map above, the
readable failure of `validate FILE`, and the agreement between the three views
are pinned by `scripts/tests/test_afk_config.py`; the scaffolder and the
developer-value resolution order by `scripts/tests/test_afk_config_init.py`; worktree copying and provisioning by `scripts/tests/create-worktree-smoke.sh` and `scripts/tests/worktree-provision-smoke.sh`; `scripts/tests/samples/monorepo-config.yaml`
is the large-repository fixture it validates.

## The shell view

`hooks/lib/config.sh` sources `afk-config.py export-shell` once per Stop and
exports:

- a scalar as `AFK_CFG_<PATH>` — `git.base-branch` becomes `AFK_CFG_GIT_BASE_BRANCH`
- a list as `AFK_CFG_<PATH>_COUNT` plus `AFK_CFG_<PATH>_0`, `_1`, …
- `AFK_CFG_LOADED=1` once the export ran

Every value is shell-quoted at export time, so a pattern containing spaces or
`;` cannot become a command.

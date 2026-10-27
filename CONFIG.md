# CONFIG.md — the consuming repository's contract with AFK Toolkit

A repository tells the toolkit what it is by committing `.afk/config.yaml` at
its root. Nothing else in the repository configures the toolkit, and no file in
the toolkit names a repository path.

Read the effective configuration with the one reader; never parse the file:

```
afk-python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" effective --json
afk-python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" get verification.tiers.e2e.command
afk-python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" validate
afk-python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" committed <commit> --json
```

`validate` fails only on schema problems. For each repository-relative path
that is absent under the repository root it prints a `warning:` line to stderr
and still exits 0. The keys are `repo-hooks`, `setup.extra`,
`maven.reactor-pom`, `maven.formatter-config`, `maven.default-module` and
`npm.workspace-root`; `maven.worktree-seed` is a per-machine path and is not
checked.

Bash gates source the flat export once per gate run through `hooks/lib/config.sh`
and read the fixed `AFK_CFG_*` names.

## Discovery

Highest precedence first:

| Layer | Path | Purpose |
|---|---|---|
| explicit | `$AFK_CONFIG` | a named file, for tests and one-off runs |
| local overlay | `<git root>/.afk/config.local.yaml` | gitignored, per developer, this checkout only; may not set `schema` |
| shared overlay | `<git common dir>/afk/config.yaml` | untracked, per developer, read by every worktree of this repository — the default home for a developer's own `developer:` block; may not set `schema` |
| repository | `<git root>/.afk/config.yaml` | committed, the repository's contract |
| machine | `~/.afk/config.yaml` | per-machine defaults across repositories |
| built-in | — | the defaults below |

Layers deep-merge: a mapping merges key by key, any other value replaces. Both
files absent is a supported state — the built-in defaults apply.

`committed <commit> --json` reads only `.afk/config.yaml` from the verified Git
commit and applies built-in defaults. An absent committed file uses those
defaults. This command ignores machine, shared, local, and environment layers.
Glossary gates use this view at the recorded merge base after refreshing the
target reference. An unreadable commit or invalid configuration fails closed.

## Starting a repository off

```sh
afk-python scripts/afk-config.py init      # --force to replace an existing file
```

Writes a starter `.afk/config.yaml` from what the repository can answer about
itself: the forge from the origin remote's host, the build gates from a root
`pom.xml` or a `mvnw` / `mvnw.cmd` wrapper and from `package.json`, the base
branch from `origin/HEAD`. Anything it cannot read is written as a commented
`TODO` rather than a plausible guess; a wrong value that validates is harder to
notice than a missing one.

A Maven reactor POM is a `TODO` that lists the candidates, unless it is a root
`pom.xml` or the only root `*pom.xml`. When `init` cannot decide the tracker
and the Jira credential chain (`PROVIDERS.md`) resolves `JIRA_BASE_URL`,
`tracker` and `jira.project` are `TODO`s too. When the machine layer
(`~/.afk/config.yaml`) already sets a `tracker` or `forge` other than `none`
that `init` cannot detect, `init` writes that value as a `TODO` comment instead
of `none`, so the repository file does not shadow it; an inherited `tracker`
picks the matching template block, and `github-issues.repo` stays a `TODO`
unless the remote is on `github.com`.
`init` prints the keys it left as `TODO` on one line.

The file it writes always passes `validate`. `/afk:setup` runs it for you when
the file is absent.
`init` refuses when the base branch or the main worktree already carries
a config: restore it (`git checkout <base> -- .afk/config.yaml`), or merge
or rebase that branch, instead of scaffolding a second contract.

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
review:
  ledger-only-paths:
    - plan/review/**
    - plan/JOURNAL.md
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
| `artifacts` | map | `service-map` |
| `glossary` | map | `manifest` (optional repository-relative path to the versioned JSON manifest; see [Glossary manifest](#glossary-manifest)) |
| `maven` | map | `reactor-pom` (the POM every reactor run targets), `formatter-config` (formatter profile file), `formatter-plugin` (`group:artifact:version` of the formatter plugin), `default-module` (app-start's default), `skip-ui-flag` (one argument, e.g. `-DskipUi=true`), `worktree-repo` (`isolated` \| `shared`), `worktree-seed` (`auto` \| `none` \| a path), `worktree-seed-exclude` (globs the seed skips, default `*-SNAPSHOT`) |
| `npm` | map | `lint` (lint command and its fixed arguments, split on whitespace; changed files appended), `workspace-root` (where a new worktree installs), `worktree-install` (`ci` \| `none`), `worktree-command` (argv words restoring the dependencies, default `npm ci`) |
| `verification` | map | `tiers`, `env` |
| `repo-hooks` | string | repository-relative path to the hook manifest; default `.afk/hooks.json` |
| `setup` | map | `extra`: repository files `/afk:setup` reads as extra register rows |
| `worktree` | map | what a new worktree carries over from the checkout it was cut from — `copy` (repository-relative files and directories, default `.mcp.json`, `.claude`, `.run`, `.idea`), `copy-personal` (`false` copies nothing), `copy-ignored-claude-md` (`false` skips the gitignored instruction-file sweep — the key name is kept for compatibility, but the sweep now copies gitignored `AGENTS.md` files as well as `CLAUDE.md`). Build-system state is NOT here: each build gate provisions its own. |
| `investigation` | map | `boundaries`, `generated`, `reactor` — which boundary classes this repository actually has, and how to enumerate each. Optional: absent means the investigation scripts run their generic defaults only, and a class with no method is reported `unverified(no method)`, never as absence. |
| `report-issue` | map | `repository` (`owner/name` or its GitHub URL: where `/afk:report-issue` files approved plugin issues; absent means the plugin manifest's `repository`), `auto-publish` (legacy Boolean, ignored; every GitHub write needs explicit human approval) |
| `review` | map | `ledger-only-paths` (repository-relative path globs that can close a final ledger-only review round; default `plan/review/**` and `plan/JOURNAL.md`) |
| `developer` | map | per-developer values — `trackerAssignee`, `mrReviewer`, `mrAssignee`, `worktreeBasePath`, `ideBinary`. Belongs in the shared overlay (one repository, all its worktrees), in `~/.afk/config.yaml` (a default for every repository), or, for a value that differs in one checkout, in that checkout's `config.local.yaml` — never the committed file, because each names a person or one machine's paths. `worktreeBasePath` names one repository's location, so `/afk:setup` never writes it to the machine file. There is no committed layer for them: `trackerAssignee`, `mrReviewer` and `mrAssignee` name a person, and a committed file never does, so `/afk:setup` asks each developer for their own in session, for each main checkout they name, suggesting the developer's own account for each assignee, and records the answers (`skills/afk/setup/MANIFEST.md` · H6). The two assignees pair up — `trackerAssignee` goes on every work item the plugin creates, `mrAssignee` on every change it opens. Resolve with `afk-config.py resolve <key>`, which applies the developer value, then (for `worktreeBasePath` alone) a derived one; nothing resolving it means fail closed (`skills/afk/bug/CONFIG.md`), except `mrAssignee`, which never gates — unset or `none` means no assignee. |

The domain glossary's entry point is NOT configurable: `/afk:glossary` fixes it
as a root `GLOSSARY-MAP.md` (`skills/utils/glossary/GLOSSARY-FORMAT.md`), and one
decision has one home.

Every map in the table is validated one level down: a child key that is not
listed is refused, named by its full dotted path. Below that level the names
are the repository's own — a transition name, a state name, a tier name — so
they are not constrained.

`review.ledger-only-paths` uses `/` separators. `*` matches one path segment.
`**` matches any number of segments. Globs are relative to the repository root.
Negation is not supported. A repository must list each wider path explicitly.

### Path templates

`repo-files.spec-dir` and `git.branch-template` expand a fixed placeholder set:
`{workId}`, `{ticket}`, `{ticket_lower}`, `{service}`, `{release}`, `{user}`. In
`repo-files.spec-dir`, `{user}` is the `USER`/`USERNAME` environment value, unchanged, and
an unknown placeholder is left alone rather than guessed.

`git.branch-template` under `scripts/create-worktree --name` adds `{name}`, the worktree
name, and reads `{user}` as the git `user.name` slug: lower case, spaces to `-`, only
`a-z 0-9 -`. In that mode every placeholder the plugin cannot resolve is filled with the
name too.

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
(`SessionStart` | `PreToolUse` | `Stop` | `WorktreeCreated` | `PreCommit`), `matcher` (a regular expression
matched against the tool name, or `*`), `timeout` in seconds, and `script`, a
repository-relative path. A script that resolves outside the repository root is
refused. What the launcher does with a handler it cannot run is pinned by
`scripts/tests/test_run_hook.py`. `hooks/run-hook.py` runs the matching entries in declaration order and
exports `AFK_PLUGIN_ROOT` to each. A declared handler this checkout cannot run
is a configuration error, and one that gives no verdict inside its `timeout` is
a timeout: on `Stop` and `PreToolUse` either blocks the turn and names the entry,
so a gate cannot go missing quietly. The timeout counts the whole run, shell
start-up included, so a handler on a host that scans every process start keeps
to bash builtins. A `PreToolUse` verdict
is the deny JSON (`hookSpecificOutput.permissionDecision: "deny"`) at exit 0: one
harness treats exit 2 as a failed hook and runs the tool. The launcher writes it
without a shell; it parses to the object `afk_emit_deny` writes on every provider
(semantic JSON parity — key order and spacing are no contract). A `Stop` verdict is the
`{"decision":"block","reason":...}` object. A script that exits non-zero, or prints its
own refusal, is a refusal: the launcher never passes a handler's own verdict or exit
code through on these events. It gathers every refusal and prints one verdict in that
shape at the adapter's code. With no POSIX shell a matching call is blocked too.

`PreCommit` runs at an agent-driven commit, after the plugin's commit gates
(`hooks/precommit-gates.sh`). Handlers run in declaration order, so declare the
cheap ones first; the first one that exits non-zero, times out or cannot run
blocks the commit, and no later handler runs. `matcher` must be `*` and `timeout` a
finite positive number of seconds; every entry is checked before any handler runs. Each
handler reads `AFK_STAGED_TREE` (the index as a tree id) and `AFK_STAGED_PATHS`,
a file with one `<status>\t<path>` line per staged change in `git diff --name-status`
form: `A`, `C`, `D`, `M` or `T`, and `R<score>\t<old>\t<new>` for a rename. Deletions
are listed, and handlers judge the staged bytes. Each run appends a
`gate-latency.jsonl` line with `"event":"PreCommit"` (`hooks/README.md`
"Latency metrics & budget"). Without `afk-python` the handlers cannot run, and the
commit blocks whenever the repository could declare them: `.afk/hooks.json` exists,
or any Discovery layer mentions `repo-hooks` or cannot be read. The shell parses
neither file; `/afk:setup` installs the launcher. `.claude/hooks/.gate-disabled`, `AFK_SKIP_PRECOMMIT_GATES=1` and
`git commit --no-verify` skip them with the plugin's gates.

`WorktreeCreated` runs after `scripts/create-worktree --name` makes a worktree: each
matching script runs inside the new worktree with `AFK_WORKTREE_PATH` and
`AFK_WORKTREE_BRANCH` set and the event JSON on stdin. A script that fails adds a
warning naming it; the worktree stays. Scripts run after build provisioning. For a
worktree the harness's worktree tool creates, both run in the background after the
tool has its path; their output goes to the worktree's `afk/setup.log` git path
(`git rev-parse --git-path afk/setup.log`).

### Investigation boundaries

`investigation` declares this repository's instances of the generic boundary
classes B1–B14 that `INVESTIGATION.md` (plugin root) owns. Declarative only: a
`pattern` is a regular expression handed to `git grep`, never a command.

```yaml
investigation:
  boundaries:
    - name: event-listener
      class: B11
      pattern: '@\w*EventListener\b'
    - name: ui-caller
      class: B10
      paths:
        - '*-ui/src'
      pattern: 'serviceBaseUrl\('
    - name: message-name
      class: B4
      judgment-only: true
      site: path/to/the/site/that/builds/the/name
      note: built by concatenation at start-up; a search cannot enumerate it
  generated:
    - target/generated-sources
  reactor:
    - pom.xml
```

Each `boundaries` entry needs `name` and `class` (`B1`–`B14`), then exactly one
enumeration method: `pattern`, or `judgment-only: true` with the `site` an agent
must read. A declared instance **adds** to the generic default of its class and
never replaces it: declared and default patterns both run, and `judgment-only`
adds a site to read beside whatever search the class already had. A declared
`site` that is not in the repository makes the class `unverified`, never
evidence. `paths` narrows the entry's own search: a block list of git pathspecs
(a glob or a directory prefix) passed after `git grep --`. `note` carries the
gotcha. `generated` lists build output directories or files — present output is
searched on disk, tracked or not; absent output is reported
`frontier(unbuilt)`, never as absence. `reactor` lists the aggregator
manifests the build-graph class (B7) parses.

### Paths in the investigation block

Every path here — `generated`, `reactor`, an entry's `paths` — is
repository-relative with forward slashes. Write it however reads well:
a trailing `/`, a doubled `//`, a backslash separator, and a leading `./` all
fold to the one spelling at the read, so what a consumer receives is `gen`
whichever of those was written. A value that cannot fold to a
repository-relative path — absolute, drive-lettered, or holding a `..` segment
— is a configuration error, reported before any run starts.

## Glossary manifest

`glossary.manifest` selects a committed file owned by the repository's team.
Omit the key until prerequisite adoption reaches the target branch.
`glossary: null` also disables the manifest.
The glossary adapter reads the pointer, manifest, ownership map, and baseline definitions
from the recorded merge base. Feature files and local overlays cannot change
that authority.

The manifest is strict JSON. Version 1 requires exactly these fields:

| Field | Type | Contract |
|---|---|---|
| `version` | integer | `1` |
| `roots` | string list | Non-empty repository-relative directories or files eligible for search. |
| `exclusions` | string list | Additional repository-relative path globs; an empty list is valid. |
| `routes` | object list | Non-empty list of the route records below. |

Every route requires exactly these fields:

| Field | Type | Contract |
|---|---|---|
| `id` | string | Non-empty and unique within the manifest. |
| `path_patterns` | string list | Globs that match changed repository paths. |
| `domain_areas` | string list | Exact names of declared domain areas. |
| `glossary_path` | string | Repository-relative glossary path listed in `GLOSSARY-MAP.md`. |
| `owner_chain` | string list | Non-empty list of human owner identifiers. |

Duplicate JSON keys, duplicate list values, unknown fields, unsupported
versions, absolute paths, and parent traversal fail validation. Paths use `/`;
the reader accepts backslash separators and normalizes them. A route needs
at least one path pattern or domain area. The ownership map remains the
authority for glossary targets; the manifest supplies delivery routes and
owner chains.

Each definition's `Owner` is the exact canonical path of its owning glossary,
such as `billing/GLOSSARY.md` or the shared root `GLOSSARY.md`.
The pinned ownership map must list that path. Manifest routes targeting the
path resolve its human owner chains. A definition cannot name another
glossary, a route ID, a map label, or an account as its `Owner`.
Ownership reads and writes both enforce this rule.

An ordinary definition revision retains its adopted `ID`. A replacement adds
a new definition with `Replaces` naming the prior ID and retains the prior
definition so the reference still resolves. A new ID that reuses a prior
term or alias requires that explicit relationship. Rename the prior canonical
term when needed to keep spellings unambiguous.

Before a definition write, call `read_definition_source(snapshot, path)`.
It returns the pinned feature definition and exact observed working bytes,
after checking pinned ownership and allowing Git's CRLF/LF conversion.
Pass those bytes to `write_definitions(snapshot, path, expected, updated)`.
The writer checks the head and expected bytes again immediately before
replacement. It returns the replacement bytes for the next sequential write.
Changed content causes an error and remains untouched. Committed control
authority still comes from the merge base.

All glossary writes share an operating-system advisory lock under the absolute
Git common directory at `afk/glossary-lifecycle/write.lock`. The writer holds
it through content checks, validation across glossaries, and atomic replacement.
Linked worktrees use the same lock. Acquisition waits at most 10 seconds by
default; the adapter's `lock_timeout` argument sets a different bound.
A timeout raises `RepositoryLockTimeout`, a typed repository error.
The lock protects cooperating writers; expected bytes still detect outside edits.

Search uses regular UTF-8 files at the pinned feature head. The file must be
tracked and within both configured roots and the explicit feature scope.
The adapter applies mandatory exclusions from `BUILTIN_EXCLUSIONS` in
`scripts/glossary_lifecycle/repository.py`, then manifest and feature exclusions.
These exclude generated output, dependencies, logs, fixtures, seeds, and data
exports. Binary content and symlinks are ineligible. Additional repository
formats or export locations belong in `exclusions`.

The default provider uses deterministic token overlap and identifies its
method as `token-overlap-v1`, with model `none`. It ranks glossary term IDs
against the eligible source text. Each area returns at most 20 candidates
with 3 source snippets each. Evidence records roots, exclusions, method,
model, excluded paths, candidate counts, and truncation. Provider errors
fail the operation. Exact term and route matches have no candidate cap.

## Secrets

A configuration file holds environment variable NAMES, never values.
`jira.credentials-env` lists the variables the Jira adapter reads. Values come
from the environment or the harness credential store. A developer's own
non-secret values live under `developer:` in the shared overlay or
`~/.afk/config.yaml`, or in the gitignored `.afk/config.local.yaml` when one
checkout needs a different value.

The subset, the discovery order, the child keys of every map above, the
readable failure of `validate FILE`, and the agreement between the three views
are pinned by `scripts/tests/test_afk_config.py`; the scaffolder and the
developer-value resolution order by `scripts/tests/test_afk_config_init.py`; worktree copying and provisioning by `scripts/tests/create-worktree-smoke.sh` and `scripts/tests/worktree-provision-smoke.sh`; `scripts/tests/samples/monorepo-config.yaml`
is the large-repository fixture it validates.

## The shell view

`hooks/lib/config.sh` sources `afk-config.py export-shell` once per gate run and
exports:

- a scalar as `AFK_CFG_<PATH>` — `git.base-branch` becomes `AFK_CFG_GIT_BASE_BRANCH`
- a list as `AFK_CFG_<PATH>_COUNT` plus `AFK_CFG_<PATH>_0`, `_1`, …
- `AFK_CFG_LOADED=1` once the export ran
- `AFK_CFG_LOAD_FAILED`, set by `config.sh` to the reason when the export could not
  run; the defaults come back and the commit gates print the reason

Every value is shell-quoted at export time, so a pattern containing spaces or
`;` cannot become a command.

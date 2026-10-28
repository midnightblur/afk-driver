# CONFIG.md — the consuming repository's contract with AFK Toolkit

A repository tells the toolkit what it is by committing `.afk/config.yaml` at
its root. Nothing else in the repository configures the toolkit, and no file in
the toolkit names a repository path.

Read the effective configuration with the one reader; never parse the file:

```
afk-python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" effective --json
afk-python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" get verification.tiers.e2e.command
afk-python "$AFK_PLUGIN_ROOT/scripts/afk-config.py" validate
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

Layers deep-merge: a mapping merges key by key, any other value replaces;
"Developer settings (K1–K5)" below names the two exceptions under `developer:`.
Both files absent is a supported state — the built-in defaults apply.

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
| `maven` | map | `reactor-pom` (the POM every reactor run targets), `formatter-config` (formatter profile file), `formatter-plugin` (`group:artifact:version` of the formatter plugin), `default-module` (app-start's default), `skip-ui-flag` (one argument, e.g. `-DskipUi=true`), `worktree-repo` (`isolated` \| `shared`), `worktree-seed` (`auto` \| `none` \| a path), `worktree-seed-exclude` (globs the seed skips, default `*-SNAPSHOT`) |
| `npm` | map | `lint` (lint command and its fixed arguments, split on whitespace; changed files appended), `workspace-root` (where a new worktree installs), `worktree-install` (`ci` \| `none`), `worktree-command` (argv words restoring the dependencies, default `npm ci`) |
| `verification` | map | `tiers`, `env` |
| `repo-hooks` | string | repository-relative path to the hook manifest; default `.afk/hooks.json` |
| `setup` | map | `extra`: repository files `/afk:setup` reads as extra register rows |
| `worktree` | map | what a new worktree carries over from the checkout it was cut from — `copy` (repository-relative files and directories, default `.mcp.json`, `.claude`, `.run`, `.idea`), `copy-personal` (`false` copies nothing), `copy-ignored-claude-md` (`false` skips the gitignored instruction-file sweep — the key name is kept for compatibility, but the sweep now copies gitignored `AGENTS.md` files as well as `CLAUDE.md`). Build-system state is NOT here: each build gate provisions its own. |
| `investigation` | map | `boundaries`, `generated`, `reactor` — which boundary classes this repository actually has, and how to enumerate each. Optional: absent means the investigation scripts run their generic defaults only, and a class with no method is reported `unverified(no method)`, never as absence. |
| `report-issue` | map | `repository` (`owner/name` or its GitHub URL: where `/afk:report-issue` files approved plugin issues; absent means the plugin manifest's `repository`), `auto-publish` (legacy Boolean, ignored; every GitHub write needs explicit human approval) |
| `review` | map | `ledger-only-paths` (repository-relative path globs that can close a final ledger-only review round; default `plan/review/**` and `plan/JOURNAL.md`) |
| `developer` | map | per-developer values — `trackerAssignee`, `mrReviewer`, `mrAssignee`, `worktreeBasePath`, `ideBinary`. Belongs in the shared overlay (one repository, all its worktrees), in `~/.afk/config.yaml` (a default for every repository), or, for a value that differs in one checkout, in that checkout's `config.local.yaml` — never the committed file, because each names a person or one machine's paths. `worktreeBasePath` names one repository's location, so `/afk:setup` never writes it to the machine file. There is no committed layer for them: `trackerAssignee`, `mrReviewer` and `mrAssignee` name a person, and a committed file never does, so `/afk:setup` asks each developer for their own in session, for each main checkout they name, suggesting the developer's own account for each assignee, and records the answers (`skills/afk/setup/MANIFEST.md` · H6). The two assignees pair up — `trackerAssignee` goes on every work item the plugin creates, `mrAssignee` on every change it opens. Resolve with `afk-config.py resolve <key>`, which applies the developer value, then (for `worktreeBasePath` alone) a derived one; ids, meanings and the missing-value rule: "Developer settings (K1–K5)" below. |

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

## Developer settings (K1–K5)

Five per-developer values under `developer:`. Every one is optional, so a
developer can often run the plugin having configured nothing at all. Read them
through `scripts/afk-config.py resolve <key>`, never by opening a file and
never with `get`: `resolve` applies the whole chain in one place. Exit 0 prints
the value; exit 1 means nothing supplied it. Provisioned and probed by the
workflow doctor (`skills/afk/setup/MANIFEST.md` · H6).

| Layer | File | Holds |
|-------|------|-------|
| Machine | `~/.afk/config.yaml` | defaults for every repository on the machine |
| Repository | `<git common dir>/afk/config.yaml` | one repository's values, read by all its worktrees; untracked; the default `/afk:setup` offers |
| Checkout | `<repo>/.afk/config.local.yaml` | a value that differs in ONE checkout; gitignored |

The committed `.afk/config.yaml` holds none of these keys: K1, K2 and K5 name a
person, and a committed file never names a person. `validate` refuses a
`developer:` block there, and nothing reads one, even through `$AFK_CONFIG`. Resolution, highest first:
the `developer:` value from any layer (checkout beats repository beats
machine), then — for `worktreeBasePath` alone — a derived value, then nothing.
An empty `developer:` block, or a key left blank, overrides nothing.

| ID | Key | Type | Meaning | Falls back to |
|----|-----|------|---------|---------------|
| K1 | `trackerAssignee` | string | Account id or email every work item the plugin creates is assigned to — bug tickets and spinoff tickets. The tracker adapter resolves it by user search | nothing — a person has no default |
| K2 | `mrReviewer` | string | Forge user assigned as reviewer on a change the plugin flips Ready | nothing — a person has no default |
| K3 | `worktreeBasePath` | string | Base directory under which fixer worktrees are created | derived: a sibling directory `<main-checkout-name>-worktrees` beside the main checkout |
| K4 | `ideBinary` | string | Path to the IDE executable launched for interactive worktree creation | nothing — no default could be right |
| K5 | `mrAssignee` | string | Forge user every MR/PR the plugin opens is assigned to | nothing — a person has no default |

K3's derivation reads `git rev-parse --git-common-dir`, which answers with the
main checkout even from inside a worktree, so every worktree of one repository
agrees on the directory. A bare clone, a submodule, or a main checkout whose
git directory lives outside it derives nothing and needs the key. A linked
worktree of that last kind takes the folder `git worktree list` names first.

**A missing value.** The literal `none` for K1, K2 or K5 reads exactly as an
unset key, and overrides a broader layer's value — it records "nobody". When an
assignee or reviewer resolves to nothing:

| Situation | What happens |
|-----------|--------------|
| a person is in the conversation | ask them, record the answer per H6 Fix steps 2-4, resolve again |
| a hands-off run, or the person declines | file the work item or open the change unassigned, with no reviewer, and name the missing key in the run's report |

An unresolved K3 stops the worktree creation that needs it and names the key;
an unset K4 only skips launching the IDE. A skill may keep a stricter rule for
its own operations and states it on its own page.

New keys may be added; existing keys are never removed or repurposed. An
unknown key under `developer:` is a validation error, so a typo is named rather
than silently ignored: `resolve` names it on stderr and H6 names it too, with
the file that holds it.

A hypothetical `~/.afk/config.yaml` that answers K1, K2, K4 and K5, with K3
derived:

```yaml
developer:
  trackerAssignee: dev@example.com   # account id or email
  mrReviewer: reviewer.name          # forge user who reviews this developer's changes
  mrAssignee: my.name                # forge user every opened change is assigned to
  ideBinary: C:/Program Files/JetBrains/IntelliJ IDEA/bin/idea64.exe
```

A repository with a different reviewer adds its own `developer:` block in
`<git common dir>/afk/config.yaml`; every worktree of it reads that block.

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

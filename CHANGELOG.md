# Changelog

Every dev-visible change to the toolkit, newest first. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the versions are
[SemVer](https://semver.org/spec/v2.0.0.html). Internal refactors, wording
sweeps, and review-fix churn are deliberately omitted.

After updating, skim the versions you missed, then reload the plugin (and run
`/afk-toolkit:setup` if an entry says the dependency set changed). The
SessionStart notice (`hooks/update-notice.sh`) prints these same sections when
a newer tag exists.

Maintenance: a commit shipping a dev-visible change adds its line under
`## [Unreleased]` **in the same commit** — trigger owned by this file's
`FRESHNESS.md` registry row. A release moves that section under its version
heading, and `hooks/release-gate.sh` refuses a tag whose version is not the
first released heading here.

## [Unreleased]

## [1.0.13] - 2026-09-05

### Fixed

- **Adapter answers quoting a Windows path were not valid JSON**, so the driver
  read no status and wrote no marker, and a degraded worktree was re-provisioned
  on every run. The backslashes went out raw. Only answers that quote a path
  were affected — the warning paths, which on Windows is where every path is a
  Windows path. Backslashes are now escaped before the quotes, and a smoke
  assertion parses an answer holding one.

## [1.0.12] - 2026-09-05

One fix, released on its own because the thing it prevents cannot be undone.

- **Migration:** none. Upgrade before you provision anything, especially a
  worktree whose `.mvn/maven.config` you wrote yourself.

### Fixed

- **The maven build gate could destroy a `maven.config` the worktree already
  had.** 1.0.11 wrote its own single line over the file: a worktree pointing
  `maven.repo.local` at a deliberate second repository — another toolchain's,
  say — silently lost that, and any other flag in the file went with it. The
  build then ran against the wrong repository, which is the kind of failure
  nobody connects to having cut a worktree. Now a different `maven.repo.local`
  reports `degraded` and the file is left exactly as it is, and the repository
  line is APPENDED, so other flags survive. Found by dry-running the 1.0.11
  provisioner over 31 real worktrees, one of which was in exactly that state;
  because it was a dry run, nothing was lost.

## [1.0.11] - 2026-09-04

Cutting a worktree wrote one build system's private local repository and ran one
build system's install, in a script every repository runs. A repository that
builds with neither got both; a repository that needs something else got
nothing. Both halves now belong to the build gate that understands them.

- **Migration:** nothing to do. Worktrees you already have are adopted on the
  next run — the state they carry is recognised and kept, not redone. The old
  flags still work: `--no-npm` and `--no-m2` mean `--skip-build-gate npm` /
  `--skip-build-gate maven` and say so once; `--m2-seed` is ignored, and its
  value belongs in `maven.worktree-seed` in `.afk/config.yaml`.

### Added

- `scripts/worktree-provision` — asks every selected build gate to provision a
  worktree for itself, and does nothing a second time. What it did is recorded
  in the worktree's git admin directory, never in its tree, so it never shows up
  in `git status` and never blocks `git worktree remove`. A worktree that
  already carries the state is **adopted**, which is how worktrees made before
  this release come forward without a migration step.
- The `worktree-provision` verb on both build-gate adapters, with the keys each
  one reads: `maven.worktree-repo`, `maven.worktree-seed`,
  `maven.worktree-seed-exclude`; `npm.worktree-install`, `npm.worktree-command`.
  Each adapter's `CONTRACT.md` is the description of what it does.
- A `worktree:` configuration block — `copy`, `copy-personal`,
  `copy-ignored-claude-md` — so a repository whose personal files are somewhere
  else changes a key instead of a script.
- Two smoke tests, both in a disposable temp repository with stub build tools:
  `scripts/tests/create-worktree-smoke.sh` and
  `scripts/tests/worktree-provision-smoke.sh`.

### Changed

- `create-worktree` moved from `skills/afk/bug/scripts/` to `scripts/`: three
  skills already called it, and a shared script living inside one skill's
  directory said the wrong thing about who owns it.
- `genericity-gate.sh` gained check 0: a generic script under `scripts/` naming
  a build system blocks. The doctrine was already written down and was still
  violated, which is the same reason every other check in that gate exists.

### Fixed

- The scaffold wrote `branch-pattern:` with nothing after it, which parses as
  null rather than the empty string the schema documents. Both read as "the
  branch-name gate is off", so nothing behaved differently; the file now says
  what it means. Found by reading the scaffold `init` produced on a real
  repository, after v1.0.10 was tagged.

## [1.0.10] - 2026-09-04

Configuring a repository was the part of adoption nobody had written down. The
file was hand-authored from a schema document, and every developer then repeated
a personal setup step in every checkout. Both are gone.

- **Migration:** run `/afk:setup` once. It moves your personal values to
  `~/.afk/config.yaml`, where one answer covers every repository and every
  worktree on the machine. Nothing breaks if you don't: a `developer:` block in
  a checkout's `.afk/config.local.yaml` still wins where it exists.

### Added

- `afk-config.py init` writes a starter `.afk/config.yaml` from what the
  repository can answer about itself: forge from the origin remote's host
  (a self-hosted GitLab is still GitLab), build gates from a root `pom.xml` /
  `package.json`, base branch from `origin/HEAD`, tracker `github-issues` when
  the repository is on github.com. Everything it cannot read is a commented
  `TODO`, never a plausible guess — a wrong value that validates is harder to
  notice than a missing one. What it writes always passes `validate`, and it
  refuses to overwrite an existing file without `--force`.
- `/afk:setup` gained a step 0: no `.afk/config.yaml` → scaffold it, walk the
  human through the `TODO`s, re-validate, and say to commit it. Present → skip,
  silently. It will not guess a tracker project or a module name on anyone's
  behalf.
- Committed team defaults `tracker-defaults.assignee` and `forge-defaults.reviewer`.
  Who reviews and who is assigned are facts about a team, not about a laptop, so
  they belong in the file the team shares.
- `afk-config.py resolve <developerKey>` — one place that knows the order, so no
  caller has to. Exit 1 means nothing supplied the value and the caller fails
  closed.

### Changed

- **Every `developer:` key is now optional.** `trackerAssignee` and `mrReviewer`
  fall back to the committed team defaults. `worktreeBasePath` is derived: a
  sibling directory `<main-checkout-name>-worktrees`, read through
  `git rev-parse --git-common-dir` so every worktree of one repository agrees on
  it. `ideBinary` has no default because none could be right. A developer who
  configures nothing can now run the bug pipeline in a repository that commits
  its defaults.
- The recommended home for personal values is `~/.afk/config.yaml`, the machine
  layer the resolver already read. A checkout's `.afk/config.local.yaml` is for
  the case it was always for: one checkout that needs a different value.
  `/afk:setup` writes the machine file by default and offers the overlay.
- `create-worktree` asks `resolve` rather than `get`, and prints which base
  directory it used and where that came from.
- `H6` reports `ok` when the values resolve from ANY layer, and `n/a` when the
  repository commits no defaults and the developer set none — naming both places
  a value could come from, because either is a correct answer.

## [1.0.9] - 2026-09-04

### Fixed

- **`/afk:diagnose` was missing from the Claude Code catalog, and had been since
  it shipped.** Its description was a plain YAML scalar containing `": "`, which
  YAML reads as a nested mapping, so the frontmatter did not load. The harness
  said nothing: no error, no warning — the skill was simply absent, one entry
  short of a manifest that listed it. Codex parsed the same file and showed the
  skill, which is why the two catalogs disagreed. The description is now quoted;
  nothing else about the skill changed.
- The registry gate gained **check F**: every `SKILL.md` frontmatter must load as
  YAML and name its own directory. Nine releases of gates passed over this file,
  because every one of them checked that the skill was listed, catalogued,
  pointed at `LANGUAGE.md` — not that a harness could read it. A silent drop has
  no symptom to grep for, so the check parses instead. It uses PyYAML when
  present and falls back to the two plain-scalar rules a description realistically
  breaks, so a machine without PyYAML still catches this one.

## [1.0.8] - 2026-09-04

The plugin is named `afk`. Skills are `/afk:fix` again, as they were before the
extraction — the prefix is the plugin's name on both harnesses, so this is a
rename and not an alias. The marketplace keeps the name `afk-toolkit`, and so
does the product.

- **Migration:** remove the marketplace, re-add it, install `afk@afk-toolkit`,
  then run `/afk:setup`. On Codex, answer the hook-trust prompt once more — the
  trust key carries the plugin name, so renaming it invalidates all eight
  entries. Nothing carries over from a `afk-toolkit@afk-toolkit` install: uninstall
  it first, or the two sit side by side and their skills collide.

This is a breaking change in a patch release. There are no users yet, and the
owner chose the number; the line above exists because a version number cannot
say that on its own, and the session-start notice now prints it.

### Changed

- Plugin name `afk-toolkit` → `afk` in both `plugin.json` files and the
  `plugins[]` entry of both marketplace manifests. Skill prefix `/afk-toolkit:` →
  `/afk:`, install key `afk-toolkit@afk-toolkit` → `afk@afk-toolkit`, logical
  agents `afk:afk-*`, Codex stubs `afk-afk-*.toml`. Unchanged, because they were
  never the plugin's name: the marketplace, the `AFK_*` environment variables,
  the `afk_` bash prefixes, `skills/afk/`, and the agent source filenames.
- The tracker MCP launcher held one name for both the cache shape and the
  marketplace shape. Those are now different names, so it carries both. A 1.0.7
  install is not found by a 1.0.8 launcher, by design — the old shape is gone
  rather than kept as a fallback.
- The session-start notice lifts a `Migration:` line out of any newer changelog
  entry and prints it under "Action needed before it works:" above the body. A
  release that needs the reader to act says so in one line, and every future one
  gets the same treatment for free.
- Per-developer config moved from `.claude/afk.local.json` to a `developer:`
  block in `.afk/config.local.yaml`, read through `scripts/afk-config.py` like
  every other key. `skills/afk/bug/CONFIG.md` remains its contract, and the
  fail-closed matrix is unchanged. `K1 trackerAssignee` now reads "account id or
  email — the tracker adapter resolves it by user search", which is what the
  adapter has always done.
- `create-worktree` no longer carries its own JSON reader, and `setup_secrets.py`
  writes the block by editing the overlay rather than rewriting it, so keys it
  knows nothing about survive.
- `H6` probes the key through `afk-config.py` instead of stat-ing a file.

### Removed

- `.claude/afk.local.json`. The extraction plan said migrate once and retire it;
  the bug pipeline was still reading it.

### Fixed

- `native-contract-gate.sh` derived the expected Codex stub filename from a
  hardcoded `afk-toolkit-` prefix. The gate that exists to catch harness
  coupling carried the plugin's old name as a literal, and this rename is what
  found it.
- `release-gate.sh` found the marketplace's version row by matching a plugin
  entry whose name equalled the marketplace's own name. That held only while the
  two names were the same word. It now matches `plugin.json`'s name, and falls
  back to the sole entry when a marketplace carries exactly one plugin. This
  release is the first that could not be tagged without the fix.
- Four `native-contract-allow.txt` rows quote CHANGELOG text to waive a
  historical line. Renaming the identifiers rewrote the quotes while the
  changelog kept the old spelling, so the waivers stopped matching. Any
  allow-list that quotes an immutable record has this hazard; the rows are now
  pinned to the historical spelling.

## [1.0.7] - 2026-09-04

Four rows and checks that reported a healthy machine as broken, found by the
first audit run from an interactive session on the second harness. One of them
was shipped by 1.0.6 itself, and fixing it made the check honest enough to find
a real term-drift in the glossary the same day.

### Fixed

- The glossary check counted files that name a term in order to *talk about the
  check* — its own test fixtures and this changelog. So the term 1.0.6 reported,
  `One-live-fixer invariant`, acquired two consumers the day it was reported and
  the check went quiet about it. Any term the check names in a release note
  would have been silenced the same way, permanently. `CHANGELOG.md` and
  `scripts/tests/test_glossary_usage.py` no longer count as consumers.
- `H2` assumed a tracker exists. Run in a working directory with no
  `.afk/config.yaml`, the tracker resolves to `none`, `tracker_get` answers
  `unsupported` — the adapter contract working exactly as designed — and the row
  called it a failure. It is now conditional, and says so, as `C3` and `C3b`
  already were. `O7`'s `tracker_get` leg inherited the same assumption and the
  same fix; its catalog and role legs stand on their own.
- `C8` probed a Windows built-in with `command -v`, which reads `PATH`. A shell
  whose `PATH` omits `System32` reported `robocopy` as absent on a machine that
  ships it. The probe now falls back to a file test, which is the authority on
  Windows.
- `CLAUDE.md` told a maintainer that broadening the execute outcome status set
  means editing the autopilot park handling. It does not: autopilot parks on
  anything that is not a recognised success, deliberately, so no status is named
  in that skill and none should be. The audit read the instruction, found no
  `adversary_fail` token in the skill, and reported drift that was not there.

### Changed

- `GLOSSARY.md` headed the `FRESHNESS.md` table as **Freshness registry**, a term
  no doctrine file uses: `CLAUDE.md` and `FRESHNESS.md` say *artifact registry*
  and *registry row*. A coined synonym, in the file that forbids coining
  synonyms. The entry is now **Artifact registry**, keeps its body, names the
  row, and lists the old heading under `_Avoid_:`.
- A glossary entry may declare a legitimate shorter spelling under `_Also_:`
  (`skills/utils/glossary/GLOSSARY-FORMAT.md`). Prose writes a term's
  distinctive part and lets the sentence carry the rest — `one-live-fixer`
  inside a list of invariants — and that is correct usage, not drift.
  `_Also_:` records what readers do write, `_Avoid_:` what they should not; the
  check accepts the first as a consumer and never the second. This is what
  1.0.6 left reported for want of a way to say it, rather than a rule loosened
  to make a report go away.

### Documentation

- The README now says what the first-session hook-trust prompt costs on a
  later upgrade: nothing, unless a release changes `hooks/hooks.codex.json`.
  The agent stubs are the opposite and need `/afk-toolkit:setup` after every
  upgrade. `providers/CONFORMANCE.md` records how that was established.
- Two counts written into README prose have gone stale since they were
  written: three agent stubs (there are four) and a 40-skill catalog. Both now
  point at what declares them, the same correction `O7` got in 1.0.6.

## [1.0.6] - 2026-09-04

The first audit run on the second harness. It found three things, and the
largest of them was the audit itself: a check that reported sixteen live
glossary terms as unused. The 1.0.5 entry below says this programme had stopped
finding things. That was written after one harness had been audited.

### Fixed

- The glossary check compared a heading's exact case, its trailing parenthetical
  qualifier, and its slash-joined term list against a tree where nobody writes it
  that way. Prose says `sign-off` where the heading says `Sign-off`, and
  `review policy` where the heading says `Review policy (lean / full)`. Sixteen
  terms were reported as having no consumer; every one of them was in use.
  Acting on that report would have deleted sixteen live entries.
  `scripts/glossary_usage.py` now normalizes before comparing and says in its own
  output that a zero-hit is a prompt to look, not a verdict.
  The 1.0.4 entry describes a probe that failed on a healthy machine; this is the
  same disease in a check rather than a probe, and the 1.0.5 fix for the same row
  pointed the wrong way — it corrected two headings so the grep could see them,
  which makes the glossary serve the check instead of the reader. No glossary
  entry is touched by this release.
  One heading is still reported, deliberately: `One-live-fixer invariant`, which
  prose writes as `one-live-fixer` with the category noun factored out into the
  sentence. Stripping a trailing category noun would need the check to know which
  nouns are categories, and would then hide a term that really is unused whenever
  it ends in one.
- `O7` required a session to list "all three agent roles". There are four, and
  `O5` lists four. The row now points at `O5` instead of carrying a number, which
  is what the row's own text asks of everyone else.

### Added

- `C9` and `C10` register `jq`, `timeout` and `curl` — external commands shipped
  code runs and the manifest never listed. Both rows are optional, because that
  is what they are: `hooks/lib/provider.sh` falls back to `grep` + `sed`,
  `hooks/tests/hook-smoke.sh` skips, and `hooks/update-notice.sh` exits 0 in
  silence. Required rows would raise a false alarm on every machine without them.
  The 1.0.5 sweep that added the missing environment variables missed these
  because it looked for variables, not commands.
- `scripts/tests/test_glossary_usage.py` pins the normalization against the
  sixteen headings the old check reported, as fixtures rather than as a snapshot
  of the current glossary, with a negative test per rule so the fix cannot
  regress into a check that reports nothing.

## [1.0.5] - 2026-09-03

The audit's last three findings, from the run after the run that fixed the
previous three. It has now stopped finding things.

### Fixed

- The glossary headed two terms with a spelling nothing uses. Every consumer
  writes the class token — the hyphenated form that appears in a finding's
  `class` field — and the glossary headed the entries with the prose form, so
  the term-usage check found a definition with no consumers and could not tell
  that apart from a term nobody needs. Both entries now lead with the token and
  keep the prose form beside it.

### Documented

- Two more variables the shipped adapters read that the register's table never
  listed: the default project key one tracker falls back to, and the
  `owner/name` fallback the other uses when the configuration names no
  repository. This is the second release to add missing rows to that table; the
  drift check that keeps finding them is doing exactly what it is for.

## [1.0.4] - 2026-09-03

Two probes that reported a healthy machine as broken. A register whose probes
cry wolf is worse than one row short: it teaches the reader to skim its failures.

### Fixed

- The agent-stub probe demanded that the baked plugin root match one exact
  string. That harness reports its root two ways — a marketplace directory and a
  versioned cache directory — and both are real, content-identical, and work.
  The probe now asks the question that matters: does the baked path resolve to
  the toolkit. It failed on a machine whose stubs were correct, which is exactly
  the failure mode that makes the previous release's genuine version-drift catch
  harder to see.
- The editor probe missed a system-wide installation, having missed a Toolbox
  installation in the previous release. Both times the editor was open while the
  row reported it absent. The location is added, and so is the rule: a probe that
  enumerates install locations is wrong until the next one is found, so a
  negative means "not found where I looked", never "not installed", and the fix
  is to add the location rather than to ask a human to install what they have.

## [1.0.3] - 2026-09-03

Everything here was found by running the setup register's own audit against the
previous release, on a machine that had been upgraded rather than freshly
installed. That is a state the audit had never been asked about before.

### Fixed

- **Upgrading the plugin silently broke all four agents on the second harness.**
  Setup bakes the installed plugin root into each agent stub, and that root
  carries the version, so every new version leaves all four stubs naming a
  directory that no longer exists. Nothing detected it: the stubs are valid
  files with a plausible path, and the failure appears only when an agent is
  spawned. The register's probe now also requires the baked root to exist, and
  the row states the rule it needed all along — re-run setup after **every**
  version change on that harness, not only when an entry says the dependency set
  changed.
- The IntelliJ row probed a package manager, which sees only what it installed.
  JetBrains Toolbox is the other common route and leaves nothing in that list,
  so the row failed on a machine where the editor was open at the time. The
  probe now also looks where Toolbox and the standalone installer put it.

### Documented

- Six environment variables that the code reads and the register's variable
  table never listed: the two forge remotes, the Obsidian vault, the repo-files
  spec directory, the compatibility marker one harness sets, and the per-job
  scratch directory a forge verb writes into. A variable that is read but not
  registered is one nobody knows to set, and one nobody knows to look at when it
  is wrong.

## [1.0.2] - 2026-09-03

### Changed

- **If you are on Codex CLI, 1.0.0 does not work — install 1.0.1 or later.** Its
  tracker MCP server never started there, so a session had no `tracker_*` tool
  at all and every skill that reads or writes a work item failed. Claude Code is
  unaffected at any version. 1.0.1 says what went wrong; this entry says plainly
  which versions are safe, because a reader deciding what to install should not
  have to infer it from a defect report.

### Documented

- Why the tracker launcher searches for its own installed root, which the design
  otherwise forbids: a search can find a stale copy as readily as the live one,
  so the rule was that the registration passes the root and the server never
  looks. One harness makes that impossible — it expands no placeholder in an
  `args` entry and exports no equivalent variable, so there is nothing to pass.
  The search is the narrowest thing that still works. An explicit argument, then
  the environment, are tried first and win whenever either exists; only when both
  are absent does it look, and then only at four fixed plugin-directory shapes
  directly under the user's home directory. It never recurses, never starts from
  a filesystem root, and never leaves the user's home directory. Recorded in
  `providers/CONFORMANCE.md` under the round-5 decisions as a deviation from the
  plan's rule, not as the intended design.

## [1.0.1] - 2026-09-03

### Fixed

- **The tracker MCP server never started on Codex CLI.** Codex expands neither
  `${PLUGIN_ROOT}` nor `${CLAUDE_PLUGIN_ROOT}` inside an `args` entry and
  exports no equivalent variable, so the launcher received the placeholder
  verbatim, could not find `mcp-servers/tracker/server.py`, and exited before
  the handshake. Every session on that harness therefore had zero `tracker_*`
  tools, while Claude Code — which does expand it — worked, which is how the
  defect reached a release. The launcher now finds its own installed root when
  no harness tells it, and the server ignores an argument that still carries an
  unexpanded placeholder instead of resolving it into a directory that cannot
  exist.

### Changed

- The setup register's O7 probe asked a new session for "exactly 40" plugin
  skills. It ships 41. The probe now counts the manifest, because a number
  written in prose is wrong the first time a skill is added.
- `CLAUDE.md` listed four gate scripts under `hooks/` that live elsewhere: the
  two PreToolUse guards belong to a consuming repository's own `.afk/hooks.json`
  and ship with no plugin, and the app-start and mutation probes moved to
  `adapters/build-gate/maven/` with the rest of the build-shaped gates.
- `CLAUDE.md` still described the changelog as dated one-liners without
  versions, which stopped being true when the release gate started enforcing
  four-way version agreement.
- Dropped the register row for `CROWDSTRIKE_GUARD_OFF`: it named a script this
  plugin no longer carries.

## [1.0.0] - 2026-09-03

### Added

- **The toolkit is a standalone plugin, installable from GitHub on Claude Code
  and Codex CLI.** It was a directory inside one company's monorepo; it is now
  `afk-toolkit@afk-toolkit`, a repository of its own, with the same skills,
  agents, hooks and MCP server.
- **Adapters.** Every external system the chain touches is a family with
  interchangeable kinds: `tracker` (`jira`, `github-issues`, `none`), `forge`
  (`gitlab`, `github`, `none`), `notes` (`repo-files`, `obsidian`, `notion`)
  and `build-gate` (`maven`, `npm`). A skill asks for a verb of a family; the
  configuration decides which directory answers. `ADAPTERS.md` is the map.
- **`.afk/config.yaml`.** A consuming repository states its kinds, its branch
  convention, its verification tiers, its build-gate settings and its own hook
  manifest in one file, read by one module (`scripts/afk-config.py`) for skills
  and hooks alike. `CONFIG.md` is the schema; `.afk/config.local.yaml` holds
  per-developer values and is gitignored.
- **Repository-owned hooks.** A repository declares its own gates in
  `.afk/hooks.json` and the plugin runs them without knowing what they are.
- **`hooks/release-gate.sh`** — a tag's version must equal both plugin
  manifests, the marketplace entry, and the first released changelog heading.
- **`hooks/update-notice.sh`** — a SessionStart notice when a newer tag exists,
  budgeted 2 seconds per step, cached 24 hours, silent on every failure.

### Changed

- **The nine tracker tools are `tracker_*`, not `jira_*`,** and the MCP server
  registers as `tracker`. It routes to the configured kind; the Jira adapter
  still accepts a pre-rename `jira` credential registration.
- **The forge is reached through 16 verbs** with the same field names on either
  host, so `ci-wait`, change intake, review comments and the merged proof no
  longer name a CLI. `ci-wait`'s exit codes are unchanged.
- **Nothing in the toolkit names a repository any more** — not a service
  directory, not a verification path, not a branch prefix, not a ticket key.
  Paths into a repository come from its configuration; plugin paths are
  `$AFK_PLUGIN_ROOT/…`, because the plugin is installed rather than checked out
  beside the work.
- **The per-developer key `jiraAssignee` is `trackerAssignee`.**

### Removed

- The register's section X (one repository's checkout, verification tree,
  environment tooling and JWT minter) and four workstation rows describing one
  company's machine build. A repository contributes its own rows through
  `setup.extra`.

### Fixed

Found by running every adapter kind against its real service before the
release, and each one was invisible to the gates, the fixtures and the tests.

- `forge: none` and `tracker: none` answered with an agent instruction instead
  of refusing: both still carried the `runner.type` of an early skeleton. The
  registry check now also requires `runner.type` to match its entry, so a kind
  cannot be mislabelled that way again.
- Dispatch for an `instruction` kind answered any word at all, so a typo read
  back as a supported verb. It now honours the kind's operations list.
- `github.remote` and `gitlab.remote` were documented and declared but never
  read: a forge always used the checkout's default project. Both kinds now
  resolve the project from that remote's URL, and both now load the
  configuration at all — a forge script runs in its own process and never
  inherited its caller's view of it.
- An inline `change-comment` failed with HTTP 422 on every Windows machine: the
  commit id carried the carriage return of a CRLF line into the request.
- The same path printed a Python traceback instead of an answer when the forge
  CLI was asked for a field it does not have.
- `reviewers: ["someone"]` reached both forge CLIs as the literal string
  `['someone']`.
- `tracker_search` rejected the comma-separated `fields` string that
  `tracker_get` requires. Both verbs now take either shape.
- `tracker: github-issues` could not close an issue unless the repository had
  configured `state-labels`. `open` and `closed` are GitHub's own states and
  are now always offered.
- The same kind passed the forge CLI's bare `'label' not found` through; it now
  names the label and says GitHub labels must exist before an issue can carry
  one.
- `change-close` on GitLab failed on any project that requires a passing
  pipeline before merging, because `glab mr close` reports the *merge*
  precondition. It now closes through the API.
- The UI lint gate stopped its workspace walk one directory above the
  repository root and its `workspace-root` fallback could never match `.`, so a
  repository whose only ESLint configuration sits at its root was gated on
  nothing and told the committer it had passed.
- `notes: notion` promised an archive on `note-delete`. A Notion MCP server
  that exposes no archive tool now produces a local delete plus `notion.error`,
  and both the contract and the procedure say so.


## Pre-1.0 (monorepo era)

The entries below are the plugin's history from before the extraction, grouped
by date rather than version. Paths, ticket keys and tool names in them are as
they were at the time.

### 2026-09-02

- **The retired lean-ctx helper is gone from every surface.** Its tool names left the crowdstrike-guard and explore-counter matchers and hook definitions, its optional setup dependency (H3) left the manifest, and skill prose reads/searches with the native Read/Grep/Glob vocabulary. Nothing changes for anyone who never installed it — it was optional and the file tools always did the same job. Re-approve the plugin hooks if your harness prompts (the definitions changed).

- **A Stop block is emitted as a decision, so every harness honours it.** Gate findings now leave `stop-gates.sh` once, through the provider shim: the text on stderr and a `{"decision":"block","reason":…}` object on stdout, with the exit code named by the active adapter. A harness that reads only the decision object recorded the previous stderr-plus-exit-2 form as a failed hook and let the turn finish — a gate that blocks on one machine and is silent on another is worse than no gate. The two adopted harness Stop gates (Java rules, i18n parity) go through the same emitter.

- **Every hook runs through one launcher.** A hook command string is parsed by whichever shell the harness picked, and `bash` on Windows often names the WSL stub, which cannot run these handlers — so a guard or gate reported a failed hook and no verdict. All commands are now `python "${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.py" plugin|repo <handler.sh>`: the launcher locates a real Git Bash, puts its toolchain on the child's PATH, resolves the handler under the plugin or the checkout, and forwards stdin and the exit code; native contract gate rule J refuses any other command shape. The no-`jq` envelope reader now tolerates whitespace too, which silently blanked every field on a pretty-printed envelope.

- **The shared Jira server finds its own credentials.** A harness may start the MCP child with a filtered environment, leaving the server no values to authenticate with. Its bootstrap now reads them from the exported variables first, then a `jira` server `env` block in the user's harness config files — nothing secret is committed.

### 2026-09-01

- **Shell handlers are pinned to LF, and the shared MCP server finds itself.** A harness that copies this tree into its own plugin cache runs the hook scripts through a POSIX shell, where a CRLF checkout is unparseable — every guard and gate silently reported a failed handler instead of a verdict. A scoped `.gitattributes` pins `*.sh` to LF and the native contract gate now blocks a CR byte in any shell handler. The shared `.mcp.json` no longer depends on plugin-root interpolation: its bootstrap resolves the root from the passed argument, the plugin-root variables, the checkout under `$PWD`, then the newest plugin cache under the user's home, so every harness reaches the same server.

- **The plugin is one native tree for every supported harness — no generator, no mirror.** Each harness discovers the same committed files through its own plugin mechanism (`.claude-plugin/` and `.codex-plugin/` manifests, shared `hooks/hooks.json`, shared `.mcp.json`, agent stubs copied unchanged), so a skill edit ships once and needs no regeneration step. `codex-sync/`, the drift gate, and the synced harness copy of `provider.sh` are gone; hook provider behavior now lives in one adapter per harness under `hooks/lib/providers/<id>.sh`. Harness-agnosticism is a standing requirement from now on: `CLAUDE.md` carries the rule, `PROVIDERS.md` carries the supported-harness registry, `CAPABILITIES.md` carries the capability matrix, `providers/CONFORMANCE.md` carries live proof plus the add-a-harness checklist, and `hooks/native-contract-gate.sh` blocks (Stop and commit) on harness vocabulary in skill prose, unsupported frontmatter, manifest/registry drift, a tracked generated mirror, or a missing adapter fixture.
### 2026-08-27

- **Fourteen recorded workflow lessons applied.** `/afk-toolkit:review` gains two hard
  rules that also reach every reviewer through `checklists/PRECEDENCE.md`: never
  verify a claim by re-running the command the reviewed record quotes as its own
  evidence, and open a cited document before overturning it. The settle loop
  (`SETTLEMENT.md`) gains **scope escalation** — two consecutive
  fix-one-leave-the-sibling findings widen the loop past the delta and add a
  `consistency-sweep` reviewer — plus a park-report contract, and its
  design-change carve-out no longer settles an observable runtime failure.
  `/afk-toolkit:preflight` PF-3 now routes all three settle-loop exits, not two.
- **`/afk-toolkit:execute` gains an `adversary_unrun` outcome.** A slice whose tiers are
  green and whose findings are settled, but whose Step 10.5 gate never got to
  run, is no longer reported as `review_fail` — it resumes at the gate instead of
  re-running from the top, and a `complex` contract now reserves budget for that
  gate up front. Two more execute rules: check a path before Write-creating at
  it, and read every subagent verdict from the spawning call rather than waiting
  on a notification that never arrives.
- **`/afk-toolkit:understand` teaches the right code.** Its diff base is the remote
  target, never the local `master` ref no one fast-forwards; deviations mined
  from the journal are now resolved against the code before they are taught; and
  the shell template no longer quotes its own injection slots, which a slot
  search used to match instead of the element.
- **Two gates stop lying.** `app-start-gate.sh` confirms a prior instance
  actually died before clearing its state file, and exits 3 (environment) naming
  the survivor instead of reporting a locked jar as a code failure. The i18n
  parity gate (PAYU007) scopes to the merger's own decisions during a merge, so
  merging master no longer blocks the turn on other teams' captions.
- **New `afk-runner-lite` subagent (Haiku) splits trigger-3 execution by
  judgment, not by output size.** Checks whose verdict *is* the exit code —
  formatter validate, linters, anchor greps, static-tier compiles — now route
  to it; test suites, reactor builds, and live tiers stay on `afk-runner`
  (Sonnet), because those verdicts turn a gate green. `/afk-toolkit:settle-mr`'s Java
  format + UI lint checks are the first callers. The cheap type never guesses:
  a result needing interpretation comes back `blocked — needs_triage: …` and
  the caller re-runs it on `afk-runner` — one wasted cheap call instead of a
  wrong verdict. Requires a **session restart**, not `/reload-plugins` (agent
  definitions are scanned at session start). Routing test + escalation rule:
  `DELEGATION.md` "Runner split"; tier names: `PROVIDERS.md`. On Codex the
  type exists but maps to the same Terra-at-low-effort as the digest tier —
  nothing below Terra ships, so the split saves nothing there.

### 2026-08-25

- **`/afk-toolkit:setup` offers two opt-in user preferences again** (deselected-by-
  default election on every run — the manifest's opt-in tier is back): **H7**
  installs the Simplified Technical English reply standard into the
  user-global steering files, so sessions outside the plugin follow it too;
  new **H8** installs a grilling-session render default — interactive
  explain/ask rounds render through lavish (`LAVISH.md`, new RP-10) even when
  no skill's own render point is in play.
- **Lavish browser tabs now show the page's own title instead of "Lavish
  Editor"**: `lavish-axi` pin bumped 0.1.36 → 0.1.43 (`LAVISH.md`) — the
  editor shell now mirrors the artifact's `<title>` (`{title} · Lavish`) and
  favicon into the tab, so concurrent review tabs are finally
  distinguishable. Restart the background server (`npx lavish-axi@0.1.43
  stop` with no session open) to pick up the new version.
- **Reviews can now classify a finding `product-debt`**: a real shortcoming in
  shipped code that was adjudicated and deliberately not fixed. Unlike
  `pattern-debt`, which is recorded under `plan/` and deleted with it at merge,
  product debt is written to a `## Known debt` section in the nearest
  `CLAUDE.md` — so the next agent on that ground reads why the obvious fix was
  rejected instead of proposing it again. `/afk-toolkit:preflight` gains **PF-4d**,
  which refuses to go green while an accepted product-debt finding has no home.

### 2026-08-24

- **Agents now trace load-bearing claims to code before stating them, or label
  them `unverified: <reason>`**: new "Truth grounding" principle in
  `harness/shared/core-services.md` (code over documents, cross every
  boundary, absence needs exhaustive enumeration, check specifics at claim
  time, label the unverified), pointed at from the `afk-reader` agent
  definition and `DELEGATION.md`'s return contract. Grounded in a mined
  catalog of 30+ retracted-claim incidents across 26 past sessions.

### 2026-08-19

- **Hands-off runs now take reversible decisions themselves instead of parking
  for you**: new plugin-root `DECISIONS.md` protocol — a mid-run fork (design
  conflict, spec inconsistency, review remediation choice) with a clear,
  branch-reversible winner is decided on the record (append-only
  `plan/DECISIONS.md` entry + a `decision(D-n)` journal line) and the run
  continues. One-way doors (migrations, external writes, human-locked aspects,
  plan reshapes) and ties still park — now as `needs_decision` naming the fork
  plus the agent's recommendation. `/afk-toolkit:autopilot`'s end-of-run report lists
  every auto-taken decision for audit; each is reversible on the branch.
- **A hung subtask subagent now wakes the orchestrator instead of stalling the
  run until a human asks**: new `hooks/stall-watchdog.sh` runs in a background
  shell beside every long-running child spawn and exits when the child's disk
  activity goes stale (or a hard cap passes) — the exit re-invokes the waiting
  orchestrator, making `/afk-toolkit:autopilot`'s wall-clock guard enforceable. The
  arm / fire → probe → park protocol, including killing the process tree a
  stopped task leaves behind (a forked JVM holds its port and steals broker
  messages), lives in `DELEGATION.md` "Stall watchdog"; a timeout park now
  rides the same journal + push-notification path as any other park
  (lesson L-0041).

### 2026-08-18

- **The settle loop can now end on its own**: `SETTLEMENT.md` gains two rules —
  a round's verdict may be written only after that round's sweep reports, and a
  round whose findings all target review artifacts rather than main or test code
  is remediated in place and closed, minting no further round. Together they stop
  a slice with stable code from failing round after round on its own bookkeeping
  (lessons L-0027, L-0028).
- **`/afk-toolkit:execute` reads the module's sidecars before it writes**: Step 5 now
  loads the `IMPL.md` / `TESTING.md` a touched module's `CLAUDE.md` announces,
  plus every matching `.claude/rules` file, before the TDD loop — the same
  documents Step 10's compliance reviewer checks the diff against, read at write
  time instead of found at the gate (lesson L-0024).

- **A field added to an existing entity now has to answer for the surfaces
  already exposing it**: the SDD's entity-design section (§4 L3) gains a
  *Surface reachability* line — per added/newly-mandatory field, one verdict per
  programmatic surface (agent tool schemas, import/export templates, public API
  DTOs), where "the feature touches no file under that surface" counts as the
  symptom rather than the answer. `/afk-toolkit:to-subtasks` gains the matching
  slice-time rule: a subtask emitting a **narrowed copy** of an existing type
  must reconcile field-by-field, write down what it dropped and why, and give
  every conditionally-required field its own assertion against the generated
  artifact. Both close the same escape — a projected input DTO silently missing
  a field, which reads green in every test that exercises only the fields it
  kept while no caller can make a valid call (lesson L-0039; payable's new
  "MCP schema parity" staple is the service-side half).
- **PRD mermaid figures render on Windows again**: `/afk-toolkit:to-ticket` resolves
  `mmdc`/`npx` on `PATH` before running them, so a missing `mmdc` now falls
  through to the `npx @mermaid-js/mermaid-cli` fallback instead of aborting the
  publish. Under the old `shell=True` call a missing command exited non-zero
  rather than raising, which killed the loop on the first candidate and left
  every diagram unrendered on machines without a global mermaid-cli.
- **Lavish session pages gain navigation chrome**: every session-default
  artifact now gets — injected at render, zero authoring cost — a sticky
  "On this page" rail (Now / Open / Blocked / Settled with counts), settled
  cards collapsed to their heading line, a floating jump-to-current-question
  control, and changed-this-round markers. Long grill sessions stop
  requiring scrolling past decided history. Page-writers emit the small
  `data-afk-item`/`-state`/`-fresh` markup grammar (`LAVISH.md` "Page
  anatomy"); pages without it render as before.
- **Render-point pages are authored by a persistent page-writer child**: at
  every lavish render point the orchestrator now hands page markup to one
  per-session `afk-implementor` page-writer — continued each round, not
  respawned — against a delta-shaped page brief; HTML stays out of the
  interview context; content decisions, render/poll, and feedback handling
  stay with the orchestrator (`LAVISH.md` "Authoring delegation";
  continuation vocabulary in `PROVIDERS.md`).
- **`writing-great-skills` → `writing-for-agents`** (upstream mattpocock
  rename adopted): the reference now covers any document an agent consumes —
  skills AND harness markdowns (CLAUDE.md, sidecars, `.claude/rules`) — and
  gains two levers (negation: prompt the positive; cache: the environment is a
  source of truth). Packaging-specific mechanics load lazily:
  `SKILL-MECHANICS.md` (invocation, descriptions, routers) and
  `HARNESS-MECHANICS.md` (inclusion bar + placement engine, moved here from
  `/afk-toolkit:claude-md`, which slims to steward mechanics and points). Old
  `GLOSSARY.md` merged into the skill body. `/reload-plugins` to pick it up.

### 2026-08-17

- **One writing doctrine, one home.** `CONCISION.md` merged into `LANGUAGE.md`
  (plugin root): which words (Simplified Technical English), whose terms
  (glossaries), and how much (concision bar + steering-notes rules) now live in
  one file, binding on every producing surface — current skills and any added
  later. Every pointer (skill/agent pointer lines, emitter/template read-first
  lines) retargeted, and pointers no longer restate any rule — they only name
  the home. `/reload-plugins` to pick it up.

### 2026-08-14

- **A Story can hold a PRD now.** `/afk-toolkit:to-ticket` PRD mode accepted only an
  Enhancement or a Bug as the parent, so publishing into a Story died on a type
  guard after the distill work was already done. Story now joins the accepted
  set, and the four places that restated the old pair were corrected with it.
  Nothing else changes: same managed block, same idempotent re-publish, same
  preservation of product-owner content outside the block.

- **One language across the chain, no setup required.** Simplified Technical
  English plus the glossaries' vocabulary is now plugin doctrine — `LANGUAGE.md`
  at the plugin root is its one home, binding on replies *and* every artifact,
  and every `SKILL.md` and agent file opens with a one-line pointer to it (new
  registry-gate check D refuses a file that lacks the pointer). This replaces
  the old opt-in that appended a block to `~/.claude/CLAUDE.md`: `/afk-toolkit:setup`
  no longer installs it and now **removes** the installed block (manifest H7,
  a one-shot migration). Keep the standard for non-AFK sessions by writing your
  own line in `~/.claude/CLAUDE.md`.

### 2026-08-12

- **Grill pages put the live question on top.** Session-default lavish
  surfaces (the grills' standing artifacts) now order by liveness — current
  round first, open items next, settled decisions at the bottom, newest
  settled first — so a long session never scrolls past decided history to
  reach the question (LAVISH.md "Live-on-top order").

- **Lavish tooltips cover the domain glossaries automatically.** The render
  hook now merges the target repo's committed glossaries (root + every
  `{service}/GLOSSARY.md`, the artifact's own service winning collisions) into
  the tooltip dictionary, finds the feature terms file by walking up from the
  artifact (no `afk-spec-dir` meta needed inside a spec folder), parses
  bulleted and annotated glossary entries, and matches plurals ("MRs") and
  hyphenated tails ("PRD-level") — no agent action required for any
  glossary-defined term.

- **Lavish pages name their browser tab.** Every rendered artifact now carries
  a `<title>` (`{page purpose} — {feature}`; LAVISH.md "Tab title"), and the
  render hook backfills untitled artifacts from filename + spec dir — so
  concurrent sessions' tabs are distinguishable. Mission Control tabs show the
  feature's plan title too.

### 2026-08-07

- **`/afk-toolkit:gc` no longer refuses every shipped feature.** Its guard script read
  the `Feature:` completion stamp with an anchored grep, but `PLAN.md` writes
  that header as a blockquote (`> Feature: …`) — so a genuinely shipped feature
  always came back `refused(not_shipped)`. The guard accepts both forms now, and
  the smoke test builds its fixtures in the blockquote form so the real-world
  shape is what gets exercised.

- **PAYU007 now checks caption *values*, not just key counts.** The i18n parity
  Stop gate used to pass any key that existed in every locale — so an English
  string pasted into a translation, an apostrophe that silently kills every later
  `{n}`, and mojibake all shipped green. It now blocks on all three (over the
  values a change adds or edits) and, repo-wide, on a backend `i18n/<locale>/`
  folder missing from that service's `languages.json` — a whole bundle that never
  loads. Per-check detail and the cognate allowlist:
  `harness/code-quality/RULES.md`.

- **Preflight merges the MR's target branch and resolves conflicts itself.**
  PF-1 now merges the MR's target branch (`origin/master` only as fallback)
  and resolves merge conflicts in place instead of parking — PF-2 validations
  and the PF-3 fresh review verify the resolution; only a conflict encoding
  contradictory design intent still parks. PF-3 passes the same base to
  `/afk-toolkit:review --feature`.

### 2026-08-05

- **Opt-in plain-language replies.** `/afk-toolkit:setup` now carries an elective
  (manifest H7, deselected by default, offered on every run): install a
  Simplified Technical English (ASD-STE100) reply standard into your
  user-global steering file (`~/.claude/CLAUDE.md`; also `~/.codex/AGENTS.md`
  on Codex machines) so every agent session — all projects — answers in short,
  plain, consistent English. Already set up? Re-run `/afk-toolkit:setup` to opt in;
  opt out by deleting the sentinel block. Standard text (one home):
  `skills/afk/setup/PLAIN-LANGUAGE.md`.

### 2026-08-07

- **Lavish artifacts keep their tooltips and dark mode after a rewrite.** The
  tooltip dictionary and the dark-mode override live inside the artifact HTML,
  so any Write/Edit that rewrote the file stripped both — silently, with no
  signal in the page or the transcript, leaving you looking at a white page
  with no hover text. `lavish-axi poll <file>` now re-injects exactly as a
  render does, so the runtime self-heals on the very next poll (and a rewrite
  is always followed by a poll). Nothing to change in how you work.

### 2026-08-05

- **Opt-in plain-language replies.** `/afk-toolkit:setup` now carries an elective
  (manifest H7, deselected by default, offered on every run): install a
  Simplified Technical English (ASD-STE100) reply standard into your
  user-global steering file (`~/.claude/CLAUDE.md`; also `~/.codex/AGENTS.md`
  on Codex machines) so every agent session — all projects — answers in short,
  plain, consistent English. Already set up? Re-run `/afk-toolkit:setup` to opt in;
  opt out by deleting the sentinel block. Standard text (one home):
  `skills/afk/setup/PLAIN-LANGUAGE.md`.

### 2026-08-03

- **Plugin files always run from the main checkout.** Every runtime skill/hook/script path across the plugin (autopilot spawn prompt, execute + cited-mode scripts, bug fixer prompt, lesson capture/digest, preflight ci-wait, smoke-gate template, mission-control, harvest) is now pinned to `<main-checkout>/tools/…` — an agent working in a worktree no longer executes the stale plugin copy frozen at the feature's branch point. Rule + term: `GLOSSARY.md` "Main checkout"; authoring convention in the plugin `CLAUDE.md`.
- **`create-worktree` no longer clones `.claude/TODO.md`.** The `/afk-toolkit:todo` list is per-worktree state, not shared config — a fresh worktree now starts with an empty todo list instead of a stale copy of the source checkout's.
- **Lavish UX round.** Pin bumped `lavish-axi` 0.1.18 → 0.1.36: annotation-mode keyboard toggle (`Ctrl/Cmd+I`), Enter-to-send, *Send & end*, and `--reopen` semantics for user-ended sessions. New doctrine: one response surface per artifact + a first-render briefing (where to respond; *End session* alone silently discards unsent feedback — finish with *Send & end*). Tooltips now source only from committed stores — the plugin's workflow `GLOSSARY.md` plus a per-feature `LAVISH-TIPS.md` terms file in the spec folder (declared via the artifact's `afk-spec-dir` meta tag; holds feature- and session-scoped terms and ids, not a glossary) — parsed at render time, so an edit reaches every future render and a session resumes on any machine; the per-machine `.claude/lavish-tips.json` overlay is retired (generic entries folded into the seed, domain entries re-home per feature via the rule-2 sweep). The injected page runtime also propagates each authored id-tooltip to every later bare occurrence of the same id (author once per page, every occurrence resolves), and grows a floating **btw** control: quick side-questions ride the queue as `[btw]` (answered in-session) or `[btw:subagent]` (fresh background agent), never treated as round feedback. Grill-verification's settled API rows now explicitly join the session's RP-3 matrix artifact. After pulling: run the pinned `stop` once with no session open so the background server restarts on the new version.
- **Lean slice reviews.** The per-subtask review gate now scales by a plan-level review policy: `lean` (the new default `/afk-toolkit:to-subtasks` stamps in PLAN.md) runs only the concerns that are much cheaper caught early — spec fidelity, scope, test veracity, plus compounding-risk escalators (refactored shared code, consumed contracts, entity shape, producer logic) — and defers smells / documented-rule nits / design-shape concerns to preflight's feature-level review, which widens its roster and sweeps the deferred findings; medium/low `smell`/`compliance`/`design` findings likewise settle at the feature gate instead of forcing slice rounds. Flip the header (or a contract's `## Review` section) to `full` for the old always-everything behaviour; `validate_plan.py` gains the (h) policy checks. Plan approval's lavish render (RP-2) now carries the policy decision surface — pick `lean`/`full` and per-subtask deviations in the UI, submitted in one send; the skill writes your choices back into the plan before it's declared emitted.
- **Audit follow-up: the low-severity residue is closed too.** The java-format gate now takes the maven lock around its `mvnw` runs (two agent commits in one checkout no longer race a validate against a reactor); rename/copy targets count as new files, so the wiring gate asks whether anything references the **new** name after a rename; the shared gate context is no longer exported (a huge change set could overflow the Windows environment block and fail every native child the gates spawn); the registry gate falls back to `python3` like the drift gate instead of silently fail-opening on python3-only machines; an allowlist line with leading whitespace registers instead of silently voiding itself; `/afk-toolkit:settle-mr` fixer subagents are pinned to the `afk-implementor` type like every other implementation-tier spawn.
- **The distribution law is written doctrine, and the audit enforces it.** `PROVIDERS.md` "Distribution law" (binding on every plugin change, linked from the plugin `CLAUDE.md` doctrine list): activation surfaces never ride git; committed prose is the one shared surface — inert, and neutral at repo root; Claude ↔ Codex parity on the committed/local/neutral split. `/afk-toolkit:setup audit` (check 5) now flags any tracked activation surface (`.agents/`, `.codex/`, `AGENTS.local.md`, `CLAUDE.local.md`) as drift.
- **Gate-suite audit hardening.** An adversarial audit of the gate refactor confirmed a set of correctness holes, all fixed. Commit path: the code gates now **refuse a commit whose staged copy of a gated file differs from its worktree copy** (they judge worktree bytes, so a broken staged blob could land behind a fixed worktree — re-stage and retry) and **skip merge commits entirely** (the staged set is the other side's whole delta, gated when it first landed); `/afk-toolkit:settle-mr` round commits carry the same explicit-long-timeout instruction as execute/bug. Stop path: a gate that **crashes no longer reads as a silent pass** — the turn isn't blocked, but no all-green stamp is recorded and the crash is named on stderr; the short-circuit digest now **sees the gitignored wiring IOU ledger** (deleting an IOU/waive line used to stay invisible until an unrelated edit); hand-edits to root `CLAUDE.md`/`AGENTS.local.md` now dispatch the codex-drift gate. Concurrency: cache/stamp writes are atomic and context scratch files per-process (two sessions in one checkout can no longer tear each other's state), and the maven lock steals stale locks atomically, records its owner, and releases when its process dies. Genericity scan regained exact word-boundary semantics: hyphen-prefixed ticket IDs, ID ranges, and package-qualified file references are caught again; longer extensions no longer truncate into false product-file hits; content after a literal tab is scanned; a path with a blank no longer un-scans its whole file; the allowlist keeps an unterminated final line. The git-hook installer now says so when a pre-existing non-AFK hook blocks installation instead of silently leaving the machine ungated.
- **Codex now has the same opt-in boundary and root-file layout as Claude.** Root `.agents/`, `.codex/`, and `AGENTS.local.md` are gitignored — per-machine activation surfaces, provisioned by `codex-sync/generate.py` (or `/afk-toolkit:setup`) at opt-in, so hooks fire and skills/agents surface **only** for devs who opted in; everyone else sees inert committed markdown under `tools/payable/ai-agents/`. The committed layer mirrors Claude's exactly: a **neutral root `AGENTS.md`** now rides git (Codex analog of root `CLAUDE.md` — routes any agent to `CLAUDE.md`, plus a read-if-present pointer to `AGENTS.local.md`, the Codex analog of `CLAUDE.local.md` and the new home of the generated afk block). `CLAUDE.local.md`, accidentally tracked since July, went back to per-machine — expect git to remove your local copy on pull if it was clean; restore it from your own machine's notes, not the repo. Two generated outputs still ride git because they're tooling, not activation: `codex-sync/config-fragment.toml` + the harness `hooks/lib/provider.sh` byte-copy. Codex devs: delete any stale local `AGENTS.md` (git will refuse the pull otherwise), pull, rerun the generator once per worktree — the drift gate reminds you; regenerate-and-commit churn on skill edits is gone.

### 2026-07-31

- **Gates no longer tax interactive work.** A turn that only talked now costs one short-circuit check instead of the whole suite, and the three expensive code gates (`maven-compile`, `java-format`, `ui-lint`) moved off Stop onto a **`pre-commit`** git hook — same enforcement, paid once per commit instead of once per question. What made this necessary: gate latency on Windows/git-bash is **subprocess count**, not algorithm (MSYS fork emulation runs ~0.5–2s per spawn against ~20–40ms native, and degrades under load), and the suite was spawning hundreds — a cache key that re-hashed the tree with two forks per changed file, recomputed independently by all seven gates; a registry gate re-grepping the same files once per skill and once per env var; a wiring gate running a full-monorepo scan **per new file**. Now: one Stop hook (`stop-gates.sh`) deriving the change set once (`gate-context.sh`) and entering a gate only when the change set holds a path it could possibly gate; per-gate pass caches keyed on **that gate's own inputs**, so editing a spec file no longer re-runs the plugin-registry gates; one batched repo scan for every wiring candidate; one `awk` pass for genericity whatever the diff's size. Measured on the same tree: full cold Stop 56–95s (was over 2min, with the genericity gate alone recorded at 12min), unchanged tree 7.5–12.5s, and design-chain artifacts (PRD/SDD/plan/ADR/journal files) no longer report as wiring orphans — they have no textual referrer by construction. Also fixed: two registry-gate false blocks (Windows Python's CRLF broke every `plugin.json` membership match; the gate flagged a variable named inside its own trailing comment). New env toggles `AFK_GATE_CTX_DISABLE`, `AFK_SKIP_PRECOMMIT_GATES`, `AFK_MAVEN_LOCK_WAIT`. **Restart the session** (hooks.json changed), and run a session in each existing checkout so `install-git-hooks.sh` adds the `pre-commit` hook. Cost model + the rules a new gate must follow: `hooks/README.md`.
- **The wiring gate finishes on a long-lived branch.** It never did before: its candidate set is every file the branch *added*, committed ones included, and it ran a full-monorepo scan per candidate — on a design branch carrying 153 added files that is 133 scans at ~6.3s each, so it hit the 60s hook timeout, got killed, stored nothing, and started over on the very next turn, forever. That is why a long grilling session saw "wiring gate" burning for hours and no gate ever recorded a pass. One batched scan covers all 133 tokens in **9s**; whole gate **23s cold**, then cached. Two more per-candidate costs went with it: the framework-annotation probe now runs only on the handful the scan could not clear, and the IOU ledger is read once instead of grepped per candidate. The gate also stopped being scope-gated on worktree-new files — a branch whose new files are all *committed* was skipping it entirely. First completed run on that branch surfaced a genuine orphan the timeout had been hiding since 22 July.
- **Committing no longer switches three gates off.** Scope-driven dispatch read the *working tree* only, but the registry, codex-drift and genericity gates each judge the whole branch — so the moment work was committed and the tree went clean, none of them ran again, and the Stop still recorded a pass. On this very branch that was 11 plugin `.md` files in the genericity gate's scope against 3 the dispatcher could see. Dispatch now spans the working tree plus the branch's commits (`gate_ctx_branch`, one memoized diff, only on a turn that already did real work). A prose violation that exists solely in a commit is caught again.
- **The maven lock is released once, not twice.** Gates share one process now, and `trap release_maven_lock RETURN` fires again as the enclosing dispatcher returns — the second `rmdir` dropped a lock another worktree's build had just acquired, re-opening the concurrent-reactor race ("cannot find symbol" from a half-written dependency) the lock exists to prevent. Replaced with one explicit release the moment the reactor finishes, so the lock is also held for a shorter window.
- **The new `pre-commit` hook never gates *your* commits.** It installs into the shared hooks dir, so it is present in every worktree and in the main checkout — but it returns immediately unless an agent runtime marks the environment, exactly like the branch-name gate. Committing from your terminal or IDE costs nothing; only an unattended agent pays the reactor build. Two wall-clock bounds come with it, because an agent commits through a tool call that can time out under the hook: the maven-lock wait drops to 240s on the commit path (`AFK_MAVEN_LOCK_WAIT`) instead of parking a commit for 15 minutes behind a sibling worktree's build, and the skills that commit code invoke `git commit` with an explicit long tool timeout. The Stop hook's own budget went 120s → 300s to match the measured cold run — a killed Stop hook silently skips every gate.
- **Implementation-tier spawns are now pinned to Opus 4.8** via a new **`afk-implementor`** agent type (`agents/afk-implementor.md`, `model: claude-opus-4-8`) — `/afk-toolkit:autopilot` routes `standard`/`complex` subtasks to it and `/afk-toolkit:bug` spawns its fixer as it, so code-writing children stop drifting onto whatever the session model happens to be, while Opus-level *judgment* spawns (frontier tier: grills, planning/slicing, review, adversary, plugin/harness edits) keep the floating `opus` alias and follow the latest Opus. Requires a **session restart**, not `/reload-plugins`: agent definitions are scanned at session start. The mechanism matters — a pinned model reaches a child **only** through an agent definition's frontmatter; the Agent/Task tool's `model` argument is an enum (`sonnet|opus|haiku|fable`) that rejects pinned ids outright. Tier names + the verified pin-delivery rules: `PROVIDERS.md`; tier roles unchanged in `DELEGATION.md`.
- **`/afk-toolkit:setup` now installs `openpyxl`.** `/afk-toolkit:review-qa-tests` imports it to annotate QA's `.xlsx` sheet, but it was registered nowhere — so a fresh machine could pass the doctor green and still die at first use (`MANIFEST.md` P4). The same audit sweep registered two env toggles that were live but undocumented: `AFK_DRIVEN` (the hands-off marker `/afk-toolkit:gc` refuses on) and `CLAUDE_PROJECT_DIR` (harness-set, locates the adopted harness gates). Re-run `/afk-toolkit:setup`.
- Wiring gate no longer flags **JS/TS test files** (`*.test.{js,mjs,ts,tsx}`, `*.spec.*`) as orphans — every JS runner discovers them by glob, so they have zero textual referrers by construction, exactly like the already-exempt `*.feature` and `*Test.java`. Writing a new api-verification or unit test stops blocking the turn, and the IOUs previously needed to paper over it (which could never auto-close, so they blocked `WIRING_FINAL=1` forever) can be deleted from `.claude/wiring-ious.md`.

### 2026-07-28

- Lavish is now the **default surface for the grill skills** (`grill-requirements`, `grill-solution`, `grill-verification` + the confirm-batch round): every question/round renders into the session's page, from the first question — the only ways out are driven mode, a render failure, or **telling the agent to stop** (new session-scoped user opt-out in `LAVISH.md`). The on-page **legend is retired** in favor of an exhaustive **tooltip layer**: a persistent term → explanation dictionary (plugin seed `hooks/lavish-tips.json` — acronyms, L1–L9, HL-1..6, RP ids, workflow + architecture vocabulary — plus a growing per-repo overlay `.claude/lavish-tips.json` for domain terms) is injected **deterministically** into every artifact at render time by the new `lavish-tips.sh` hook, so hover explanations cost the LLM one definition ever, then ride every future page free; per-artifact item ids stay authored inline (`data-tip`) and share the same hover UI. `LAVISH.md` also gains a **visualization doctrine** — content-type → proven form (C4-altitude zoom for architecture, sequence/state diagrams, option cards, before/after pairs) with fixed color semantics. `/reload-plugins` to pick it up.
- Review checklists sharpened from a 365-day mine of two senior reviewers' MR comments (756 comments → 55 verified themes): `logic-correctness` gains a lifecycle & persistence block (state-constrained queries on revisioned entities, orphaned link rows, string-assembled SQL, persisted-identifier renames without migration); `code-quality` gains **magic value without provenance**. The bulk of the mine (~40 write-time standards: nullability, naming, validation placement, exceptions, REST/DTO conventions, DB-side work, entity columns, Vue idioms, background-job security) landed in the team harness shared docs + service rules, not the plugin.
- Artifacts the chain writes are now **compact by default**: new plugin-root doctrine `CONCISION.md` (one home — fact-dense prose, cut words never facts, one-fact-one-home, tables for parallel structure, formats stay contracts) read-before-writing by every markdown-writing skill/template (PRD/SDD templates, plan slicer, review + adversary reports, retro, verification plan, design brief, handoff, `/afk-toolkit:claude-md`); the former `claude-md/STYLE.md` is merged in as its steering-notes section — one home. Same criteria applied retroactively to the team harness: `tools/payable/ai-agents/harness/*` trimmed ~23% with stale claims fixed (jira MCP tools wrap plain text into ADF — the "wiki markup" claim was wrong; crowdstrike-guard log location; dead `lean-ctx` recommendations and the orphan `shared/coding-standards.md` tombstone removed), and the 11xxx CLAUDE.md/IMPL/TESTING/GLOSSARY steering tree swept with verification. New `tools/payable/ai-agents/CLAUDE.md` auto-loads the authoring doctrine (DRY one-fact-one-home et al. + the CONCISION bar) for any agent editing the plugin/harness tree — previously nothing loaded outside `plugins/workflow/`.
- Always-loaded context slimmed further (~2.5k tokens per session, every teammate): the 28 `afk` chain-skill descriptions cut to ~170 chars average — triggers kept, detail lives in each `SKILL.md` body — and the monorepo root `CLAUDE.md` drops the dead GitNexus block (revivable from git history) and moves the new-UI-project checklist to `docs/new-ui-project.md`. `/reload-plugins` to pick up.
- Four mechanical prose-walks are now **scripts** (deterministic, smoke-tested): `/afk-toolkit:to-subtasks` validation checks (a)/(b)/(e)/(g) → `scripts/validate_plan.py` (owns the forbidden-anchor-token list + glob→tier table); `/afk-toolkit:execute` cited-mode consumer/producer preflights → `scripts/verify-contract.sh`; its tracker-cell flips → `scripts/plan-status.sh`; `/afk-toolkit:gc`'s refusal guards + worktree verify-safe checks → `scripts/gc-check.sh` (hands-off invokers export `AFK_DRIVEN=1`). Prose in those skills now just invokes them.
- Correctness fixes: `/afk-toolkit:bug`'s fixer no longer flips the MR Ready when no reviewer is configured (K2 absent → stays Draft, fail-closed); `PLAN-TEMPLATE.md`'s smoke-gate table regained the `Requires target` column `/afk-toolkit:smoke-test` reads; `/afk-toolkit:review` reviewer prompts no longer carry checklist `## Guardrails` blocks they must ignore; spinoff rows in `GRILL-LOG.md` now carry `pain`/`why-out` (what the mint actually reads); stale claims that the SDD publishes to the ticket removed everywhere.
- Plugin-wide token slim-down (~10k words): root `CLAUDE.md`/`README.md` per-skill catalogs collapsed to pointer tables (each skill's `SKILL.md` is the one home), `hooks/README.md` defers to script headers, frontmatter descriptions tightened. New doctrine in `CLAUDE.md` "How to write these skill files": **Minimal-first** (least instruction that works; add only on observed failure) and **Deterministic-first** (mechanical work goes in scripts, not prose). `/reload-plugins` to pick everything up.

- Eight ledger lessons applied as durable edits (`/afk-toolkit:lessons apply`): `/afk-toolkit:grill-verification` gains an **External-state gate recheck (TOCTOU)** aspect row + a time-of-check/time-of-use walk (for every gate resting on another system's state: where is it re-checked, what if the state flips before the irreversible action, which scenario covers the window), an **Accepted staples** aspect row (every staple the PRD accepted needs a proving scenario or recorded N/A), a widened **Data-scoped access** trigger + enumeration rule covering every dropdown/lookup/reference-data endpoint the UI consumes — including shared ones inherited from other surfaces — and a **new-transaction-boundary** rule in its API-scenario walk (an endpoint wrapping an existing pipeline in its own `@Transactional` re-proves the wrapped validation failures at the new surface, where a 400 can silently become a 500). `/afk-toolkit:grill-solution` L5 now pins **lifecycle-stage binding** of validation rules (check the state machine before adding a rule to a create/update path — progressive completion), and its external-seam rule requires pinning the **exact trigger** (exception vs null-return, and a caller role that can actually reach it) for any status migration at a resolution seam. `/afk-toolkit:settle-mr` fixers that touch tests self-apply the `test-veracity` checklist + nearest `TESTING.md` before returning. `LAVISH.md` gains **Queue discipline** — one review = one queued prompt; controls mark locally (localStorage), one send control composes a single summary. `/reload-plugins` to pick these up.
- The afk plugin now carries the **whole gate suite** — the four gates that previously required the separate, rarely-installed `payable-harness` plugin (`java-rules-gate` CSJ code standards, `i18n-parity-gate` locale parity, `crowdstrike-guard`, `explore-counter`) are registered in this plugin's `hooks.json`, invoked in place from `tools/payable/ai-agents/harness/hooks/` so they track the checkout, not the plugin snapshot. The `payable-harness` plugin is **retired** (manifests + its `hooks.json` deleted; uninstall any old copy) — enabling `afk-toolkit@afk-toolkit` is the single opt-in. Notably this closes the gap where CSJ001 (no inline FQNs in Java) was documented and machine-checked but silently unenforced. `/reload-plugins` to pick it up.

### 2026-07-24

- New **`/afk-toolkit:harvest`** — harvest the lessons a session taught you and apply them on the spot, without waiting for the autonomous workflow. Until now the lesson loop only fired from inside the chain (execute's gates, `/afk-toolkit:fix`, `/afk-toolkit:claude-md`, `/afk-toolkit:glossary`), and anything targeting a **plugin file** was deliberately parked for a separate `/afk-toolkit:lessons apply` session. `/afk-toolkit:harvest` is the manual sweep: it walks the whole session, qualifies each correction/gotcha/established pattern against the same capture bar, drops what a detection point already applied this run, proposes one grouped round, and on your approval routes each edit through its owning steward — then tells you what to reload so the edit is actually in force (`/reload-plugins` for a plugin file; project memory is already live). You invoke it by name — it never fires on its own, so it can't compete with `/afk-toolkit:claude-md`'s auto-harvest over the same signal. Paired change in `skills/afk/lessons/CAPTURE.md`: a **self-contained** plugin edit — one file, no lockstep partner, no freshness registry row — may now be applied mid-task via a delegated writer instead of being parked; anything touching a lockstep set still waits, so a half-written contract can't ship. `/afk-toolkit:lessons` gains the matching **Bind** rule it was missing: after any applied edit — from `apply` or from a detection point — it now names what the edit needs to actually take effect, instead of leaving a freshly-written skill inert until you happen to reload.
- `/afk-toolkit:gc` now cleans up the **worktree** too, not just the spec folder. After a merge it offers a second, independently-approved item: remove the feature's dev worktree (reclaiming its private Maven repo — the freed size is reported) and delete the local feature branch. It only does so once that checkout is proven to hold nothing you'd lose — no uncommitted or untracked work, no commits missing from `origin/master` — and never forces it (`worktree remove` without `--force`, `branch -d` never `-D`); any doubt skips with its reason and the spec compaction proceeds regardless. Remote branches are never deleted, and the bug pipeline's fixer worktrees stay `/afk-toolkit:bug purge`'s. New guard: running `/afk-toolkit:gc` from inside the worktree it would remove is refused (`inside_target_worktree`) — run it from the main checkout.
- `/afk-toolkit:grill-solution` now treats six design aspects as **human-locked** — yours to decide, never the agent's and never the executor's: **entity design** (HL-1: every field, type, nullability, unit, key, relation with cardinality/owning side/delete behaviour, index, Envers verdict, retention, and the migration + backfill of existing rows), the **API surface** (HL-2: per endpoint — method + path, roles, request fields with validation, success and every error envelope, paging, idempotency, and the compatible-or-breaking verdict for an endpoint that already exists), **authz + data scoping** (HL-3), **lifecycle states, transitions and invariants** (HL-4), **irreversible or outward side effects** (HL-5), and **changes to existing behaviour** at the L9 seams (HL-6). Each live aspect is grilled to a stated **contract grade**, presented as its own review packet (the tables verbatim, alternatives, blast radius, risks — rendered via new **RP-9**), and signed off **by you, by id, in your own words**, recorded as `signoff` rows in `GRILL-LOG.md`; an aspect whose design later moves is void and re-signed. Unsigned = the design isn't exhausted. `/afk-toolkit:to-sdd` carries the register into **SDD §0** and gains a refuse-to-publish gate (Step 7b) for unsigned aspects; §3 and §4 now demand endpoint-level and field-level detail so what you signed is what an executor builds. Set + protocol: new `skills/afk/grill-solution/HUMAN-SIGNOFF.md`.
- Grills can now **spin off deferred work** into its own Jira ticket without leaving the interview. When a walk surfaces work that's real but out of the current ticket's scope — a dependency to defer, an adjacent pain this feature won't fix — the grill records it as a **spinoff candidate** row in `GRILL-LOG.md`, and (human-present, on your say-so) mints it as a stub Enhancement under the parent epic via a new **`/afk-toolkit:to-ticket` spinoff mode**. Links the Jira API can't set (`blocked-by`/`relates`) are tracked as **link-debt** on the candidate row and surfaced for you to set by hand; resume-safe dedup never files the same spinoff twice. New plugin-root doctrine file `SPINOFF-TICKET.md` owns the protocol (woven into all three grills; `/afk-toolkit:grill-verification` records candidates only, its no-tracker rule intact). The "exactly two Jira writers" boundary holds — `/afk-toolkit:to-ticket` gains a mode, not a new writer.

### 2026-07-23

- New skill `/afk-toolkit:to-demo-plan`: turns a delivered feature into `DEMO-PLAN.md`, the script for the hour you spend showing it to **product owners and QA**. It reuses what the chain already settled — the PRD's pain + user stories, the verification plan's walked click-paths, the ADRs, the delivered diff — and lays them out as **beats** (what to *say*, the exact steps to *do*, the line to land, its minutes), each classed **show** (performed live) or **tell** (one sentence, so obvious behaviour never eats the clock). Ordered why → concepts → happy path → touch points → edges, with a **touch-point map** of everything the feature adds to / changes in / interacts with existing behaviour (every `changes` row must be shown — that's QA's regression scope), ≤3 decisions explained in consequence language, questions **pre-empted at the beat that raises them**, an explicit out-of-scope table, and a setup section so no beat depends on state nobody created. Budget: ≤60 min with ≥10 protected for questions. The plan demos *value*, not correctness — the gates already settled correctness. Repo-only; adds a `Demo plan` row to the ticket `INDEX.md`.

### 2026-07-22

- `/afk-toolkit:grill-verification` now **resumes from `GRILL-LOG.md`** like the other two grills: its opening digest reads any existing checkpoint section, so the documented post-SDD re-run (design the deferred API scenarios) picks up the already-settled UI journeys and per-aspect verdicts from disk instead of re-walking them. It already wrote the section — only the read side was missing.

### 2026-07-21

- Ticket spec folders moved out of the packaged-resources tree: the convention is now `{service}/specs/{year}r{release}/{TICKET-ID}/` (was `{service}/src/main/resources/specs/...`). Payable's specs migrated to `11700-payable/specs/`; every path-carrying skill (`/afk-toolkit:to-prd`, `/afk-toolkit:fix`, `/afk-toolkit:retro`) and doc updated. Specs no longer risk shipping in a service jar, so payable's pom stops overriding Maven `<resources>` (which had silently dropped `descriptor.yaml` and application-property filtering).
- `/afk-toolkit:prototype` now renders through **lavish** (new RP-8): the mockup serves in the Lavish Editor, where the annotation toggle lets you drive the simulation as before *and* pin feedback to specific elements, select text, or hit embedded feedback controls — notes land back in the session via poll instead of being described in chat. Mockups stay fully portable (live controls marked `data-lavish-action`, `window.lavish` calls guarded — rules generalized into `LAVISH.md`'s new **Drivable artifacts** section, alongside the `poll --agent-reply` shape); plain-browser `file://` refresh remains the fallback.
- `/afk-toolkit:to-ticket` re-publishes now leave a paper trail: when the ticket already carries a published description and the PRD changed (requirement gaps closed, scope added/cut), the skill distills the delta into `TICKET-CHANGES.md` and the engine posts it as an **issue comment** right after the description update (`--changes`; one confirmation gates both writes) — the description keeps showing current truth, comments record how the requirements moved. The dry-run summary gained an `action` line (`first publish` / `re-publish`), and a first publish skips the comment with a warning.
- `/afk-toolkit:prototype` mockups now render **in situ**: every new screen sits inside a replica of the real app shell (nav, header, breadcrumbs, active item), and the feature's **neighbor pages** — where each story enters from and where it navigates to — appear as shallow drivable stubs, so you reach the new UI by clicking from where you'd really start. The capability walk drives each story from its entry-point stub, and the fidelity pass diffs shell + nav chrome too — familiarity is the instrument for spotting gaps.

### 2026-07-20

- `/afk-toolkit:grill-requirements` "Challenge the want" gains a third standing obligation: every validity change (new gate, admin mode/toggle, curation, removal) is walked over still-editable records created before the change or under the other setting — every record the change makes rejectable needs a named, role-reachable repair affordance, and "no silent migration" decisions must name that affordance in the same requirement. New exit-gate bullet enforces it.
- `/afk-toolkit:understand` is now the one-stop shop for **learning any piece of code** — it takes a shipped feature (`{plan-dir}`), a **GitLab MR URL**, or a **code area** (`path:`/`symbol:`) and produces the same self-contained interactive HTML learning artifact for each (`/afk-toolkit:to-code-walkthrough` is retired; its MR fetcher, spec discovery, and size gates moved into understand). The artifact also became a much better teacher: learning objectives + key concepts & constraints up front, a one-sentence mental model re-invoked through walkthrough and recap, the walkthrough split into **one tour step per seam/flow group** (stated ordering rationale, plain-language overview before code), evidence-grounded "where you'd naturally go wrong" callouts, optional one-question checks per group, and a recap section — all enforced by five new skeptic criteria (jargon-before-use, ordering rationale, objectives/recap integrity, representation match, grounded misconceptions). Shell chrome gained resume-where-you-left-off, per-step reading-time hints, and an **ask-the-teacher** button that assembles a context-rich clipboard prompt for a live Claude Code session (page stays fully offline). The interactive-walkthrough widget catalog grew two teaching widgets: a **before/after comparator** and a **predict-then-reveal** pause.
- New skill `/afk-toolkit:gc`: post-merge spec compaction. After a feature's MR merges, it proposes — and on your approval deletes — the ticket folder's run artifacts (whole `plan/`, `GRILL-LOG.md`, publish intermediates), keeping the evergreen docs (PRD/SDD/ADRs/VERIFICATION-PLAN/PROTOTYPE/INDEX/understanding) and recording the git archive ref in `INDEX.md`. Stops stale subtask contracts and settled review findings from surfacing in future sessions' greps as current truth. `plan/`'s lifespan (slicing → merge) is now declared in `/afk-toolkit:to-subtasks`, and `/afk-toolkit:preflight`'s success report points at the post-merge step.

### 2026-07-19

- `/afk-toolkit:setup base` now checks the IntelliJ IDE max heap (W7): every installed `IntelliJIdea*` config dir must set `-Xmx` ≥ 16384 MB (default target; pick your own at the election) — the stock 2 GB heap thrashes on a monorepo reimport. Fix upserts the `-Xmx` line in `idea64.exe.vmoptions`, leaving other options untouched.
- `/afk-toolkit:prototype` now settles a **drivable** mockup, not a picture: every PRD User Story / Acceptance Criterion must be clickable in the HTML (simulated client-side against fixtures) or logged as a gap — enforced by a pre-settle **capability walk** — and a **fidelity pass** diffs the mockup side-by-side against the live app (or the `/afk-toolkit:design-system` catalog), with the fidelity basis (`live-verified`/`catalog`/`source-only`) recorded in `PROTOTYPE.md`. Anchoring is layered: catalog first, live-DOM lifts second, source digest as fallback.
- Grill sessions got faster, same rigor — agent work now overlaps your think-time instead of alternating with it: delegation doctrine adds a think-time overlap rule (background digests spawned before the turn yields — `DELEGATION.md`); confirm-batch evidence pre-fills as items accumulate instead of at the batch boundary (`TRIAGE.md`); the L9 seam walk fans out parallel draft seam rows and interviews only the mismatches, with compatibility auditors launching as each area locks; `/afk-toolkit:grill-requirements` and `/afk-toolkit:grill-solution` open with a parallel pre-brief digest (glossary, staples, ADRs, prior grill log) instead of mid-session reads; the devil's-advocate pass runs alongside the final confirm batch; lavish renders warm up at phase start and live artifacts re-render at question boundaries (`LAVISH.md`).
- `/afk-toolkit:to-ticket` no longer publishes the raw PRD: it first distills a requirements-level `TICKET.md` (User Stories + Acceptance Criteria mandatory; no technical depth, no repo-artifact references) and publishes that — Product Owner/QA-readable ticket descriptions.

### 2026-07-17

- `/afk-toolkit:setup base` is now elective per item: the pre-fix report doubles as a pick list of every base-tier item needing action (toolchain pins + all workstation apps/OS config, including anything added to the register later), so you install only what you'll use — deselected items report `skipped (user choice)` instead of `needs-human`. The skill-load-bearing default surface stays mandatory.
- New utility `/afk-toolkit:review-qa-tests`: review a QA team's **manual** test cases (typically a spreadsheet) against the feature's requirements and annotate their sheet in place — missing scenarios as new rows (only the human columns filled, scoring left to QA), fixes to existing cases as threaded comments. Writes strictly at requirements/behaviour level: the QA reader is treated as **black-box** (nothing about code, bugs, or dev process reaches a comment), and a **manual reach** filter recommends dropping cases only automation can exercise (injected faults, multi-instance, true races). Ambiguities settle with you before anything is written. Ships an `EXCEL.md` recipe + a reusable `annotate_sheet.py` that writes real threaded comments (not legacy notes) and dodges the two orphan-relationship faults that make Excel prompt to repair.

### 2026-07-16

- `APP_START_SKIP_UI=false` now actually serves a frontend. It was a silent no-op: the default Maven profile leaves `*-ui` out of the reactor, so the UI never built, the app's `public/` stayed empty, and the instance booted serving nothing — a browser tier would pass against a page that wasn't there. `app-start-gate.sh` now runs the service's own `build_ui.sh` before packaging the leaf, refuses to boot (exit 2) if the build leaves no `public/index.html`, and clears the SPA target before each build so a reprovision serves the fresh UI rather than a stale copy nested one level deep (`cp -R` nests into `public/spa/` when `public/` already exists). Reaching for Maven's `-DskipUi=false -DpipelineBuild=true` instead would force every in-house UI lib to rebuild (`skipUi` is global) — needing a vite/rollup native binary that isn't pinned on all dev platforms, to remake a `dist/` that already exists. New env var: `CI_PROJECT_DIR` (optional, defaults to the repo root).
- Lesson ledger made trustworthy on Windows: `lesson-digest.sh` no longer reports a parse-failed ledger as "no lessons recorded" (it now says `ledger unreadable` and tolerates stray non-UTF-8 bytes per line), and `lesson-append.sh` emits ASCII-safe JSON so console-codepage output can't corrupt the ledger again.
- Settle loop (`skills/afk/review/SETTLEMENT.md`): a fix that introduces new behaviour is now a design change, not a patch — the implementor must enumerate its failure modes and pin each with a test in the same fix commit, instead of letting successive review rounds design the feature one finding at a time.
- Mission control rebuilt as a two-layer interactive dashboard (spec design ADR-0008). The page is now a navigable app (sidebar sections, keyboard nav, page-wide legend tooltips, freshness dots) instead of one scroll of raw tables. **Live** sections stay deterministically derived and gained real synthesis: an Overview hero (phase ribbon, status bar, gate chips, artifact inventory), Progress with per-subtask sub-phase detail (settle round, review verdict, per-subtask commits mined from subject tags + journal-recorded hashes), a filterable Timeline, Gates (smoke + preflight + rollup + adversary), auto-mined Insights (open parks/blockings/advisories with superseded items dropped), and feature-scoped Diffs. **Digest** sections (architecture module DAG, steppable flow simulations, entities, ADR decision cards, critical-logic shortlist, legend) render committed hash-stamped `plan/digests/*.json` authored by the new `/afk-toolkit:mission-control build` mode — schemas + digestibility rules in the skill's `DIGEST-FORMAT.md`; stale/unbuilt digests render an amber hint and launching never spends tokens. Renderer CLI grew `--check-digests`; panel parsers moved `scripts/mc/panels/` → `scripts/mc/sections/`.
- Model selection goes role-based and provider-named: `DELEGATION.md` now defines three tiers — **frontier** (grills, planning/slicing, review + adjudication, gating verdicts: Fable, or Opus if unavailable), **implementation** (product code from a frontier-authored plan: Opus, never Fable; Sonnet for simpler slices), **digest** (Sonnet; mechanical chores at low effort) — with Codex CLI equivalents (`gpt-5.6-sol`/`-terra`) named in `PROVIDERS.md`. "Inherit the session model" is gone; autopilot's `## Complexity` routing follows the tiers; and any work on the plugin/harness itself always runs frontier.
- New utility `/afk-toolkit:settle-mr`: review any GitLab MR (URL or IID — bug fixes and small work outside the AFK chain) against a real MR-head worktree checkout, using the same review machinery and settle loop as the AFK gates, with the MR itself as the ledger — every finding is an inline MR discussion, fixes/disputes/adjudication verdicts reply on the threads, and a managed summary comment keeps the round accounting, so sessions and devs can hand the MR off mid-loop. Your own MR defaults to the auto-fix loop (fixer subagents read findings from the MR threads, fix-or-dispute on merit, commit+push per round until nothing actionable remains); someone else's MR defaults to review-only, each re-invocation a follow-up round over new commits + author replies. Never merges. Replaces the personal `gitlab-mr-review` skill.
- Skill authoring is now doctrine-at-write-time: plugin `CLAUDE.md` requires loading `writing-great-skills` before creating or editing any skill file, replacing after-the-fact audits.
- Worktrees stop competing over `~/.m2`: `create-worktree` now provisions a private per-worktree Maven repo — it writes `.mvn/maven.config` (`-Dmaven.repo.local=<worktree>/.m2/repository`, picked up automatically by every `./mvnw` run, the maven-invoking hooks, and IntelliJ) and seeds it from your local repo minus `*-SNAPSHOT` dirs (robocopy, `cp -a` fallback; dependency set changed — C8). Opt out with `--no-m2`; `--m2-seed <path|none>` overrides the seed source. Retrofit an existing worktree by writing the same one-line `.mvn/maven.config` in it.
- Review gate goes multi-round: execute Step 10 and preflight PF-3 now settle the independent review through a fix-or-dispute settle loop (`skills/afk/review/SETTLEMENT.md`) — fresh re-review after every remediation, every finding (nits included) fixed or disputed, disputes adjudicated by fresh skeptics, and termination accounting (hard 10-round stalemate cap → flagged for a human) kept by the referee, never leaked into reviewer/adjudicator prompts. Rounds after the first review only the remediation delta (`--base` last-reviewed tip, full diff handed to reviewers as context) and stay cheap by construction: the reviewer fan-out consolidates to one `delta-sweep` reviewer plus signal-activated specialists (fix-owner concerns, delta triggers, or an oversized delta), and per-round re-verification is compile + local tests only — live tiers, mutation probe, and other expensive surfaces run once outside the loop. `/afk-toolkit:review` grew `--tag` for per-round artifact naming; the adversary gate now carries its own 2-cycle cap.
- Token-lean runs, same gates: subtask contracts now carry `## Context excerpts` (slicing-time verbatim PRD/SDD/ADR quotes) so each executor works from its contract instead of re-reading the parent docs; execute's design-bar checklist reads and review's `refactor-safety` concern are trigger-gated by diff/slice shape; review materializes the diff once to a scratch file for all reviewers; `/afk-toolkit:grill-verification` ingests sources via an `afk-reader` digest; maven-compile/ui-lint gates report triaged failure digests (full log to a file) instead of unbounded dumps.

### 2026-07-15

- Pass cache extended to all Stop gates: wiring, skill-registry, codex-drift, and genericity now skip their scans when the tree is unchanged since their last pass (`gate-cache.sh`, previously compile/lint/format only); wiring bypasses the cache in final mode.
- Glossary-first grilling: `/afk-toolkit:grill-requirements` now actively hunts candidate terms from the first exchange (draft-then-verify questions, asked as soon as a term surfaces), gates exit on a user-verified entry per term, and commits the glossary before `/afk-toolkit:to-prd`; `/afk-toolkit:execute` reconciles `GLOSSARY.md` post-subtask when implementation semantics diverge from the grill-time definition.
- Conclude-at-detection self-improvement loop: new `/afk-toolkit:lessons` steward + a main-checkout workflow lesson ledger (`.claude/lessons/LEDGER.jsonl`). Detection points capture classified lessons with drafted edits the moment they conclude (execute's review/adversary outcomes, `/afk-toolkit:fix` Phase 3.5 — now records to the ledger instead of a handoff doc, `/afk-toolkit:claude-md` HARVEST, `/afk-toolkit:glossary` GRILL); `/afk-toolkit:execute` reads open lessons before designing; preflight surfaces open drafts (new advisory row PF-4c); `/afk-toolkit:retro` grades lesson closure and escalates recurrences (reword → relocate → checklist → gate).
- `/afk-toolkit:setup base` now provisions the WSL2 runtime Docker Desktop requires (C7 — absent WSL surfaces as Docker's misleading "virtualization support not detected" error even with firmware virtualization on); also fixed two Windows probe false-negatives: H6 no longer trips on the `python3` Store stub, W5's `reg query` gets the `MSYS_NO_PATHCONV=1` prefix Git Bash needs.
- Faithful-input doctrine: api/e2e verification must drive the real client's interaction shape — never reshape an input to dodge an unexpected failure (that failure is a candidate defect). Rule added to the subtask contract's Verification template, both verification AUTHORING guides, payable's TESTING.md antipattern list, and `/afk-toolkit:fix`'s escape analysis (new miss class `dodged-failure`).
- `/afk-toolkit:setup base` grew a hosts-file check (W6): `127.0.0.1 proxy` must be in `C:\Windows\System32\drivers\etc\hosts` so `proxy`-hostname URLs resolve for local builds.
- Dual-provider support: the workflow now also runs under the OpenAI Codex CLI — a generated mirror (`.agents/skills/`, `.codex/`, AGENTS.md block) produced by `tools/payable/ai-agents/codex-sync/generate.py`, a `PROVIDERS.md` provider mapping, a provider shim for hooks (`hooks/lib/provider.sh`), Jira creds fallback to `~/.codex/config.toml`, `/afk-toolkit:setup` section O for Codex provisioning, and a `codex-drift-gate.sh` Stop gate that keeps the mirror regenerated in the same commit.
- `/afk-toolkit:setup`'s human-gated fixes are now one script: run `skills/afk/setup/scripts/setup_secrets.py` from your own terminal — prompts for tracker + SCM credentials, validates before writing, never echoes a secret, idempotent.
- The Jira MCP server now ships in-plugin (`mcp-servers/jira/server.py`) — no separate checkout; registered user-scoped under key `jira` (the setup script places it).
- Wiring gate diffs new files against `origin/master` instead of your branch's upstream — other teams' merged files can no longer false-block your turn.
- `/afk-toolkit:setup base` grew two checks: JDK distribution pinned to Amazon Corretto, and Windows long paths (OS registry flag + `git core.longpaths`).
- Registry gate now also blocks uncatalogued skills (no `CLAUDE.md`/`README.md` mention) and unregistered hook env toggles (no MANIFEST E-table row); seven previously undocumented toggles got registered.

### 2026-07-14

- `/afk-toolkit:setup base` — opt-in provisioning of the version-pinned monorepo toolchain (git, JDK, Maven, Node/npm, Python, Docker) plus workstation apps and OS config, for fresh machines and pin bumps.
- `/afk-toolkit:understand` — post-ship interactive HTML explainer per feature (dual-depth background, seam-ordered diff walkthrough, opt-in quiz); auto-run from preflight's advisory row or standalone; surfaced in `INDEX.md` and a new mission-control panel.
- New `interactive-walkthrough` utils skill (agent-invoked): embeddable HTML flow-slider / branching-simulator / overlap-gantt widgets; `draw-charts` became agent-invoked only.

### 2026-07-13

- `/afk-toolkit:bug` — mid-task bug pipeline: `capture` (evidence bundle + Jira Bug before anything else), `dispatch` (autonomous fixer in its own worktree → Draft MR you merge), `status` / `retest` / `purge`.
- `/afk-toolkit:review` rebuilt multi-aspect: 11 book-derived concern checklists, diff-shape triggers for design-level concerns, adversarial skeptic pass before design findings gate, pattern-debt channel.
- Genericity Stop gate: added plugin prose naming a concrete ticket or product symbol blocks the turn (deliberate references go in `hooks/genericity-allow.txt`).
- Verification coverage is exhaustive by default — a subtask declares every applicable tier, not a sample.

### 2026-07-11

- Shared Jira library (`scripts/jira_core.py`): one engine for creds resolution, ADF conversion, and attachment/media upload behind both the PRD and Bug publishers.

### 2026-07-10

- Branch-name gate (git-level, agent-only): an agent creating an off-pattern local branch is refused at ref-update time; branches you create in your own terminal/IDE are never gated.

### 2026-07-09

- Skill-registry Stop gate: a skill dir missing from `plugin.json` blocks the turn — the drift that had silently hidden `/afk-toolkit:setup` and `/afk-toolkit:retro` (both re-registered).
- Lavish artifacts render dark-mode deterministically (PreToolUse hook).
- Delegation routing: mechanical slices route to Sonnet (Haiku tier dropped).

### 2026-07-08

- `/afk-toolkit:setup` — the workflow doctor: probes every entry of the new dependency register (`skills/afk/setup/MANIFEST.md`), fixes what it can, guides the rest; idempotent for first install and post-pull repair.
- `/afk-toolkit:retro` — cross-feature retrospective mining journals, review rollups, and gate metrics into evidence-cited plugin-edit proposals.
- Code Stop gates: maven-compile, ui-lint, java-format — with a content-hash pass cache so unchanged trees cost nothing.
- `/afk-toolkit:to-ticket` meeting mode: publish collapsible Meeting Summaries onto any ticket, disjoint from the PRD block.
- The design chain went purely offline: the SDD is no longer published to Jira.
- CLAUDE.md steward: role-scoped sidecars (`IMPL.md`/`TESTING.md`/`DEBUG.md`) keep CLAUDE.md decision-only.
- Lavish render is mandatory at grill render points when a human is present.

### 2026-07-07

- `/afk-toolkit:mission-control` — read-only per-feature dashboard (watch mode or `--once` retroactive render).
- `/afk-toolkit:preflight` — feature-level ship gate: merges master behind an ancestry guard, re-validates, integrated review, babysits CI, flips the Draft MR to Ready; chained from autopilot after smoke-green.
- `LAVISH.md` + render points: human-present visualizations woven into the grill/design skills.

### 2026-07-06

- Wiring gate ships with the plugin: a new artifact with no consumer and no anchored IOU blocks the turn; `verify-seams` (agent-invoked) is the judgment tier.
- Chain-wide skill audit shipped behavior fixes: park-on-timeout autopilot semantics, bounded adversary respawns, lockstep drift repairs.
- `tdd` and `verify-seams` hidden from the `/` menu (agent-invoked only).

### 2026-07-05

- `/afk-toolkit:autopilot` — hands-off plan driver: fresh subagent per subtask, parks failures + dependents while independent work continues, ends at the smoke gate.
- `/afk-toolkit:adversary` — live-app execution gate probing the running app under an information diet, wired into execute as Step 10.5.
- Human-followability layer: `REPORTING.md` plain-terms protocol, plugin `GLOSSARY.md`, ticket `INDEX.md` dashboard, append-only `plan/JOURNAL.md`, review rollup, `TRACE.md` matrix, grill-log checkpoints.
- Delegation doctrine (`DELEGATION.md`) + named `afk-reader`/`afk-runner` subagents woven through the chain.
- `writing-great-skills` adopted as the skill-authoring reference (`create-skill` retired).

### 2026-07-03

- Staples registry: per-service `STAPLES.md` (stewarded by `/afk-toolkit:claude-md`) with consult/capture loops threaded through grill → PRD → SDD → subtasks → review.

### 2026-06-30

- `/afk-toolkit:review` — independent post-verification review gate (findings contract, severity rubric), wired into execute Step 10.

### 2026-06-29

- Verification doctrine: persistence must be proven by API refetch, never by UI echo alone.

### 2026-06-23

- Plugin lands at `tools/payable/ai-agents/plugins/workflow`: core chain (grill-requirements → to-prd → to-ticket → grill-solution → to-sdd → to-subtasks → execute → smoke-test) plus `prototype`, `design-system`, the `claude-md` steward, and the `tdd` doctrine.
- `/afk-toolkit:fix` — disciplined bug-fix orchestration: diagnose wrap, proportional test coverage, escape analysis of the test that should have caught it.

# AUDIT.md — the drift audit (`/afk:setup audit`)

Hunts staleness between the plugin's artifacts and reality. Read-only — returns
findings routed to the file that must change. The sweeps are repo-wide grep/read
work: delegate to fresh subagents per `DELEGATION.md` (plugin root), keep only
the digests.

Run all eight checks; report even when clean.

## 1 · Structural consistency

Five surfaces that enumerate skills must agree:
`.claude-plugin/plugin.json` and `.codex-plugin/plugin.json` (`skills` arrays) ↔ skill dirs on disk
(`skills/*/*/SKILL.md`) ↔ `README.md` §10 skill reference ↔ `AGENTS.md`
"The skills". A skill on one surface, absent from another → finding (route: the
surface missing it — or `plugin.json` if the dir itself is the stray). Also:
both `.claude-plugin/*.json` descriptions still describe the chain's current
shape.

## 2 · Dependency drift

Grep `skills/`, `hooks/`, `agents/` for dependency-shaped references. Named
patterns are a **floor, not the definition** — an unfamiliar tool name is what
this check exists to catch, so the generic shapes are mandatory:

- MCP tools: `mcp__[a-z_]+`
- Known CLIs: `glab|gh|mmdc|npx |npm |node |python|mvnw|bash |lavish-axi |herdr `
- **Generic command shapes:** any backticked invocation carrying flags
  (`` [a-z][a-z0-9_-]+ --[a-z-]+ ``) and any `scripts/*.{py,sh,mjs,cmd}`
  execution — a hit whose leading token is not a known CLI above is a candidate,
  *especially* if unfamiliar
- Env vars: `[A-Z][A-Z_]{3,}` — every hit is a candidate unless it matches a
  MANIFEST `E`-table var, an `S`-entry secret, or an obvious non-var (Markdown
  heading, acronym in prose)

Diff the hit-set against `MANIFEST.md` entries. A dependency a skill references
but registered nowhere → finding (route: `MANIFEST.md`); a manifest entry no
skill references anymore → finding too (route: delete or annotate).

## 3 · Pointer integrity

Every relative file path cited in the plugin's `.md` files must resolve on
disk — a dead pointer is a stale doc. Sweep two scopes:

- **In-plugin:** paths under the plugin root (sibling `.md`s, `skills/...`,
  `hooks/...`, `agents/...`, `scripts/...`).
- **External anchors:** paths into the consuming repository the skills lean on
  — every one of them comes from `.afk/config.yaml` (a `verification.tiers`
  command, a `verification.env` command, a `setup.extra` file), so the check is
  that the configured path exists, not that a named path does.

- **Install blocks:** each `MANIFEST.md` opt-in whose fix copies a sentinel
  block — its source file exists, and its opening and closing sentinels match
  the strings the entry's probe and fix greps for. A block whose sentinel
  drifted installs nothing and probes clean forever.

Route: the citing file (fix the pointer) — unless the target genuinely moved,
then the finding names both sides.

## 4 · Registry compliance

For each `FRESHNESS.md` registry row: the artifact exists, its steward file
exists, the update-trigger surfaces it names still exist. For each lockstep
pair/triple named in `AGENTS.md` "Lockstep": the sections the pair binds
(emitter grammar ↔ parser expectation) are both still present. Route:
`FRESHNESS.md` for dead rows; the drifted member for broken pairs.

## 5 · Native harness contract

Run `bash "$AFK_PLUGIN_ROOT/hooks/native-contract-gate.sh"`
from the repo root. A failure routes to the named surface. Then run each
installed harness's setup probes from `MANIFEST.md`: plugin enablement, native
skill catalog, hooks, shared MCP, agent definitions, and local activation
cleanup. Record live conformance gaps in `providers/CONFORMANCE.md`.

## 6 · Glossary term usage

`python "$AFK_PLUGIN_ROOT/scripts/glossary_usage.py" "$AFK_PLUGIN_ROOT"` — every
`**Term**:` heading in the plugin-root `GLOSSARY.md` must have ≥1 consumer file
using the term.

Do not grep the heading string. A heading is written for a reader: prose writes
`sign-off` where the heading writes `Sign-off`, one heading can head several
terms, and a trailing parenthetical names the variants the entry covers rather
than part of the term. The script case-folds, drops that qualifier, and splits a
multi-term heading, then requires a consumer for each part.

A zero-hit term means no file uses that word. It is a prompt to look, not a
verdict, and never on its own a reason to delete an entry: check first whether
prose spells the term differently. Where prose legitimately writes it shorter,
the fix is an `_Also_:` line on that entry (`skills/utils/glossary/GLOSSARY-FORMAT.md`),
not a looser check. Report it as a finding (route: `GLOSSARY.md`) only once you
have looked and the term really is unused.

`scripts/tests/test_glossary_usage.py` pins that normalization against the
sixteen headings an earlier, exact-match check reported as unused while every
one of them was in use.

## 7 · Managed behavior

Run these read-only checks from the plugin root:

```sh
python scripts/behavior_registry.py validate --registry BEHAVIORS.md --plugin-root . --dispositions hooks/behavior-dispositions.tsv --parity-root . --verbose
. hooks/lib/provider.sh
args=()
while IFS= read -r -d '' name && IFS= read -r -d '' target \
  && IFS= read -r -d '' root && IFS= read -r -d '' enablement; do
  args+=(--target-root "$target" "$root" "$enablement")
done < <(afk_all_provider_targets)
python scripts/behavior_registry.py audit --registry BEHAVIORS.md --plugin-root . "${args[@]}"
```

Each target is checked against *its own* resolved root and *its own*
enablement (`--target-root TARGET ROOT ENABLEMENT`, one triple per provider,
never colon-joined — `afk_all_provider_targets` is the one home for this
resolution, `hooks/lib/provider.sh`). Every known target is audited every
run, even when its provider's root cannot be independently verified:
`afk_all_provider_targets` then emits an empty ROOT for it, which the audit
reads as "inspect this target's content for a leftover marker, but never
compare it against a rendered expected block" — never as "skip this target."
A leftover managed or legacy block in a target whose root cannot resolve is
exactly the drift this catches; the audit never leaves a target unchecked
the way an install must leave it unwritten. The same applies, independently
of root, when ENABLEMENT is not `enabled`: a provider that is installed
(its root resolves fine) but currently disabled still rejects a leftover
marker — an enabled provider's own clean install never hides a disabled
provider's stale block.

The audit must reject a stale revision or hash, a wrong installed plugin root,
duplicate unified blocks, and any H7, H8, or H10 legacy block. It reports likely
duplicate behavior outside managed sentinels. It never edits that text.

Also run the H1 and O1 plugin-enable probes from `MANIFEST.md`. If both report
disabled, any installed `afk:behaviors` block is stale activation. Route the
finding to `/afk:setup teardown`. Check 7's own per-target ENABLEMENT column
already catches this per provider automatically; H1/O1 remain the whole-run
cross-check for "is the managed-behavior feature itself stale everywhere."

## 8 · Python runtime

Run the `MANIFEST.md` P1 probe. It is read-only. Each `fail` line is a finding:
a missing command, a Python version other than the pin, a command that runs
outside the private environment or is not the installed entry, a stamp from
another `runtime/uv.lock`, installed packages that differ from that lock, a
hook shell that now finds another `afk-python` file than the stamp names, a
failed import, or no `AFK_PYTHON`.
Route: `/afk:setup` (P1 fix).

## Report

Ranked findings (staleness that misleads an agent first, cosmetic last), each:
`[check#] what drifted → file to fix`. Close per `REPORTING.md` — one
plain-terms sentence: is the plugin's documentation trustworthy now, and if not,
which file misleads. Clean run ⇒ say so explicitly; silence is not a verdict.

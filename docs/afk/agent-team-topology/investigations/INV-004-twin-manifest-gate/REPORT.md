C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@9d9fce6 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-004-twin-manifest-gate/COVERAGE.json

## Answer

Native check C (hooks/native-contract-gate.sh:146, :166-196) globs `skills/**/SKILL.md`, maps each file to `./` plus its parent directory, and compares that set separately with the `skills` array of .claude-plugin/plugin.json and of .codex-plugin/plugin.json, trailing `/` stripped. A missing or extra entry in either manifest blocks. It runs at Stop (hooks/stop-gates.sh:130) and at pre-commit (hooks/precommit-gates.sh:140-154). The marketplace files list no skills.

## What a new skill directory must touch

1. An entry `./skills/<group>/<name>` in both manifests: .claude-plugin/plugin.json:16 and .codex-plugin/plugin.json:6. Registry check A (hooks/skill-registry-gate.sh:82-108) reads only the Claude manifest and compares exact strings, so a trailing `/` passes native check C but fails registry check A.
2. A mention in CLAUDE.md and README.md (registry check B, skill-registry-gate.sh:124-136). AGENTS.md is not read.
3. The LANGUAGE.md pointer line (registry check D).
4. Frontmatter whose `name` equals the directory name (registry check F, skill-registry-gate.sh:183-185; hooks/lib/skill_frontmatter_check.py:79-86), with only the allowed keys (native check B, native-contract-gate.sh:139-162).
5. No provider vocabulary in its markdown (native check A, native-contract-gate.sh:80).
6. A group directory of `afk/` or `utils/`: registry checks A, B and D glob only those (skill-registry-gate.sh:70). The registry gate runs at Stop only (stop-gates.sh:125).

## Tests

Only check F is pinned (scripts/tests/test_skill_frontmatter.py:63, :86-92). Native check C and registry checks A, B and D are unguarded. That is an inference backed by reads of hooks/tests/hook-smoke.sh:243-244 and scripts/tests/test_lesson_filing.py:34 and by a search of the tests.

## Frontier

B14: external consumers, including consumers of the marketplace file. How a harness loader treats a skill directory a manifest does not list is outside this repository (human decision S-75): nodes at PROVIDERS.md:11 and :12 and hooks/skill-registry-gate.sh:7. For this design that claim is not load-bearing (S-85): the design lists the new skill in both manifests, and native check C blocks a commit when one is missing.

## Unverified

None.

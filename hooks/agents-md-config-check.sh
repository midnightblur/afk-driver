#!/usr/bin/env bash
# SessionStart notice (ships with the afk plugin): a repository that tracks
# AGENTS.md files needs Claude to load both AGENTS.md and CLAUDE.md, which is the
# instructionFiles=claude-md-and-agents-md setting (setup register row H11).
#
# Warn — never block — when ALL of these hold:
#   - the provider is Claude (the setting is Claude-only; the shim decides this),
#   - the repository at $PWD tracks at least one AGENTS.md, and
#   - the effective setting is not "claude-md-and-agents-md".
# The warning is <=3 lines: it names the setting and says to run /afk:setup.
#
# Run with `--soft`. Every uncertain path exits 0 in silence:
#   - not a Claude session (the setting does not apply),
#   - no git, or the repository tracks no AGENTS.md,
#   - no python, no settings file, or an unreadable value.
#
# The value and the settings-path resolution (which honours CLAUDE_CONFIG_DIR)
# come from set_instruction_files.py --get, the same reader row H11 writes with,
# so this hook duplicates no JSON logic.
set -uo pipefail

ROOT=${AFK_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}

# shellcheck source=/dev/null
. "$ROOT/hooks/lib/provider.sh" 2>/dev/null || exit 0
[ "$(afk_provider 2>/dev/null)" = "claude" ] || exit 0

command -v git >/dev/null 2>&1 || exit 0
git rev-parse --show-toplevel >/dev/null 2>&1 || exit 0

# Fast on a large monorepo: an index read that stops at the first hit. A
# node_modules copy of AGENTS.md is not the repository's own steering.
TRACKED=$(git ls-files -- '*AGENTS.md' ':!:**/node_modules/**' 2>/dev/null | head -n1)
[ -n "$TRACKED" ] || exit 0

PY=python
command -v python >/dev/null 2>&1 || PY=python3
command -v "$PY" >/dev/null 2>&1 || exit 0

READER="$ROOT/skills/afk/setup/scripts/set_instruction_files.py"
[ -f "$READER" ] || exit 0

# No settings file at all -> nothing to warn about, stay silent. A file that
# exists but holds the wrong value (or no value) is what the warning is for.
SETTINGS=$("$PY" "$READER" --path 2>/dev/null) || exit 0
[ -n "$SETTINGS" ] && [ -f "$SETTINGS" ] || exit 0

VALUE=$("$PY" "$READER" --get 2>/dev/null) || exit 0
[ "$VALUE" = "claude-md-and-agents-md" ] && exit 0

printf 'This repository tracks AGENTS.md files, but the Claude setting\n'
printf 'pluginConfigs."agents-md@builtin".options.instructionFiles is "%s".\n' "$VALUE"
printf 'Run /afk:setup (register row H11) to set it to "claude-md-and-agents-md" so those files load.\n'
exit 0

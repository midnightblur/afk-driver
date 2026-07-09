#!/usr/bin/env bash
# Stop hook (ships with the afk plugin): skill-registry gate — every skill dir
# under skills/afk/ and skills/utils/ (and every agent under agents/) must be
# listed in .claude-plugin/plugin.json, or the plugin loader never registers
# it and it's invisible in-session (silent, no error) — happened for
# skills/afk/setup and skills/afk/retro (added in 331deb608a5, plugin.json
# never updated; caught only when a human noticed the skill was missing).
#
# Verdict:
#   dir with SKILL.md / agent .md, listed in plugin.json   -> pass
#   dir with SKILL.md / agent .md, NOT listed               -> orphan, exit 2
#   plugin.json entry pointing at a dir that no longer exists -> stale, exit 2
#
# Mechanical only: existence + membership. Doesn't validate SKILL.md content.
# Disable: SKILL_REGISTRY_GATE_DISABLE=1, or repo file .claude/hooks/.gate-disabled.

set -u

[ "${SKILL_REGISTRY_GATE_DISABLE:-0}" = "1" ] && exit 0

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$repo_root" || exit 0

if [ -f .claude/hooks/.gate-disabled ]; then
  exit 0
fi

PLUGIN_DIR="tools/payable/ai-agents/plugins/workflow"
MANIFEST="$PLUGIN_DIR/.claude-plugin/plugin.json"

# Not this plugin's checkout — nothing to gate.
[ -f "$MANIFEST" ] || exit 0

. "$(dirname "${BASH_SOURCE[0]}")/gate-metrics.sh"

# ---- actual dirs on disk (relative to PLUGIN_DIR, "./skills/afk/<name>" shape)
actual_skills=$(
  { find "$PLUGIN_DIR/skills/afk" -maxdepth 2 -type f -name SKILL.md 2>/dev/null
    find "$PLUGIN_DIR/skills/utils" -maxdepth 2 -type f -name SKILL.md 2>/dev/null
  } | sed -E "s#^$PLUGIN_DIR/(.*)/SKILL\.md\$#./\1#" | sort -u
)
actual_agents=$(
  find "$PLUGIN_DIR/agents" -maxdepth 1 -type f -name '*.md' 2>/dev/null \
    | sed -E "s#^$PLUGIN_DIR/agents/#./agents/#" | sort -u
)

# ---- entries declared in plugin.json (python: no assumption about JSON layout)
declared=$(python -c "
import json, sys
try:
    m = json.load(open(sys.argv[1], encoding='utf-8'))
except Exception:
    sys.exit(0)
for s in m.get('skills', []): print('SKILL\t' + s)
for a in m.get('agents', []): print('AGENT\t' + a)
" "$MANIFEST" 2>/dev/null)
[ -z "$declared" ] && exit 0   # can't parse manifest — don't false-block on it

declared_skills=$(printf '%s\n' "$declared" | awk -F'\t' '$1=="SKILL"{print $2}' | sort -u)
declared_agents=$(printf '%s\n' "$declared" | awk -F'\t' '$1=="AGENT"{print $2}' | sort -u)

n_checked=$(printf '%s\n%s\n' "$actual_skills" "$actual_agents" | sed '/^$/d' | wc -l | tr -d '[:space:]')
gate_metrics_begin

orphan_skills=$(comm -23 <(printf '%s\n' "$actual_skills") <(printf '%s\n' "$declared_skills"))
orphan_agents=$(comm -23 <(printf '%s\n' "$actual_agents") <(printf '%s\n' "$declared_agents"))
stale_skills=$(comm -13 <(printf '%s\n' "$actual_skills") <(printf '%s\n' "$declared_skills") | while IFS= read -r s; do [ -n "$s" ] && [ ! -d "$PLUGIN_DIR/${s#./}" ] && printf '%s\n' "$s"; done)
stale_agents=$(comm -13 <(printf '%s\n' "$actual_agents") <(printf '%s\n' "$declared_agents") | while IFS= read -r a; do [ -n "$a" ] && [ ! -f "$PLUGIN_DIR/${a#./}" ] && printf '%s\n' "$a"; done)

orphans=$(printf '%s\n%s\n' "$orphan_skills" "$orphan_agents" | sed '/^$/d')
stale=$(printf '%s\n%s\n' "$stale_skills" "$stale_agents" | sed '/^$/d')

if [ -n "$orphans" ] || [ -n "$stale" ]; then
  gate_metrics_emit skill-registry blocked "\"checked\":$n_checked"
  {
    printf '[afk] Skill-registry gate: %s drifted from disk.\n' "$MANIFEST"
    if [ -n "$orphans" ]; then
      printf 'On disk but NOT in plugin.json (invisible to the plugin loader — add them):\n'
      printf '%s\n' "$orphans" | sed 's/^/  - /'
    fi
    if [ -n "$stale" ]; then
      printf 'In plugin.json but no longer on disk (remove the entry):\n'
      printf '%s\n' "$stale" | sed 's/^/  - /'
    fi
    printf 'Fix: edit the "skills"/"agents" array in %s, then /reload-plugins.\n' "$MANIFEST"
  } >&2
  exit 2
fi

gate_metrics_emit skill-registry pass "\"checked\":$n_checked"
exit 0

#!/usr/bin/env bash
# Stop hook (ships with the afk plugin): registry gate — the plugin's three
# machine-checkable registries must match disk. Three checks:
#
# A. plugin.json membership — every skill dir under skills/afk/ + skills/utils/
#    (and every agent under agents/) is listed in .claude-plugin/plugin.json,
#    or the plugin loader never registers it and it's invisible in-session
#    (silent, no error) — happened for skills/afk/setup and skills/afk/retro
#    (added in 331deb608a5, plugin.json never updated; caught only when a
#    human noticed the skill was missing).
# B. skill catalog — every skill name is mentioned in the plugin's CLAUDE.md
#    and README.md (as /afk:<name>, `<name>`, or its skills/ path); an agent
#    reading the harness never learns an uncatalogued skill exists — happened
#    for seven skills/utils/ entries, caught only by an /afk:setup audit.
# C. env-toggle register — every external all-caps env var read by hooks/*.sh
#    (read but never assigned in hooks/, ambient vars excluded) appears in the
#    dependency register skills/afk/setup/MANIFEST.md (§E) — happened for six
#    gate toggles, caught only by an /afk:setup audit.
#
# Verdict per check: membership present -> pass; missing -> exit 2 (with the
# exact list + where to add it); plugin.json entry pointing at a dir that no
# longer exists -> stale, exit 2.
#
# Mechanical only: existence + membership. Doesn't validate SKILL.md content,
# catalog wording, or E-table row accuracy — /afk:setup audit judges those.
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

# ---- check B: every skill name catalogued in the plugin's CLAUDE.md + README.md
# Accepted mention shapes: /afk:<name>, `<name>`, or its skills/(afk|utils)/<name> path.
uncatalogued=""
for doc in CLAUDE.md README.md; do
  [ -f "$PLUGIN_DIR/$doc" ] || continue
  while IFS= read -r s; do
    [ -n "$s" ] || continue
    name=${s##*/}
    if ! grep -qE "(/afk:$name|\`$name\`|skills/(afk|utils)/$name)" "$PLUGIN_DIR/$doc"; then
      uncatalogued="$uncatalogued  - $name (missing from $doc)"$'\n'
    fi
  done <<EOF
$actual_skills
EOF
done

# ---- check C: every external env var read by hooks/*.sh is in the setup register.
# External = read ($VAR / ${VAR...}) somewhere in hooks/*.sh but assigned nowhere
# in hooks/ (a self-default VAR=${VAR:-...} counts as a read, not an assignment).
# Ambient OS/harness vars are not toggles and are excluded.
REGISTER="$PLUGIN_DIR/skills/afk/setup/MANIFEST.md"
ambient='PATH|HOME|USERPROFILE|TMPDIR|TEMP|TMP|PWD|OLDPWD|IFS|BASH_SOURCE|FUNCNAME|OSTYPE|JAVA_HOME|CLAUDECODE|CLAUDE_PLUGIN_ROOT'
unregistered=""
if [ -f "$REGISTER" ]; then
  hook_reads=$(grep -hvE '^[[:space:]]*#' "$PLUGIN_DIR"/hooks/*.sh "$PLUGIN_DIR"/hooks/lib/*.sh 2>/dev/null \
    | grep -oE '\$\{?[A-Z][A-Z0-9_]{2,}' \
    | sed -E 's/^\$\{?//' | sort -u | grep -vE "^($ambient)$")
  for v in $hook_reads; do
    # assigned in hooks/ (comment lines stripped; self-defaults don't count) => internal
    if grep -hvE '^[[:space:]]*#' "$PLUGIN_DIR"/hooks/*.sh "$PLUGIN_DIR"/hooks/lib/*.sh 2>/dev/null \
        | grep -E "(^|[^A-Za-z0-9_\$])${v}=" | grep -vE "${v}=\"?\\\$\{${v}[:}-]" | grep -q .; then
      continue
    fi
    grep -qE "(^|[^A-Za-z0-9_])${v}([^A-Za-z0-9_]|$)" "$REGISTER" \
      || unregistered="$unregistered  - $v"$'\n'
  done
fi

if [ -n "$orphans" ] || [ -n "$stale" ] || [ -n "$uncatalogued" ] || [ -n "$unregistered" ]; then
  gate_metrics_emit skill-registry blocked "\"checked\":$n_checked"
  {
    printf '[afk] Registry gate: a plugin registry drifted from disk.\n'
    if [ -n "$orphans" ]; then
      printf 'On disk but NOT in plugin.json (invisible to the plugin loader — add to the "skills"/"agents" array, then /reload-plugins):\n'
      printf '%s\n' "$orphans" | sed 's/^/  - /'
    fi
    if [ -n "$stale" ]; then
      printf 'In plugin.json but no longer on disk (remove the entry):\n'
      printf '%s\n' "$stale" | sed 's/^/  - /'
    fi
    if [ -n "$uncatalogued" ]; then
      printf 'Skill exists but is uncatalogued (add a /afk:<name> mention to the named doc — an agent reading the harness never learns it exists):\n%s' "$uncatalogued"
    fi
    if [ -n "$unregistered" ]; then
      printf 'Env toggle read by hooks/*.sh but absent from the dependency register (add an E-table row in %s):\n%s' "$REGISTER" "$unregistered"
    fi
  } >&2
  exit 2
fi

gate_metrics_emit skill-registry pass "\"checked\":$n_checked"
exit 0

#!/usr/bin/env bash
# Stop gate (ships with the afk plugin): registry gate — the plugin's three
# machine-checkable registries must match disk. Three checks:
#
# A. Claude plugin.json membership — every skill dir under skills/afk/ + skills/utils/
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
# D. language pointer — every SKILL.md + agents/*.md names LANGUAGE.md (the one
#    home for the writing doctrine). Root docs are not auto-loaded, so a file
#    missing the pointer runs blind to the doctrine, which is exactly how it
#    drifted before.
# E. adapter coherence — an adapter kind is described in four places, and a kind
#    described in three of them is a kind nobody can select. For every
#    adapters/<family>/<kind>/: adapter.json parses and its runner entry exists
#    on disk; CONTRACT.md names every operation adapter.json declares; the kind
#    appears in its family's enum in CONFIG.md; every configuration key it reads
#    appears in CONFIG.md; and every register row it declares in `register`
#    exists as a heading in the dependency register.
#
# Verdict per check: membership present -> pass; missing -> exit 2 (with the
# exact list + where to add it); plugin.json entry pointing at a dir that no
# longer exists -> stale, exit 2.
#
# Checks B and C each used to re-grep the same files once per skill / per env
# var (~200 subprocesses). Every input file is now read ONCE into a variable and
# matched with bash patterns, so the whole gate costs a handful of spawns.
#
# Mechanical only: existence + Claude-manifest membership + pointer presence.
# native-contract-gate.sh owns twin-manifest parity and allowed frontmatter;
# /afk:setup audit judges catalog wording and E-table row accuracy.
# Disable: SKILL_REGISTRY_GATE_DISABLE=1, or repo file .claude/hooks/.gate-disabled.

set -u

gate_skill_registry() {
  [ "${SKILL_REGISTRY_GATE_DISABLE:-0}" = "1" ] && return 0
  [ -f .claude/hooks/.gate-disabled ] && return 0

  local PLUGIN_DIR PLUGIN_SCOPE; PLUGIN_DIR=$(afk_plugin_dir); PLUGIN_SCOPE=$(afk_plugin_scope)
  local MANIFEST="$PLUGIN_DIR/.claude-plugin/plugin.json"
  [ -f "$MANIFEST" ] || return 0          # not this plugin's checkout

  # Every input this gate reads lives under the plugin dir, so an edit anywhere
  # else cannot change its verdict and must not invalidate its pass.
  local cache_key
  cache_key=$(gate_cache_key skill-registry "$PLUGIN_SCOPE*")
  gate_cache_hit skill-registry "$cache_key" && return 0

  gate_metrics_begin

  # ---- actual dirs on disk ("./skills/afk/<name>" shape). Globs, not find.
  local p name
  local -a actual_skills=() actual_agents=()
  for p in "$PLUGIN_DIR"/skills/afk/*/SKILL.md "$PLUGIN_DIR"/skills/utils/*/SKILL.md; do
    [ -f "$p" ] || continue
    p=${p#"$PLUGIN_DIR"/}; actual_skills+=("./${p%/SKILL.md}")
  done
  for p in "$PLUGIN_DIR"/agents/*.md; do
    [ -f "$p" ] || continue
    actual_agents+=("./agents/${p##*/}")
  done

  # ---- entries declared in plugin.json (python: no assumption about JSON layout)
  local py=python declared
  command -v python >/dev/null 2>&1 || py=python3    # python3-only machines: same fallback as native-contract-gate.sh
  declared=$("$py" -c "
import json, sys
try:
    m = json.load(open(sys.argv[1], encoding='utf-8'))
except Exception:
    sys.exit(0)
for s in m.get('skills', []): print('SKILL\t' + s)
for a in m.get('agents', []): print('AGENT\t' + a)
" "$MANIFEST" 2>/dev/null)
  [ -z "$declared" ] && return 0   # can't parse manifest — don't false-block on it

  local -A decl_skill=() decl_agent=()
  local kind val
  while IFS=$'\t' read -r kind val; do
    val=${val%$'\r'}          # Windows python writes CRLF; the CR would break every match
    [ -n "${val:-}" ] || continue
    case "$kind" in
      SKILL) decl_skill["$val"]=1 ;;
      AGENT) decl_agent["$val"]=1 ;;
    esac
  done <<<"$declared"

  local n_checked=$(( ${#actual_skills[@]} + ${#actual_agents[@]} ))
  local orphans="" stale="" s a

  for s in ${actual_skills[@]+"${actual_skills[@]}"}; do
    [ -n "${decl_skill[$s]:-}" ] || orphans="$orphans$s"$'\n'
  done
  for a in ${actual_agents[@]+"${actual_agents[@]}"}; do
    [ -n "${decl_agent[$a]:-}" ] || orphans="$orphans$a"$'\n'
  done
  for s in "${!decl_skill[@]}"; do
    [ -d "$PLUGIN_DIR/${s#./}" ] || stale="$stale$s"$'\n'
  done
  for a in "${!decl_agent[@]}"; do
    [ -f "$PLUGIN_DIR/${a#./}" ] || stale="$stale$a"$'\n'
  done

  # ---- check B: every skill name catalogued in the plugin's CLAUDE.md + README.md.
  # Accepted mention shapes: /afk:<name>, `<name>`, or its skills/(afk|utils)/<name> path.
  # Each doc is read once; the per-skill test is a fork-free bash pattern match.
  local uncatalogued="" doc doc_body
  for doc in CLAUDE.md README.md; do
    [ -f "$PLUGIN_DIR/$doc" ] || continue
    doc_body=$(<"$PLUGIN_DIR/$doc")
    for s in ${actual_skills[@]+"${actual_skills[@]}"}; do
      name=${s##*/}
      if [[ "$doc_body" != *"/afk:$name"* \
         && "$doc_body" != *'`'"$name"'`'* \
         && "$doc_body" != *"skills/afk/$name"* \
         && "$doc_body" != *"skills/utils/$name"* ]]; then
        uncatalogued="$uncatalogued  - $name (missing from $doc)"$'\n'
      fi
    done
  done

  # ---- check C: every external env var read by hooks/*.sh is in the setup register.
  # External = read ($VAR / ${VAR...}) somewhere in hooks/*.sh but assigned nowhere
  # in hooks/ (a self-default VAR=${VAR:-...} counts as a read, not an assignment).
  # Ambient OS/harness vars are not toggles and are excluded.
  local REGISTER="$PLUGIN_DIR/skills/afk/setup/MANIFEST.md"
  local ambient='PATH|HOME|USERPROFILE|TMPDIR|TEMP|TMP|PWD|OLDPWD|IFS|BASH_SOURCE|FUNCNAME|OSTYPE|JAVA_HOME|CLAUDECODE|CLAUDE_PLUGIN_ROOT'
  local unregistered=""
  if [ -f "$REGISTER" ]; then
    # One read of every hook source (comments stripped) and one of the register;
    # all per-var tests below are bash regex against these strings.
    local hooks_src register_body v
    hooks_src=$(grep -hvE '^[[:space:]]*#' "$PLUGIN_DIR"/hooks/*.sh "$PLUGIN_DIR"/hooks/lib/*.sh 2>/dev/null)
    register_body=$(<"$REGISTER")

    # Assignment set, built in one pass. Each match is "VAR=" optionally followed
    # by the start of a ${...} expansion, which is what tells a real assignment
    # (VAR=x) apart from a self-default (VAR=${VAR:-x}) — the latter is a read.
    local -A assigned=()
    local m lhs rhs
    while IFS= read -r m; do
      [ -n "$m" ] || continue
      m=${m#"${m%%[A-Z]*}"}          # drop the leading delimiter char, if any
      lhs=${m%%=*}
      rhs=${m#*=}
      rhs=${rhs#\"}; rhs=${rhs#\$\{}
      # Same name on both sides means a self-default expansion, which is a READ
      # of an external toggle, not an assignment of an internal one.
      [ "$rhs" = "$lhs" ] && continue
      assigned["$lhs"]=1
    done < <(printf '%s' "$hooks_src" | grep -oE '(^|[^A-Za-z0-9_$])[A-Z][A-Z0-9_]{2,}=("?\$\{[A-Z][A-Z0-9_]{2,})?')

    local hook_reads
    hook_reads=$(printf '%s' "$hooks_src" | grep -oE '\$\{?[A-Z][A-Z0-9_]{2,}' | sed -E 's/^\$\{?//' | sort -u)
    while IFS= read -r v; do
      [ -n "$v" ] || continue
      [[ "$v" =~ ^($ambient)$ ]] && continue
      [ -n "${assigned[$v]:-}" ] && continue      # assigned in hooks/ => internal
      [[ "$register_body" =~ (^|[^A-Za-z0-9_])"$v"([^A-Za-z0-9_]|$) ]] \
        || unregistered="$unregistered  - $v"$'\n'
    done <<<"$hook_reads"
  fi

  # ---- check D: every skill + agent file carries the LANGUAGE.md pointer line.
  # One grep -L over the whole set (files WITHOUT a match), not a test per file.
  local no_language
  no_language=$(grep -L 'LANGUAGE\.md' "$PLUGIN_DIR"/skills/afk/*/SKILL.md \
    "$PLUGIN_DIR"/skills/utils/*/SKILL.md "$PLUGIN_DIR"/agents/*.md 2>/dev/null \
    | sed "s|^$PLUGIN_DIR/||")

  # ---- check E: adapter.json <-> its entry <-> CONTRACT.md <-> CONFIG.md <->
  # the register. One python pass over every adapter, so the cost is one spawn
  # whatever the number of families.
  local adapter_drift=""
  if [ -d "$PLUGIN_DIR/adapters" ]; then
    local _py=python
    command -v python >/dev/null 2>&1 || _py=python3
    adapter_drift=$("$_py" "$PLUGIN_DIR/hooks/lib/adapter_registry_check.py" "$PLUGIN_DIR" 2>&1)
  fi

  if [ -n "$orphans" ] || [ -n "$stale" ] || [ -n "$uncatalogued" ] || [ -n "$unregistered" ] || [ -n "$no_language" ] || [ -n "$adapter_drift" ]; then
    gate_metrics_emit skill-registry blocked "\"checked\":$n_checked"
    {
      printf '[afk] Registry gate: a plugin registry drifted from disk.\n'
      if [ -n "$orphans" ]; then
        printf 'On disk but NOT in plugin.json (invisible to the plugin loader — add to the "skills"/"agents" array, then /reload-plugins):\n'
        printf '%s' "$orphans" | sed 's/^/  - /'
      fi
      if [ -n "$stale" ]; then
        printf 'In plugin.json but no longer on disk (remove the entry):\n'
        printf '%s' "$stale" | sed 's/^/  - /'
      fi
      if [ -n "$uncatalogued" ]; then
        printf 'Skill exists but is uncatalogued (add a /afk:<name> mention to the named doc — an agent reading the harness never learns it exists):\n%s' "$uncatalogued"
      fi
      if [ -n "$unregistered" ]; then
        printf 'Env toggle read by hooks/*.sh but absent from the dependency register (add an E-table row in %s):\n%s' "$REGISTER" "$unregistered"
      fi
      if [ -n "$no_language" ]; then
        printf 'Skill/agent file missing the LANGUAGE.md pointer line (copy the one-liner any sibling SKILL.md carries right after its frontmatter):\n'
        printf '%s\n' "$no_language" | sed 's/^/  - /'
      fi
      if [ -n "$adapter_drift" ]; then
        printf 'Adapter described in some places but not all (ADAPTERS.md "Adding a kind" lists the four):\n'
        printf '%s\n' "$adapter_drift" | sed 's/^/  - /'
      fi
    } >&2
    return 2
  fi

  gate_metrics_emit skill-registry pass "\"checked\":$n_checked"
  gate_cache_store skill-registry "$cache_key"
  return 0
}

# ---- standalone invocation
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  _d=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  _root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  cd "$_root" || exit 0
  # provider.sh first: this gate resolves the plugin's own directory through
  # afk_plugin_dir, and without it a manual run would scope to nothing and
  # report a silent pass.
  . "$_d/lib/provider.sh"
  . "$_d/lib/config.sh"; afk_config_load
  . "$_d/gate-context.sh"; gate_ctx_build
  . "$_d/gate-cache.sh"
  . "$_d/gate-metrics.sh"
  gate_skill_registry; exit $?
fi

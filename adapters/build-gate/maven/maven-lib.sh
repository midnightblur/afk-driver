#!/usr/bin/env bash
# Shared helpers for the Maven build-gate adapter. Every repository fact this
# adapter needs comes from the `maven:` block of `.afk/config.yaml`, read through
# the AFK_CFG_* export that hooks/lib/config.sh publishes. Nothing here names a
# repository, a module or a formatter profile.
#
# Source this from a gate; it is idempotent.

[ -n "${AFK_MAVEN_LIB_LOADED:-}" ] && return 0
AFK_MAVEN_LIB_LOADED=1

AFK_MAVEN_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# The gate context, cache and metrics libraries stay with the hook runner: they
# are shared by every family, not owned by this adapter.
AFK_MAVEN_HOOKS_DIR="${AFK_PLUGIN_ROOT:-$(cd "$AFK_MAVEN_DIR/../../.." && pwd)}/hooks"

# `maven.reactor-pom` — the POM every reactor invocation is run against. Absent
# means the repository declared no Maven reactor, and every Maven gate is inert.
afk_maven_reactor() { printf '%s' "${AFK_CFG_MAVEN_REACTOR_POM:-}"; }

# True when this checkout is the one the configuration describes.
afk_maven_available() {
  local pom; pom=$(afk_maven_reactor)
  [ -n "$pom" ] && [ -f "$pom" ]
}

# `maven.skip-ui-flag` — the property a reactor pass sets to leave UI modules
# out. Emitted as zero or one argument, so a repository with no such property
# simply contributes nothing.
afk_maven_skip_ui() {
  [ -n "${AFK_CFG_MAVEN_SKIP_UI_FLAG:-}" ] && printf '%s' "$AFK_CFG_MAVEN_SKIP_UI_FLAG"
}

# The Maven module owning a path: the nearest ancestor directory holding a
# pom.xml, excluding the reactor root itself (a change under the root but inside
# no module has no module to build). Prints nothing when there is none.
afk_maven_module_of() {
  local path=$1 dir reactor_dir
  reactor_dir=$(dirname "$(afk_maven_reactor)")
  [ "$reactor_dir" = "." ] && reactor_dir=""
  dir=${path%/*}
  [ "$dir" = "$path" ] && return 0
  while [ -n "$dir" ] && [ "$dir" != "." ] && [ "$dir" != "/" ]; do
    if [ -f "$dir/pom.xml" ] && [ "$dir" != "$reactor_dir" ]; then
      printf '%s' "$dir"
      return 0
    fi
    [ "${dir%/*}" = "$dir" ] && break
    dir=${dir%/*}
  done
  return 0
}

# The unique modules owning a newline-separated list of paths, sorted.
afk_maven_modules_of() {
  local paths=$1 p m out=""
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    m=$(afk_maven_module_of "$p")
    [ -n "$m" ] && out+="$m"$'\n'
  done <<<"$paths"
  printf '%s' "$out" | sort -u
}

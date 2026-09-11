#!/usr/bin/env bash
# The environment table of a plugin issue, as one JSON object on stdout.
#
#   collect_env.sh [--plan-dir DIR] [--journal-lines N]
#
# Fields: plugin_version, provider, os, git, gh, python, the adapter KINDS the
# repository selected (tracker, forge, notes, build_gates — never a value
# under them), and journal_tail (the last N lines of DIR/JOURNAL.md, default
# 20; empty without --plan-dir). Raw, unredacted: the caller redacts the body
# it lands in. A tool that is absent reports "absent". Exit 2 on a usage error.

set -u

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
root=$(cd "$here/../../../.." && pwd)
py=python; command -v python >/dev/null 2>&1 || py=python3

plan_dir="" lines=20
while [ $# -gt 0 ]; do
  case "$1" in
    --plan-dir) plan_dir=${2-}; shift 2 || exit 2 ;;
    --journal-lines) lines=${2-}; shift 2 || exit 2 ;;
    *) echo "collect_env: unknown argument $1" >&2; exit 2 ;;
  esac
done
case "$lines" in ''|*[!0-9]*) echo "collect_env: --journal-lines needs a number" >&2; exit 2 ;; esac

version() { command -v "$1" >/dev/null 2>&1 && "$@" 2>&1 | head -n 1 || echo absent; }
cfg() { "$py" "$root/scripts/afk-config.py" get "$1" 2>/dev/null || true; }

provider=$(. "$root/hooks/lib/provider.sh" >/dev/null 2>&1 && afk_provider 2>/dev/null) || provider=""
journal=""
if [ -n "$plan_dir" ] && [ -f "$plan_dir/JOURNAL.md" ]; then
  journal=$(tail -n "$lines" "$plan_dir/JOURNAL.md")
fi

ENV_ROOT="$root" \
ENV_PROVIDER="${provider:-unknown}" \
ENV_OS="$(uname -srm 2>/dev/null || echo unknown)" \
ENV_GIT="$(version git --version)" \
ENV_GH="$(version gh --version)" \
ENV_PYTHON="$(version "$py" --version)" \
ENV_TRACKER="$(cfg tracker)" \
ENV_FORGE="$(cfg forge)" \
ENV_NOTES="$(cfg notes)" \
ENV_BUILD_GATES="$(cfg build-gates)" \
ENV_JOURNAL="$journal" \
"$py" - <<'PY'
import json, os
from pathlib import Path

env = os.environ
try:
    manifest = json.loads((Path(env["ENV_ROOT"]) / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    version = manifest.get("version", "unknown")
except (OSError, ValueError):
    version = "unknown"
try:
    gates = json.loads(env["ENV_BUILD_GATES"]) if env["ENV_BUILD_GATES"] else []
except ValueError:
    gates = [env["ENV_BUILD_GATES"]]
print(json.dumps({
    "plugin_version": version,
    "provider": env["ENV_PROVIDER"],
    "os": env["ENV_OS"],
    "git": env["ENV_GIT"],
    "gh": env["ENV_GH"],
    "python": env["ENV_PYTHON"],
    "tracker": env["ENV_TRACKER"] or "none",
    "forge": env["ENV_FORGE"] or "none",
    "notes": env["ENV_NOTES"] or "unknown",
    "build_gates": gates,
    "journal_tail": env["ENV_JOURNAL"],
}, indent=2, ensure_ascii=True))
PY

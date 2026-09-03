#!/usr/bin/env bash
# Provider detection, native hook-envelope, launcher and native-twin smoke tests.
#
# Everything here is self-contained: the plugin ships no repository-owned
# handler, so the repository-hook path is exercised against a throwaway fixture
# repository built in this script.

set -uo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
workflow=$(cd "$here/../.." && pwd)
envelopes="$here/envelopes"
shim="$workflow/hooks/lib/provider.sh"
lavish="$workflow/hooks/lavish-dark.sh"
lavish_tips="$workflow/hooks/lavish-tips.sh"

command -v jq >/dev/null 2>&1 || { echo "SKIP: jq not on PATH" >&2; exit 0; }

fails=0
pass() { echo "  ok: $1"; }
fail() { echo "  FAIL: $1" >&2; fails=$((fails + 1)); }

detect() {
  env AFK_PROVIDER="${AFK_PROVIDER_CASE:-}" \
      PLUGIN_ROOT="${PLUGIN_ROOT_CASE:-}" PLUGIN_DATA="${PLUGIN_DATA_CASE:-}" \
      CLAUDE_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT_CASE:-}" \
      CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA_CASE:-}" \
      CLAUDECODE="${CLAUDECODE_CASE:-}" \
      bash -c '. "$1"; afk_provider' _ "$shim"
}

assert_detect() {
  local label=$1 expected=$2 actual
  actual=$(detect)
  if [ "$actual" = "$expected" ]; then
    pass "$label"
  else
    fail "$label (expected=$expected actual=$actual)"
  fi
}

echo "== provider detection =="
AFK_PROVIDER_CASE=claude PLUGIN_ROOT_CASE=/codex CLAUDECODE_CASE=1 \
  assert_detect "AFK_PROVIDER override wins" claude
AFK_PROVIDER_CASE=nonsense PLUGIN_ROOT_CASE= CLAUDECODE_CASE=1 \
  assert_detect "unknown AFK_PROVIDER is reported, never guessed" unknown
AFK_PROVIDER_CASE= PLUGIN_ROOT_CASE=/codex CLAUDE_PLUGIN_ROOT_CASE=/compat CLAUDECODE_CASE=1 \
  assert_detect "PLUGIN_ROOT wins over inherited CLAUDECODE" codex
AFK_PROVIDER_CASE= PLUGIN_ROOT_CASE= CLAUDE_PLUGIN_ROOT_CASE=/claude CLAUDECODE_CASE= \
  assert_detect "CLAUDE_PLUGIN_ROOT detects Claude" claude
AFK_PROVIDER_CASE= PLUGIN_ROOT_CASE= CLAUDE_PLUGIN_ROOT_CASE= CLAUDECODE_CASE=1 \
  assert_detect "CLAUDECODE fallback detects Claude" claude
AFK_PROVIDER_CASE= PLUGIN_ROOT_CASE= CLAUDE_PLUGIN_ROOT_CASE= CLAUDECODE_CASE= \
  assert_detect "no marker is unknown" unknown

actual=$(PLUGIN_ROOT=/codex-root PLUGIN_DATA=/codex-data \
  CLAUDE_PLUGIN_ROOT=/compat-root CLAUDE_PLUGIN_DATA=/compat-data CLAUDECODE=1 \
  bash -c '. "$1"; printf "%s|%s" "$(afk_plugin_root)" "$(afk_plugin_data)"' _ "$shim")
if [ "$actual" = "/codex-root|/codex-data" ]; then
  pass "Codex prefers native root and data variables"
else
  fail "Codex root/data precedence (actual=$actual)"
fi

actual=$(PLUGIN_ROOT= PLUGIN_DATA= CLAUDE_PLUGIN_ROOT=/claude-root \
  CLAUDE_PLUGIN_DATA=/claude-data CLAUDECODE=1 \
  bash -c '. "$1"; printf "%s|%s" "$(afk_plugin_root)" "$(afk_plugin_data)"' _ "$shim")
if [ "$actual" = "/claude-root|/claude-data" ]; then
  pass "Claude uses compatibility root and data variables"
else
  fail "Claude root/data precedence (actual=$actual)"
fi

for adapter in "$workflow"/hooks/lib/providers/*.sh; do
  provider=${adapter##*/}
  provider=${provider%.sh}
  provider_envelopes="$envelopes/$provider"
  echo "== provider: $provider =="

  for event in session-start pretooluse-bash-safe stop; do
    fixture="$provider_envelopes/$event.json"
    parsed=$(AFK_PROVIDER="$provider" bash -c \
      '. "$1"; afk_hook_input; printf "%s" "$(afk_hook_field hook_event_name)"' \
      _ "$shim" < "$fixture")
    case "$event:$parsed" in
      session-start:SessionStart|pretooluse-bash-safe:PreToolUse|stop:Stop)
        pass "$event envelope parses" ;;
      *) fail "$event envelope parse (actual=$parsed)" ;;
    esac
  done

  out=$(AFK_PROVIDER="$provider" bash "$lavish" \
    < "$provider_envelopes/pretooluse-bash-safe.json" 2>/dev/null)
  rc=$?
  if [ "$rc" = 0 ]; then
    pass "lavish-dark passes non-render command"
  else
    fail "lavish-dark pass-through (rc=$rc)"
  fi

  block_out=$(AFK_PROVIDER="$provider" bash -c \
    '. "$1"; afk_emit_stop_block "gate said no"' _ "$shim" 2>/dev/null)
  block_err=$(AFK_PROVIDER="$provider" bash -c \
    '. "$1"; afk_emit_stop_block "gate said no"' _ "$shim" 2>&1 >/dev/null)
  block_code=$(AFK_PROVIDER="$provider" bash -c \
    '. "$1"; afk_stop_block_code' _ "$shim")
  if printf '%s' "$block_out" | jq -e \
      '.decision == "block" and (.reason | length > 0)' >/dev/null \
      && [ "$block_err" = "gate said no" ] && [ -n "$block_code" ]; then
    pass "stop block emits a decision, the findings, and an exit code"
  else
    fail "stop block emission (json=$block_out stderr=$block_err code=$block_code)"
  fi

  out=$(AFK_PROVIDER="$provider" bash "$lavish_tips" \
    < "$provider_envelopes/pretooluse-bash-safe.json" 2>/dev/null)
  rc=$?
  if [ "$rc" = 0 ]; then
    pass "lavish-tips passes non-render command"
  else
    fail "lavish-tips pass-through (rc=$rc)"
  fi
done

# ---- the launcher every hook command goes through.
launcher="$workflow/hooks/run-hook.py"
py=python
command -v python >/dev/null 2>&1 || py=python3

echo "== hook launcher =="

# A throwaway consuming repository: one declared PreToolUse handler that denies,
# one declared Stop handler that blocks, and one path that escapes the root.
fixture_repo=$(mktemp -d)
git -C "$fixture_repo" init -q
mkdir -p "$fixture_repo/.afk" "$fixture_repo/hooks"
cat > "$fixture_repo/hooks/deny.sh" <<'FIXTURE'
#!/usr/bin/env bash
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"fixture"}}\n'
exit 0
FIXTURE
cat > "$fixture_repo/hooks/block.sh" <<'FIXTURE'
#!/usr/bin/env bash
echo "fixture stop finding" >&2
exit 2
FIXTURE
cat > "$fixture_repo/.afk/hooks.json" <<'FIXTURE'
[
  {"event": "PreToolUse", "matcher": "Bash|PowerShell", "timeout": 15, "script": "hooks/deny.sh"},
  {"event": "PreToolUse", "matcher": "Grep", "timeout": 15, "script": "hooks/escape.sh"},
  {"event": "Stop", "matcher": "*", "timeout": 60, "script": "hooks/block.sh"}
]
FIXTURE
python - "$fixture_repo" <<'PY'
import json, sys
root = sys.argv[1]
path = root + "/.afk/hooks.json"
data = json.load(open(path, encoding="utf-8"))
data[1]["script"] = "../outside.sh"
json.dump(data, open(path, "w", encoding="utf-8"), indent=2)
PY

out=$(cd "$fixture_repo" && "$py" "$launcher" repo-list PreToolUse \
  < "$envelopes/claude/pretooluse-bash-safe.json" 2>/dev/null)
rc=$?
if [ "$rc" = 0 ] && printf '%s' "$out" | jq -e \
    '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null; then
  pass "launcher runs a declared repository handler and carries its decision"
else
  fail "launcher repository handler (rc=$rc out=$out)"
fi

out=$(cd "$fixture_repo" && "$py" "$launcher" repo-list PreToolUse \
  < "$envelopes/claude/pretooluse-grep.json" 2>&1)
rc=$?
if [ "$rc" = 0 ] && printf '%s' "$out" | grep -q "escapes the repository root"; then
  pass "launcher refuses a handler path outside the repository root"
else
  fail "launcher escape refusal (rc=$rc out=$out)"
fi

out=$(cd "$fixture_repo" && "$py" "$launcher" repo-list Stop \
  < "$envelopes/claude/stop.json" 2>&1)
rc=$?
if [ "$rc" = 2 ] && printf '%s' "$out" | grep -q "fixture stop finding"; then
  pass "launcher carries a repository Stop handler's blocking exit code"
else
  fail "launcher stop exit code (rc=$rc out=$out)"
fi

out=$(cd "$fixture_repo" && "$py" "$launcher" plugin afk-no-such-handler.sh 2>&1)
rc=$?
if [ "$rc" = 0 ] && [ -z "$out" ]; then
  pass "launcher stays silent on an absent plugin handler"
else
  fail "launcher absent handler (rc=$rc out=$out)"
fi

bare_repo=$(mktemp -d)
git -C "$bare_repo" init -q
out=$(cd "$bare_repo" && "$py" "$launcher" repo-list Stop < "$envelopes/claude/stop.json" 2>&1)
rc=$?
if [ "$rc" = 0 ] && [ -z "$out" ]; then
  pass "launcher exits 0 where the repository declares no hooks"
else
  fail "launcher no-manifest (rc=$rc out=$out)"
fi

# PATH without a POSIX shell is the machine the probes ran on: the system
# directory's WSL stub is the only thing named bash.
py_abs=$(command -v "$py")
out=$(cd "$fixture_repo" && env PATH="${SYSTEMROOT:-C:\\Windows}/System32" \
  "$py_abs" "$launcher" repo-list PreToolUse \
  < "$envelopes/claude/pretooluse-bash-safe.json" 2>/dev/null)
rc=$?
if [ "$rc" = 0 ] && printf '%s' "$out" | jq -e \
    '.hookSpecificOutput.permissionDecision == "deny"' >/dev/null; then
  pass "launcher finds a shell when PATH carries only the WSL stub"
else
  fail "launcher shell lookup (rc=$rc out=$out)"
fi

rm -rf "$fixture_repo" "$bare_repo"

# ---- native twins: same semantics, only the root variable differs.
echo "== native twins =="
twin() {
  local label=$1 claude_file=$2 codex_file=$3
  if "$py" - "$workflow/$claude_file" "$workflow/$codex_file" <<'PY'
import json, sys
claude = json.load(open(sys.argv[1], encoding="utf-8"))
codex = json.load(open(sys.argv[2], encoding="utf-8"))
left = json.dumps(claude, sort_keys=True).replace("${CLAUDE_PLUGIN_ROOT}", "<ROOT>")
right = json.dumps(codex, sort_keys=True).replace("${PLUGIN_ROOT}", "<ROOT>")
sys.exit(0 if left == right else 1)
PY
  then
    pass "$label twins are equal modulo the root variable"
  else
    fail "$label twin drift ($claude_file vs $codex_file)"
  fi
}
twin hooks hooks/hooks.json hooks/hooks.codex.json
twin mcp .mcp.json .mcp.codex.json

# A plugin root containing spaces is the common Windows install path.
spaced=$(mktemp -d)/"afk toolkit root"
mkdir -p "$spaced"
cp -r "$workflow/hooks" "$spaced/hooks"
cp "$workflow/.mcp.json" "$spaced/.mcp.json"
mkdir -p "$spaced/mcp-servers/jira"
printf 'print("fixture server")\n' > "$spaced/mcp-servers/jira/server.py"
out=$("$py" -c "$("$py" -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8'))['mcpServers']['jira']['args'][1])" "$spaced/.mcp.json")" "$spaced" 2>&1)
rc=$?
if [ "$rc" = 0 ] && printf '%s' "$out" | grep -q "fixture server"; then
  pass "MCP launcher resolves a plugin root containing spaces"
else
  fail "MCP launcher spaced root (rc=$rc out=$out)"
fi
out=$(cd "$spaced" && "$py" hooks/run-hook.py plugin afk-no-such-handler.sh 2>&1)
rc=$?
if [ "$rc" = 0 ] && [ -z "$out" ]; then
  pass "hook launcher runs from a plugin root containing spaces"
else
  fail "hook launcher spaced root (rc=$rc out=$out)"
fi
rm -rf "$(dirname "$spaced")"

echo
if [ "$fails" -gt 0 ]; then
  echo "hook-smoke: $fails failure(s)" >&2
  exit 1
fi
echo "hook-smoke: all green"

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
guard="$workflow/hooks/protected-branch-guard.py"

command -v jq >/dev/null 2>&1 || { echo "FAIL: jq not on PATH; these smoke tests need it to read hook answers" >&2; exit 1; }

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

actual=$(CLAUDE_CONFIG_DIR=/claude-home CODEX_HOME=/codex-home CLAUDECODE=1 \
  bash -c '. "$1"; afk_user_instruction_file' _ "$shim")
if [ "$actual" = "/claude-home/CLAUDE.md" ]; then
  pass "afk_user_instruction_file targets Claude's own file under a Claude session"
else
  fail "afk_user_instruction_file (claude session, actual=$actual)"
fi

actual=$(CLAUDE_CONFIG_DIR=/claude-home CODEX_HOME=/codex-home PLUGIN_ROOT=1 \
  bash -c '. "$1"; afk_user_instruction_file' _ "$shim")
if [ "$actual" = "/codex-home/AGENTS.md" ]; then
  pass "afk_user_instruction_file targets Codex's own file under a Codex session"
else
  fail "afk_user_instruction_file (codex session, actual=$actual)"
fi

# Fields are NUL-terminated (see hooks/lib/provider.sh's doc comment): a
# printable delimiter — including the ASCII unit separator this repo used
# before — can legally occur inside a filesystem path and would silently
# shift a field boundary; only NUL cannot. `$(...)` command substitution also
# strips embedded NULs from a captured string, so every assertion below
# decodes the raw byte stream with the real 4-sequential-read consumer
# pattern rather than grepping a captured string.
read_provider_rows() {
  row_name=(); row_target=(); row_root=(); row_enablement=()
  local n t r e
  while IFS= read -r -d '' n && IFS= read -r -d '' t \
    && IFS= read -r -d '' r && IFS= read -r -d '' e; do
    row_name+=("$n"); row_target+=("$t"); row_root+=("$r"); row_enablement+=("$e")
  done
}

find_row() {
  local want=$1 i
  for i in "${!row_name[@]}"; do
    if [ "${row_name[$i]}" = "$want" ]; then
      printf '%s\n' "$i"
      return 0
    fi
  done
  printf -- '-1\n'
}

apt_claude=$(mktemp -d)
mkdir -p "$apt_claude/plugins"
workflow_win=$(command -v cygpath >/dev/null 2>&1 && cygpath -m "$workflow" || printf '%s' "$workflow")
cat > "$apt_claude/plugins/installed_plugins.json" <<JSON
{"plugins": {"afk@afk-toolkit": [{"installPath": "$workflow_win"}]}}
JSON
read_provider_rows < <(CLAUDE_CONFIG_DIR="$apt_claude" CODEX_HOME=/codex-home-unset \
  bash -c '. "$1"; afk_all_provider_targets' _ "$shim")
claude_idx=$(find_row claude)
codex_idx=$(find_row codex)

if [ "$claude_idx" -ge 0 ] && [ "${row_target[$claude_idx]}" = "$apt_claude/CLAUDE.md" ] \
  && [ -n "${row_root[$claude_idx]}" ]; then
  pass "afk_all_provider_targets resolves the claude target and root through the adapter"
else
  fail "afk_all_provider_targets should emit claude's own verified target/root (idx=$claude_idx target=${row_target[$claude_idx]:-<unset>} root=${row_root[$claude_idx]:-<unset>})"
fi
if [ "$codex_idx" -ge 0 ] && [ -z "${row_root[$codex_idx]}" ] \
  && [[ "${row_enablement[$codex_idx]}" =~ ^(enabled|disabled|absent)$ ]]; then
  pass "afk_all_provider_targets still lists codex with an empty root when it cannot be verified"
else
  fail "afk_all_provider_targets should never omit a target row, only leave root empty (idx=$codex_idx root=${row_root[$codex_idx]:-<unset>} enablement=${row_enablement[$codex_idx]:-<unset>})"
fi
# Enablement is a 4th, independent field — $apt_claude has no settings.json
# at all, so claude's enablement must be "absent" regardless of whether its
# root resolved (checked above).
if [ "$claude_idx" -ge 0 ] && [ "${row_enablement[$claude_idx]}" = "absent" ]; then
  pass "afk_all_provider_targets reports claude's own enablement alongside its root"
else
  fail "afk_all_provider_targets should report claude enablement=absent with no settings.json (enablement=${row_enablement[$claude_idx]:-<unset>})"
fi
# A resolver subprocess's own stdout can carry a CRLF line terminator on
# Windows; a newline-preserving capture scheme that strips only the final
# LF would leave a trailing CR baked into ROOT, pointing H7's render at a
# path that doesn't exist — a regression this repo hit and reverted; plain
# `$(...)` command substitution is what stays correct here. Exercise the
# REAL resolver (no stub) and check the exact trailing byte of both
# fields.
if [ "$claude_idx" -ge 0 ] \
  && [[ "${row_target[$claude_idx]}" != *$'\r' && "${row_target[$claude_idx]}" != *$'\n' \
    && "${row_root[$claude_idx]}" != *$'\r' && "${row_root[$claude_idx]}" != *$'\n' ]]; then
  pass "afk_all_provider_targets' real resolver leaves no trailing CR or LF on TARGET or ROOT"
else
  fail "afk_all_provider_targets should never leave a trailing CR or LF byte on TARGET/ROOT (target_last=$(printf '%s' "${row_target[$claude_idx]:-}" | tail -c1 | od -An -tx1) root_last=$(printf '%s' "${row_root[$claude_idx]:-}" | tail -c1 | od -An -tx1))"
fi
rm -rf "$apt_claude"

# A provider whose plugin is installed (root resolves) but turned off must
# report enablement=disabled — a distinct fact from an unresolved root.
apt_disabled=$(mktemp -d)
mkdir -p "$apt_disabled/plugins"
cat > "$apt_disabled/plugins/installed_plugins.json" <<JSON
{"plugins": {"afk@afk-toolkit": [{"installPath": "$workflow_win"}]}}
JSON
cat > "$apt_disabled/settings.json" <<JSON
{"enabledPlugins": {"afk@afk-toolkit": false}}
JSON
read_provider_rows < <(CLAUDE_CONFIG_DIR="$apt_disabled" CODEX_HOME=/codex-home-unset \
  bash -c '. "$1"; afk_all_provider_targets' _ "$shim")
claude_idx=$(find_row claude)
if [ "$claude_idx" -ge 0 ] && [ -n "${row_root[$claude_idx]}" ] \
  && [ "${row_enablement[$claude_idx]}" = "disabled" ]; then
  pass "afk_all_provider_targets reports enablement=disabled for a resolved-root disabled provider"
else
  fail "afk_all_provider_targets should report claude enablement=disabled alongside a resolved root (root=${row_root[$claude_idx]:-<unset>} enablement=${row_enablement[$claude_idx]:-<unset>})"
fi
rm -rf "$apt_disabled"

# A raw byte that used to be this format's own field delimiter (the ASCII
# unit separator) must now pass straight through TARGET and ROOT untouched
# — proof the NUL-only delimiter has no path byte that can collide with it.
us_byte=$(printf '\x1f')
target_with_us="target-us${us_byte}path/AGENTS.md"
root_with_us="root-us${us_byte}path"

# Extract the fenced shell block that immediately follows a heading line, up
# to the closing fence — the real recipe text the two consumers below run,
# never a restated copy. Extraction returning nothing would make every
# assertion below vacuously pass, so that is checked first.
extract_fence() {
  local file=$1 heading=$2
  awk -v heading="$heading" '
    { sub(/\r$/, "") }
    $0 == heading { in_section = 1 }
    in_section && /```sh/ { in_fence = 1; next }
    in_fence && /```/ { exit }
    in_fence { sub(/^  /, ""); print }
  ' "$file"
}

h7_block=$(extract_fence "$workflow/skills/afk/setup/MANIFEST.md" '### H7 · managed agent behavior **[opt-in]**')
audit_block=$(extract_fence "$workflow/skills/afk/setup/AUDIT.md" '## 7 · Managed behavior')
if [ -n "$h7_block" ]; then
  pass "H7's fenced recipe extracted non-empty content"
else
  fail "H7's fenced recipe extraction returned nothing; the real-loop assertions below would pass vacuously"
fi
if [ -n "$audit_block" ]; then
  pass "AUDIT check 7's fenced recipe extracted non-empty content"
else
  fail "AUDIT check 7's fenced recipe extraction returned nothing; the real-loop assertions below would pass vacuously"
fi

# Four synthetic rows fed to the real loops below, NUL-delimited, generated
# straight onto the pipe (never round-tripped through a bash variable, which
# cannot hold an embedded NUL): 3 empty-root rows, one per enablement value
# (if a consumer's `read` ever let an empty ROOT bleed into ENABLEMENT — the
# whitespace-delimiter field-collapsing bug an earlier scheme had — one of these would parse with a
# non-empty root and trigger a render/install attempt), plus a 4th enabled
# row with a real, non-empty TARGET/ROOT that each embed the retired
# unit-separator byte, proving both that an enabled+resolved row is
# installed at all and that the byte survives intact.
emit_fixture_rows() {
  printf 'codex\0target-empty-x\0\0enabled\0'
  printf 'codex\0target-empty-x\0\0disabled\0'
  printf 'codex\0target-empty-x\0\0absent\0'
  printf 'codex\0%s\0%s\0enabled\0' "$target_with_us" "$root_with_us"
}

# H7's install loop, run for real against the fixture: a stub `python` on
# PATH records every invocation and always exits 0 (so the loop's `|| exit 1`
# guards never cut the run short before the 4th row is reached).
stub_bin=$(mktemp -d)
py_log="$stub_bin/py.log"
cat > "$stub_bin/python" <<'STUB'
#!/usr/bin/env bash
echo "python $*" >> "$PY_LOG"
exit 0
STUB
chmod +x "$stub_bin/python"
h7_script=$(printf '%s\n' "$h7_block" | grep -vF '. "$AFK_PLUGIN_ROOT/hooks/lib/provider.sh"')
(
  PATH="$stub_bin:$PATH"
  PY_LOG="$py_log"
  export PATH PY_LOG
  AFK_PLUGIN_ROOT="$workflow"
  . "$AFK_PLUGIN_ROOT/hooks/lib/provider.sh"
  afk_all_provider_targets() { emit_fixture_rows; }
  afk_provider() { printf 'unknown\n'; }
  eval "$h7_script"
) 2>/dev/null
py_log_line_count=$(grep -c '^python ' "$py_log" 2>/dev/null || printf '0')
if [ "$py_log_line_count" = "2" ]; then
  pass "H7's real install loop calls python exactly twice: only the enabled, resolved-root row triggers render+install"
else
  fail "H7's real install loop should call python exactly twice, once each for render and install (line_count=$py_log_line_count log=$(cat "$py_log" 2>/dev/null))"
fi
rendered_path=$(grep -oE -- '--output [^ ]+' "$py_log" 2>/dev/null | awk '{print $2}')
if grep -qF -- "--plugin-root $root_with_us --output" "$py_log" 2>/dev/null; then
  pass "H7's real install loop passes ROOT to render with the unit-separator byte intact"
else
  fail "H7's real install loop should pass --plugin-root '$root_with_us' unmodified (log=$(cat "$py_log" 2>/dev/null))"
fi
if [ -n "$rendered_path" ] && grep -qF -- "install $rendered_path $target_with_us" "$py_log" 2>/dev/null; then
  pass "H7's real install loop passes TARGET to install with the unit-separator byte intact"
else
  fail "H7's real install loop should pass install target '$target_with_us' unmodified (log=$(cat "$py_log" 2>/dev/null))"
fi
rm -rf "$stub_bin"

# AUDIT.md check 7's argument-building loop, run for real against the same
# 4-row fixture: each of the 3 empty-root rows' ROOT must stay empty and its
# own ENABLEMENT must reach the matching `--target-root` triple, never
# shifted into a neighboring field; the 4th row's TARGET/ROOT — each
# carrying the retired unit-separator byte — must reach the audit intact.
audit_loop=$(printf '%s\n' "$audit_block" | sed -n '/^args=()/,/^done < <(afk_all_provider_targets)/p')
args=()
afk_all_provider_targets() { emit_fixture_rows; }
eval "$audit_loop"
if [ "${#args[@]}" -eq 16 ] \
  && [ "${args[0]}" = "--target-root" ] && [ "${args[1]}" = "target-empty-x" ] \
  && [ "${args[2]}" = "" ] && [ "${args[3]}" = "enabled" ] \
  && [ "${args[4]}" = "--target-root" ] && [ "${args[5]}" = "target-empty-x" ] \
  && [ "${args[6]}" = "" ] && [ "${args[7]}" = "disabled" ] \
  && [ "${args[8]}" = "--target-root" ] && [ "${args[9]}" = "target-empty-x" ] \
  && [ "${args[10]}" = "" ] && [ "${args[11]}" = "absent" ] \
  && [ "${args[12]}" = "--target-root" ] && [ "${args[13]}" = "$target_with_us" ] \
  && [ "${args[14]}" = "$root_with_us" ] && [ "${args[15]}" = "enabled" ]; then
  pass "AUDIT check 7's real loop builds all 4 --target-root triples intact, including the unit-separator row"
else
  fail "AUDIT check 7's real loop should build 4 clean --target-root triples (actual=${args[*]})"
fi
unset -f afk_all_provider_targets

for adapter in "$workflow"/hooks/lib/providers/*.sh; do
  provider=${adapter##*/}
  provider=${provider%.sh}
  provider_envelopes="$envelopes/$provider"
  echo "== provider: $provider =="

  for event in session-start sessionstart-clear pretooluse-bash-safe posttooluse postcompact stop; do
    fixture="$provider_envelopes/$event.json"
    parsed=$(AFK_PROVIDER="$provider" bash -c \
      '. "$1"; afk_hook_input; printf "%s" "$(afk_hook_field hook_event_name)"' \
      _ "$shim" < "$fixture")
    case "$event:$parsed" in
      session-start:SessionStart|sessionstart-clear:SessionStart|\
pretooluse-bash-safe:PreToolUse|posttooluse:PostToolUse|\
postcompact:PostCompact|stop:Stop)
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

  guard_repo=$(mktemp -d)
  git -C "$guard_repo" init -q -b dev
  guard_cwd=$(cd "$guard_repo" && pwd -W 2>/dev/null || pwd)
  AFK_PROVIDER="$provider" python "$guard" < "$provider_envelopes/pretooluse-bash-safe.json" >/dev/null 2>&1
  rc=$?
  if [ "$rc" = 0 ]; then
    pass "protected-branch-guard passes a command outside any repository"
  else
    fail "protected-branch-guard outside git (rc=$rc)"
  fi
  sed -e "s|\"cwd\": *\"[^\"]*\"|\"cwd\": \"$guard_cwd\"|" -e 's|"command": *"[^"]*"|"command": "touch changed"|' "$provider_envelopes/pretooluse-bash-safe.json"     | AFK_PROVIDER="$provider" python "$guard" 2>/dev/null >"$guard_repo.out"
  rc=$?
  if [ "$rc" = 0 ] && grep -q '"permissionDecision": "deny"' "$guard_repo.out"; then
    pass "protected-branch-guard refuses a command in a main checkout"
  else
    fail "protected-branch-guard main checkout (rc=$rc, exit 0 plus the deny JSON expected)"
  fi
  rm -rf "$guard_repo" "$guard_repo.out"
done

# ---- lavish render shape: the global binary's bare `lavish-axi <file>` command
# (LAVISH.md "Pin and invocation") reaches both injection hooks.
echo "== lavish bare render =="
lv_dir=$(mktemp -d)
lv_page="$lv_dir/page.html"
printf '<!doctype html><html><head></head><body><p>PRD</p></body></html>\n' > "$lv_page"
# A native Windows Python cannot open a POSIX temp path; hand it a mixed one.
lv_arg=$(cygpath -m "$lv_page" 2>/dev/null || printf '%s' "$lv_page")
lv_env=$(jq -n --arg cmd "lavish-axi $lv_arg --no-open" --arg cwd "$lv_dir" \
  '{session_id:"s", cwd:$cwd, hook_event_name:"PreToolUse", tool_name:"Bash", tool_input:{command:$cmd}}')
printf '%s' "$lv_env" | AFK_PROVIDER=claude bash "$lavish" >/dev/null 2>&1
printf '%s' "$lv_env" | AFK_PROVIDER=claude bash "$lavish_tips" >/dev/null 2>&1
if grep -q 'afk-lavish-dark' "$lv_page" && grep -q 'afk-tips-dict' "$lv_page"; then
  pass "bare lavish-axi render injects dark mode and the tips runtime"
else
  fail "bare lavish-axi render left the page uninjected"
fi
rm -rf "$lv_dir"

# ---- nested-steering handler: inject nested AGENTS.md below the launch dir on
# a harness that loaded only the launch chain, dedup, reset, and stay silent on
# the harness that reads nested files natively.
echo "== nested steering =="
ns_repo=$(mktemp -d)
git -C "$ns_repo" init -q >/dev/null 2>&1
top=$(git -C "$ns_repo" rev-parse --show-toplevel)
printf 'root steering\n' > "$top/AGENTS.md"
printf '@AGENTS.md\n' > "$top/CLAUDE.md"
mkdir -p "$top/sub/deep" "$top/.claude/rules"
printf 'deep steering NESTED-TOKEN-XYZ\n' > "$top/sub/deep/AGENTS.md"
printf 'hello\n' > "$top/sub/deep/x.txt"
printf 'export const a = 1;\n' > "$top/sub/deep/widget.ts"
printf -- '---\npaths: ["**/*.ts"]\n---\nrule body RULE-TOKEN-QRS\n' > "$top/.claude/rules/scoped.md"
ns_data=$(mktemp -d)

ns_run() {  # provider event file_path -> handler stdout
  local prov=$1 evt=$2 fp=$3
  printf '{"session_id":"ns-sess","cwd":"%s","hook_event_name":"%s","tool_name":"Read","tool_input":{"file_path":"%s"}}' \
    "$top" "$evt" "$fp" \
    | env AFK_PROVIDER="$prov" PLUGIN_DATA="$ns_data" CLAUDE_PLUGIN_DATA="$ns_data" \
      bash "$workflow/hooks/nested-steering.sh"
}

out=$(ns_run codex PostToolUse "$top/sub/deep/x.txt")
if printf '%s' "$out" | jq -e '.hookSpecificOutput.additionalContext | test("NESTED-TOKEN-XYZ")' >/dev/null 2>&1; then
  pass "codex injects a nested AGENTS.md token below the launch dir"
else
  fail "codex nested injection (out=$out)"
fi

out2=$(ns_run codex PostToolUse "$top/sub/deep/x.txt")
if [ -z "$out2" ]; then
  pass "a second touch of the same dir is deduped"
else
  fail "dedup failed (out=$out2)"
fi

printf '{"session_id":"ns-sess","cwd":"%s","hook_event_name":"PostCompact"}' "$top" \
  | env AFK_PROVIDER=codex PLUGIN_DATA="$ns_data" bash "$workflow/hooks/nested-steering.sh" >/dev/null 2>&1
out3=$(ns_run codex PostToolUse "$top/sub/deep/x.txt")
if printf '%s' "$out3" | jq -e '.hookSpecificOutput.additionalContext | test("NESTED-TOKEN-XYZ")' >/dev/null 2>&1; then
  pass "reset on PostCompact re-arms injection"
else
  fail "reset did not re-arm (out=$out3)"
fi

out4=$(ns_run codex PostToolUse "$top/sub/deep/widget.ts")
if printf '%s' "$out4" | jq -e '.additional_context | test("RULE-TOKEN-QRS")' >/dev/null 2>&1; then
  pass "codex injects a matching .claude/rules body"
else
  fail "codex rule injection (out=$out4)"
fi

out5=$(ns_run claude PostToolUse "$top/sub/deep/x.txt")
if [ -z "$out5" ]; then
  pass "claude main session injects nothing (mode never; native AGENTS.md support handles the subtree)"
else
  fail "claude main session should be silent (out=$out5)"
fi

# claude stays never even for a subagent tool call: a Claude subagent lazy-loads
# a nested AGENTS.md natively (providers/CONFORMANCE.md, 2026-09-23), so injecting
# would double it. The handler must emit nothing regardless of agent_id.
out6=$(printf '{"session_id":"ns-sess-a","cwd":"%s","hook_event_name":"PostToolUse","tool_name":"Read","agent_id":"child-7","tool_input":{"file_path":"%s"}}' \
    "$top" "$top/sub/deep/x.txt" \
  | env AFK_PROVIDER=claude PLUGIN_DATA="$ns_data" CLAUDE_PLUGIN_DATA="$ns_data" \
    bash "$workflow/hooks/nested-steering.sh")
if [ -z "$out6" ]; then
  pass "claude subagent tool call injects nothing (mode never; no double-inject over native lazy-load)"
else
  fail "claude subagent should be silent (out=$out6)"
fi

# agent-only is correct machinery for a harness whose subagents do NOT lazy-load,
# though no shipped provider selects it. Exercise it directly against the module
# (synthetic mode): it injects when the envelope carries agent_id and is silent
# without one.
ns_py=python
command -v python >/dev/null 2>&1 || ns_py=python3
out7=$(printf '{"session_id":"ns-sess-b","cwd":"%s","hook_event_name":"PostToolUse","tool_name":"Read","agent_id":"child-9","tool_input":{"file_path":"%s"}}' \
    "$top" "$top/sub/deep/x.txt" \
  | "$ns_py" "$workflow/hooks/lib/nested_steering.py" \
    --provider synthetic --mode agent-only --rules 0 --data-dir "$ns_data")
out8=$(printf '{"session_id":"ns-sess-c","cwd":"%s","hook_event_name":"PostToolUse","tool_name":"Read","tool_input":{"file_path":"%s"}}' \
    "$top" "$top/sub/deep/x.txt" \
  | "$ns_py" "$workflow/hooks/lib/nested_steering.py" \
    --provider synthetic --mode agent-only --rules 0 --data-dir "$ns_data")
if printf '%s' "$out7" | grep -q "NESTED-TOKEN-XYZ" && [ -z "$out8" ]; then
  pass "agent-only machinery injects for a subagent tool call, silent without agent_id"
else
  fail "agent-only machinery (with-agent='$out7' without-agent='$out8')"
fi
rm -rf "$ns_repo" "$ns_data"

# ---- agents-md-config-check.sh: the SessionStart notice for the instructionFiles setting.
echo "== agents-md config notice =="
amc_repo_a=$(mktemp -d)          # tracks an AGENTS.md
git -C "$amc_repo_a" init -q
printf 'root steering\n' > "$amc_repo_a/AGENTS.md"
git -C "$amc_repo_a" add AGENTS.md
git -C "$amc_repo_a" -c user.email=a@b.c -c user.name=x commit -q -m init
amc_repo_b=$(mktemp -d)          # no AGENTS.md
git -C "$amc_repo_b" init -q
printf 'x\n' > "$amc_repo_b/README.md"
git -C "$amc_repo_b" add README.md
git -C "$amc_repo_b" -c user.email=a@b.c -c user.name=x commit -q -m init

amc_wrong=$(mktemp -d)           # settings with the wrong value
printf '{"pluginConfigs":{"agents-md@builtin":{"options":{"instructionFiles":"claude-md"}}}}\n' \
  > "$amc_wrong/settings.json"
amc_right=$(mktemp -d)           # settings with the required value
printf '{"pluginConfigs":{"agents-md@builtin":{"options":{"instructionFiles":"claude-md-and-agents-md"}}}}\n' \
  > "$amc_right/settings.json"
amc_missing=$(mktemp -d)         # no settings.json at all

amc_run() {  # provider repo config_dir -> handler stdout
  ( cd "$2" && env AFK_PROVIDER="$1" CLAUDE_CONFIG_DIR="$3" \
      bash "$workflow/hooks/agents-md-config-check.sh" )
}

a1=$(amc_run claude "$amc_repo_a" "$amc_wrong")
if printf '%s' "$a1" | grep -q 'instructionFiles'; then
  pass "claude + tracked AGENTS.md + wrong value -> warns and names the setting"
else
  fail "claude wrong-value should warn (out=$a1)"
fi

a2=$(amc_run claude "$amc_repo_a" "$amc_right")
if [ -z "$a2" ]; then
  pass "claude + tracked AGENTS.md + right value -> silent"
else
  fail "claude right-value should be silent (out=$a2)"
fi

a3=$(amc_run claude "$amc_repo_b" "$amc_wrong")
if [ -z "$a3" ]; then
  pass "claude + no tracked AGENTS.md -> silent"
else
  fail "no-AGENTS.md should be silent (out=$a3)"
fi

a4=$(amc_run codex "$amc_repo_a" "$amc_wrong")
if [ -z "$a4" ]; then
  pass "codex -> silent (setting is Claude-only)"
else
  fail "codex should be silent (out=$a4)"
fi

a5=$(amc_run claude "$amc_repo_a" "$amc_missing")
if [ -z "$a5" ]; then
  pass "claude + missing settings file -> silent"
else
  fail "missing settings file should be silent (out=$a5)"
fi
rm -rf "$amc_repo_a" "$amc_repo_b" "$amc_wrong" "$amc_right" "$amc_missing"

# ---- behavior-drift.sh: the SessionStart notice for managed behavior.
echo "== managed behavior drift notice =="
bd_claude=$(mktemp -d)
bd_codex=$(mktemp -d)
bd_rendered=$(mktemp)
behavior_py=python
command -v python >/dev/null 2>&1 || behavior_py=python3

bd_run() {
  env CLAUDECODE=1 CLAUDE_CONFIG_DIR="$bd_claude" CODEX_HOME="$bd_codex" \
    bash "$workflow/hooks/behavior-drift.sh"
}

if [ -z "$(bd_run)" ]; then
  pass "no managed behavior opt-in -> drift notice silent"
else
  fail "no managed behavior opt-in should be silent"
fi

"$behavior_py" "$workflow/scripts/behavior_registry.py" render \
  --registry "$workflow/BEHAVIORS.md" --plugin-root "$workflow" \
  --output "$bd_rendered"
"$behavior_py" "$workflow/skills/afk/setup/scripts/install_block.py" \
  install "$bd_rendered" "$bd_claude/CLAUDE.md" >/dev/null
"$behavior_py" "$workflow/skills/afk/setup/scripts/install_block.py" \
  install "$bd_rendered" "$bd_codex/AGENTS.md" >/dev/null
if [ -z "$(bd_run)" ]; then
  pass "current managed behavior -> drift notice silent"
else
  fail "current managed behavior should be silent"
fi

sed -i 's/registry-revision: [0-9]*/registry-revision: 0/' "$bd_claude/CLAUDE.md"
bd_stale=$(bd_run)
if [ "$(printf '%s\n' "$bd_stale" | wc -l)" -eq 1 ] \
   && printf '%s' "$bd_stale" | grep -q '/afk:setup'; then
  pass "stale managed behavior -> one setup instruction"
else
  fail "stale managed behavior notice (out=$bd_stale)"
fi

"$behavior_py" "$workflow/skills/afk/setup/scripts/install_block.py" \
  teardown "$bd_claude/CLAUDE.md" >/dev/null
"$behavior_py" "$workflow/skills/afk/setup/scripts/install_block.py" \
  teardown "$bd_codex/AGENTS.md" >/dev/null
printf '<!-- afk:plain-language:start -->\nlegacy\n<!-- afk:plain-language:end -->\n' \
  > "$bd_claude/CLAUDE.md"
if bd_run | grep -q '/afk:setup'; then
  pass "legacy behavior block -> migration notice"
else
  fail "legacy behavior block should request migration"
fi

# Each provider's own SessionStart hook checks only its own target, never the
# other harness's file — a developer who only opted in on one harness must
# never see a stale notice from the other harness's absent file.
bd2_claude=$(mktemp -d)
bd2_codex=$(mktemp -d)
"$behavior_py" "$workflow/skills/afk/setup/scripts/install_block.py" \
  install "$bd_rendered" "$bd2_claude/CLAUDE.md" >/dev/null
# bd2_codex/AGENTS.md is left absent: never opted in on Codex.
bd2_claude_out=$(env CLAUDECODE=1 CLAUDE_CONFIG_DIR="$bd2_claude" CODEX_HOME="$bd2_codex" \
  bash "$workflow/hooks/behavior-drift.sh")
if [ -z "$bd2_claude_out" ]; then
  pass "claude session stays silent for a codex target never opted into"
else
  fail "claude session should not flag the other harness's absent target (out=$bd2_claude_out)"
fi
bd2_codex_out=$(env CLAUDE_CONFIG_DIR="$bd2_claude" CODEX_HOME="$bd2_codex" PLUGIN_ROOT="$workflow" \
  bash "$workflow/hooks/behavior-drift.sh")
if [ -z "$bd2_codex_out" ]; then
  pass "codex session (PLUGIN_ROOT set) also stays silent: it never opted in either"
else
  fail "codex session should be silent on its own absent target (out=$bd2_codex_out)"
fi
rm -rf "$bd2_claude" "$bd2_codex"
rm -rf "$bd_claude" "$bd_codex" "$bd_rendered"

# A tool/config problem (unreadable registry) must never read as drift.
bd_broken=$(mktemp -d)
mkdir -p "$bd_broken/hooks" "$bd_broken/scripts"
cp "$workflow/hooks/behavior-drift.sh" "$bd_broken/hooks/behavior-drift.sh"
cp -r "$workflow/hooks/lib" "$bd_broken/hooks/lib"
cp "$workflow/scripts/behavior_registry.py" "$bd_broken/scripts/behavior_registry.py"
printf 'not a valid registry\n' > "$bd_broken/BEHAVIORS.md"
bd_broken_claude=$(mktemp -d)
printf '<!-- afk:behaviors:start -->\nx\n<!-- afk:behaviors:end -->\n' \
  > "$bd_broken_claude/CLAUDE.md"
bd_broken_out=$(env CLAUDECODE=1 CLAUDE_CONFIG_DIR="$bd_broken_claude" \
  bash "$bd_broken/hooks/behavior-drift.sh" 2>&1)
if printf '%s' "$bd_broken_out" | grep -qi 'check failed' \
   && ! printf '%s' "$bd_broken_out" | grep -q 'is stale'; then
  pass "broken registry reports a check failure, never a stale-drift instruction"
else
  fail "broken registry should report a distinct tool-error notice (out=$bd_broken_out)"
fi
rm -rf "$bd_broken" "$bd_broken_claude"

# An end-only marker (malformed or partial install) still reaches the audit,
# never a silent skip at the prefilter stage.
bd4_claude=$(mktemp -d)
printf 'preamble\n<!-- afk:behaviors:end -->\n' > "$bd4_claude/CLAUDE.md"
bd4_out=$(env CLAUDECODE=1 CLAUDE_CONFIG_DIR="$bd4_claude" \
  bash "$workflow/hooks/behavior-drift.sh" 2>&1)
if [ -n "$bd4_out" ]; then
  pass "end-only marker still reaches the audit, not a silent skip"
else
  fail "end-only marker should not silently skip the audit"
fi
rm -rf "$bd4_claude"

# Drive the hook through the production launcher (hooks/run-hook.py) — the
# real entry point every hook command goes through — under a genuine Codex
# provider signal (PLUGIN_ROOT, per providers/CONFORMANCE.md row 21). PLUGIN_ROOT
# here is only a detection signal: the hook's own root stays self-path-derived,
# never taken from PLUGIN_ROOT's value.
bd5_codex=$(mktemp -d)
bd5_rendered=$(mktemp)
"$behavior_py" "$workflow/scripts/behavior_registry.py" render \
  --registry "$workflow/BEHAVIORS.md" --plugin-root "$workflow" \
  --output "$bd5_rendered"
"$behavior_py" "$workflow/skills/afk/setup/scripts/install_block.py" \
  install "$bd5_rendered" "$bd5_codex/AGENTS.md" >/dev/null
sed -i 's/registry-revision: [0-9]*/registry-revision: 0/' "$bd5_codex/AGENTS.md"
bd5_out=$(env -u CLAUDECODE -u CLAUDE_PLUGIN_ROOT -u CLAUDE_CONFIG_DIR \
  PLUGIN_ROOT=1 CODEX_HOME="$bd5_codex" \
  "$behavior_py" "$workflow/hooks/run-hook.py" plugin behavior-drift.sh)
if printf '%s' "$bd5_out" | grep -q '/afk:setup'; then
  pass "production launcher drives the codex target through the adapter"
else
  fail "production launcher should surface stale codex drift (out=$bd5_out)"
fi
rm -rf "$bd5_codex" "$bd5_rendered"

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
if [ "$rc" = 0 ] && printf '%s' "$out" | grep -q "fixture stop finding" && printf '%s' "$out" | grep -q '"decision": "block"'; then
  pass "launcher turns a repository Stop handler's non-zero exit into the block object"
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

# The gated tree is the working directory's Git root, not CLAUDE_PROJECT_DIR.
clean_repo=$(mktemp -d)
git -C "$clean_repo" init -q
mkdir -p "$fixture_repo/sub"
out=$(cd "$clean_repo" && CLAUDE_PROJECT_DIR="$fixture_repo" "$py" "$launcher" repo-list Stop \
  < "$envelopes/claude/stop.json" 2>&1)
rc=$?
if [ "$rc" = 0 ] && [ -z "$out" ]; then
  pass "launcher ignores a CLAUDE_PROJECT_DIR that is not the working tree"
else
  fail "launcher project-dir override (rc=$rc out=$out)"
fi
out=$(cd "$fixture_repo" && CLAUDE_PROJECT_DIR="$clean_repo" "$py" "$launcher" repo-list Stop \
  < "$envelopes/claude/stop.json" 2>&1)
rc=$?
if [ "$rc" = 0 ] && printf '%s' "$out" | grep -q '"decision": "block"'   && printf '%s' "$out" | grep -q "fixture stop finding"; then
  pass "launcher gates the working tree despite a clean CLAUDE_PROJECT_DIR"
else
  fail "launcher working-tree gate (rc=$rc out=$out)"
fi
out=$(cd "$fixture_repo/sub" && CLAUDE_PROJECT_DIR="$fixture_repo/sub" "$py" "$launcher" repo-list Stop \
  < "$envelopes/claude/stop.json" 2>&1)
rc=$?
if [ "$rc" = 0 ] && printf '%s' "$out" | grep -q '"decision": "block"'   && printf '%s' "$out" | grep -q "fixture stop finding"; then
  pass "launcher gates the repository when the session starts in a subdirectory"
else
  fail "launcher subdirectory gate (rc=$rc out=$out)"
fi

# PATH without a POSIX shell is the machine the probes ran on: the system
# directory's WSL stub is the only thing named bash. Windows-only premise.
case "$(uname -s)" in
MINGW* | MSYS* | CYGWIN*)
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
  ;;
*) echo "  skip: launcher WSL-stub shell lookup (Windows only)" ;;
esac

rm -rf "$fixture_repo" "$bare_repo" "$clean_repo"

# ---- native twins: same semantics, only the root variable differs.
echo "== native twins =="
twin() {
  local label=$1 claude_file=$2 codex_file=$3
  if "$py" - "$workflow/$claude_file" "$workflow/$codex_file" "$workflow/CAPABILITIES.md" <<'PY'
import json, re, sys
claude = json.load(open(sys.argv[1], encoding="utf-8"))
codex = json.load(open(sys.argv[2], encoding="utf-8"))
declared = re.search(r"(?m)^Provider-specific hook events:\s*(.+)$",
                     open(sys.argv[3], encoding="utf-8").read())
for pair in (declared.group(1).split(",") if declared else []):
    provider, _, event = pair.strip().partition("=")
    (claude if provider == "claude" else codex).get("hooks", {}).pop(event, None)
left = json.dumps(claude, sort_keys=True).replace("${CLAUDE_PLUGIN_ROOT}", "<ROOT>")
right = json.dumps(codex, sort_keys=True).replace("${PLUGIN_ROOT}", "<ROOT>")
# The MCP launcher names its own harness directory once; nothing else differs.
own = re.compile(r'own = \\*"\.(claude|codex)\\*"')
left, right = own.sub("own = <OWN>", left), own.sub("own = <OWN>", right)
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
mkdir -p "$spaced/mcp-servers/tracker"
printf 'print("fixture server")\n' > "$spaced/mcp-servers/tracker/server.py"
out=$("$py" -c "$("$py" -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8'))['mcpServers']['tracker']['args'][1])" "$spaced/.mcp.json")" "$spaced" 2>&1)
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

# The genericity gate's cache key must move when any input it reads moves, and
# stay put when none does. The scope comes from the gate itself, so what these
# measure is what the gate keys on. Both placements are exercised: the plugin as
# the whole repository (no product tree), and the plugin inside one.
cachefix=$(mktemp -d)
(
  cd "$cachefix" || exit 1
  git init -q . && git config user.email f@example.invalid && git config user.name f
  mkdir -p hooks plugin src
  printf 'prose\n' > plugin/README.md
  printf 'Widget  # a deliberate reference\n' > hooks/genericity-allow.txt
  printf 'class Widget {}\n' > src/Widget.java
  git add -A && git commit -qm first
) >/dev/null 2>&1
key_of() (
  cd "$cachefix" || exit 1
  AFK_CTX_READY=0 bash -c '
    . "$1"/hooks/genericity-gate.sh
    . "$1"/hooks/gate-cache.sh
    scope=(); while IFS= read -r pat; do scope+=("$pat"); done \
      < <(genericity_cache_scope "$2")
    gate_cache_key genericity "${scope[@]}"' _ "$workflow" "$1"
)
first=$(key_of "plugin/")
if [ -n "$first" ] && [ "$first" = "$(key_of "plugin/")" ]; then
  pass "two runs on an unchanged tree key the same"
else
  fail "the genericity cache key moved with no edit (scratch file inside the tree?)"
fi
printf 'class Widget { }\n' > "$cachefix/src/Widget.java"
if [ "$first" != "$(key_of "plugin/")" ]; then
  pass "a product-tree edit busts the genericity cache key"
else
  fail "product-tree edit left the genericity cache key unchanged"
fi
before=$(key_of "")
printf '\n' > "$cachefix/hooks/genericity-allow.txt"
if [ -n "$before" ] && [ "$before" != "$(key_of "")" ]; then
  pass "an allow-list edit busts the genericity cache key"
else
  fail "a removed allow line reused the cached verdict"
fi
# Cache and metrics live under the git dir: storing a pass and emitting a line
# (from a subdirectory too) adds nothing to the working tree.
(cd "$cachefix" && git checkout -q -- . && mkdir -p src/deep && cd src/deep && bash -c '
  unset GATE_METRICS_FILE; GATE_METRICS_DISABLE=0; GATE_CACHE_DISABLE=0
  . "$1"/hooks/gate-cache.sh; . "$1"/hooks/gate-metrics.sh
  gate_cache_store probe somekey; gate_metrics_begin; gate_metrics_emit probe pass' _ "$workflow")
if [ -z "$(git -C "$cachefix" status --porcelain -uall)" ] &&
   [ "$(<"$cachefix/.git/afk/gate-cache/probe")" = somekey ] &&
   grep -q '"gate":"probe"' "$cachefix/.git/afk/metrics/gate-latency.jsonl"; then
  pass "gate cache and metrics stay under the git dir"
else
  fail "gate cache or metrics wrote into the working tree ($(git -C "$cachefix" status --porcelain -uall))"
fi
rm -rf "$cachefix"
nogit=$(mktemp -d)
(cd "$nogit" && GIT_CEILING_DIRECTORIES=$(dirname "$nogit") bash -c '
  unset GATE_METRICS_FILE; GATE_METRICS_DISABLE=0; GATE_CACHE_DISABLE=0
  . "$1"/hooks/gate-cache.sh; . "$1"/hooks/gate-metrics.sh
  gate_cache_store probe k; gate_cache_hit probe k && exit 3
  gate_metrics_begin; gate_metrics_emit probe pass' _ "$workflow"); rc=$?
if [ "$rc" = 0 ] && [ -z "$(ls -A "$nogit")" ]; then
  pass "outside a repository the cache and metrics write nothing"
else
  fail "outside a repository: rc=$rc files=$(ls -A "$nogit")"
fi
rm -rf "$nogit"

# A shared pattern that does not compile must block, not match nothing and pass.
badpat=$(mktemp -d)
mkdir -p "$badpat/skills" "$badpat/hooks/lib"
sed 's/^ticket-id\t.*/ticket-id\t[/' "$workflow/hooks/lib/sensitive-patterns.tsv" > "$badpat/hooks/lib/sensitive-patterns.tsv"
err=$(cd "$badpat" && bash -c '
  . "$1"/hooks/genericity-gate.sh
  afk_plugin_dir() { printf ".\n"; }; afk_plugin_scope() { printf "\n"; }
  gate_genericity' _ "$workflow" 2>&1 >/dev/null); rc=$?
if [ "$rc" = 2 ] && printf '%s' "$err" | grep -q 'cannot compile'; then
  pass "a ticket-id pattern of \"[\" blocks the genericity gate"
else
  fail "malformed genericity pattern did not block (rc=$rc err=$err)"
fi
rm -rf "$badpat"

# The current-question jump includes the kit send bar. Authored pages without
# the form keep the current-card fallback.
nav_calls=$(grep -c 'var cur = currentAnswerSurface();' "$lavish_tips")
if grep -Fq "return current.closest('[data-afk-answer-form=\"1\"]') || current;" "$lavish_tips" &&
   [ "$nav_calls" = "2" ]; then
  pass "lavish navigation targets the kit answer form"
else
  fail "lavish navigation lost the kit answer form or current-card fallback"
fi

# A pattern that matches the empty string must block, not loop forever.
emptypat=$(mktemp -d)
mkdir -p "$emptypat/skills" "$emptypat/hooks/lib"
sed 's/^ticket-id\t.*/ticket-id\tx*/' "$workflow/hooks/lib/sensitive-patterns.tsv" > "$emptypat/hooks/lib/sensitive-patterns.tsv"
err=$(cd "$emptypat" && timeout 30 bash -c '
  . "$1"/hooks/genericity-gate.sh
  afk_plugin_dir() { printf ".\n"; }; afk_plugin_scope() { printf "\n"; }
  gate_genericity' _ "$workflow" 2>&1 >/dev/null); rc=$?
if [ "$rc" = 2 ] && printf '%s' "$err" | grep -q 'matches the empty string'; then
  pass "a ticket-id pattern of \"x*\" blocks the genericity gate without hanging"
else
  fail "empty-matching genericity pattern (rc=$rc, 124 = hung; err=$err)"
fi
rm -rf "$emptypat"

# ---- comment gate: a staged tracker reference blocks; COMMENT_GATE_DISABLE lets it through.
cg=$(mktemp -d)
(cd "$cg" && git init -q && git config user.name t && git config user.email t@example.test   && printf 'class A {
  int a; // PAY-142 why
}
' > A.java && git add A.java)
err=$(cd "$cg" && bash -c '
  . "$1"/hooks/gate-metrics.sh; GATE_METRICS_DISABLE=1
  . "$1"/hooks/comment-gate.sh; gate_comment' _ "$workflow" 2>&1 >/dev/null); rc=$?
if [ "$rc" = 2 ] && printf '%s' "$err" | grep -q 'A.java:2'; then
  pass "comment gate blocks a staged tracker reference"
else
  fail "comment gate block (rc=$rc err=$err)"
fi
(cd "$cg" && COMMENT_GATE_DISABLE=1 bash -c '
  . "$1"/hooks/gate-metrics.sh; . "$1"/hooks/comment-gate.sh; gate_comment' _ "$workflow")   && pass "COMMENT_GATE_DISABLE=1 skips the comment gate"   || fail "COMMENT_GATE_DISABLE=1 did not skip"
rm -rf "$cg"

echo
if [ "$fails" -gt 0 ]; then
  echo "hook-smoke: $fails failure(s)" >&2
  exit 1
fi
echo "hook-smoke: all green"

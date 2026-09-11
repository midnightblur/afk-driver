#!/usr/bin/env bash
#
# publish-smoke.sh — seam-test for publish.sh against a stubbed `gh`.
#
# Runs in a disposable git repository with a fake `gh` first on PATH, so no
# network call and no real issue or label ever happens. Asserts, per the
# publish.sh header: dry-run runs no gh; create adds missing labels; a visible
# Fingerprint row match comments instead of creating; the title is redacted
# like the body; no auth, a residual hit, an incomplete body, an invalid
# configuration, and auto-publish off all queue an unapproved run (exit 3); an
# approved residual refuses (exit 4) until --accept-residual; --from-queue and
# --accept-residual need --approved; --list and --from-queue drain the queue; a
# bad argument exits 2. Exit 0 = all green.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUBLISH="$SCRIPT_DIR/../publish.sh"

PASS=0
FAIL=0
ok()  { echo "  ok   - $1"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL - $1"; FAIL=$((FAIL + 1)); }

sandbox=$(mktemp -d)
trap 'rm -rf "$sandbox"' EXIT
repo="$sandbox/repo"; bin="$sandbox/bin"; log="$sandbox/gh.log"
mkdir -p "$repo" "$bin"
git -C "$repo" init -q

cat > "$bin/gh" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$FAKE_GH_LOG"
case "$1 $2" in
  "auth status") exit "${FAKE_GH_AUTH:-0}" ;;
  "issue list") printf '%s\n' "${FAKE_GH_FOUND:-[]}" ;;
  "label list") printf '[{"name":"bug"}]\n' ;;
  "label create") exit 0 ;;
  "issue create") printf 'https://github.com/o/n/issues/7\n' ;;
  "issue comment") exit 0 ;;
  *) exit 9 ;;
esac
SH
chmod +x "$bin/gh"
export PATH="$bin:$PATH" FAKE_GH_LOG="$log"
unset AFK_CONFIG

fp=0123456789ab
body() {  # body <file> <extra summary text> [section to drop]
  local s
  for s in Summary Goal Expected Actual "Steps to reproduce" Evidence Environment "Suspected owner"; do
    [ "$s" = "${3-}" ] && continue
    printf '## %s\n' "$s"
    case "$s" in
      Summary) printf 'A plugin hook crashed. %s\n\n' "$2" ;;
      Environment) printf '| Field | Value |\n|---|---|\n| Fingerprint | `%s` |\n\n' "$fp" ;;
      *) printf 'none captured\n\n' ;;
    esac
  done > "$1"
}
body "$sandbox/clean.md" ""
body "$sandbox/residual.md" "value zx9Qw7Er5Ty3Ui1Op0As8Df6Gh4Jk2LmNb"
body "$sandbox/nogoal.md" "" Goal
token="ghp""_""A1b2C3d4A1b2C3d4A1b2C3d4A1b2C3d4"

pub() { (cd "$repo" && bash "$PUBLISH" "$@"); }
reset() { : > "$log"; rm -rf "$repo/.claude"; unset FAKE_GH_AUTH FAKE_GH_FOUND; }

echo "== dry-run =="
reset
out=$(pub --body "$sandbox/clean.md" --title "t $token" --kind bug --fp $fp --dry-run); rc=$?
[ $rc = 0 ] && [ ! -s "$log" ] && ok "dry-run exits 0 and runs no gh" || bad "dry-run (rc=$rc)"
printf '%s' "$out" | grep -q '^ISSUE: dry-run midnightblur/afk-driver$' \
  && ok "target falls back to the plugin manifest repository" || bad "manifest fallback: $out"
! printf '%s' "$out" | grep -qF "$token" && printf '%s' "$out" | grep -q '^--- title: t <token>$' \
  && ok "dry-run shows the redacted title" || bad "dry-run title: $out"

echo "== create =="
reset
out=$(pub --body "$sandbox/clean.md" --title t --kind bug --fp $fp --repo o/n); rc=$?
[ $rc = 0 ] && [ "$out" = "ISSUE: created https://github.com/o/n/issues/7" ] && ok "creates the issue" || bad "create (rc=$rc out=$out)"
grep -q '^label create agent-filed' "$log" && ! grep -q '^label create bug' "$log" \
  && ok "creates only the missing label" || bad "labels: $(cat "$log")"
grep -q '^issue create .*--label bug --label agent-filed' "$log" && ok "agent run labels bug + agent-filed" || bad "create labels"

echo "== dedup =="
reset
export FAKE_GH_FOUND='[{"number":5,"url":"https://github.com/o/n/issues/5","body":"x\n| Fingerprint | `0123456789ab` |\n"}]'
out=$(pub --body "$sandbox/clean.md" --title t --kind bug --fp $fp --repo o/n); rc=$?
[ $rc = 0 ] && [ "$out" = "ISSUE: commented https://github.com/o/n/issues/5" ] && ok "visible Fingerprint row match comments" || bad "dedup (rc=$rc out=$out)"
! grep -q '^issue create' "$log" && grep -q '^issue comment 5' "$log" && ok "no duplicate issue" || bad "dedup calls"
reset
export FAKE_GH_FOUND='[{"number":5,"url":"https://github.com/o/n/issues/5","body":"x 0123456789ab elsewhere"}]'
out=$(pub --body "$sandbox/clean.md" --title t --kind bug --fp $fp --repo o/n); rc=$?
[ $rc = 0 ] && grep -q '^issue create' "$log" && ok "a bare hash without the row is no match" || bad "dedup false match (out=$out)"

echo "== queue =="
reset
export FAKE_GH_AUTH=1
out=$(pub --body "$sandbox/clean.md" --title "hook crash $token" --kind bug --fp $fp --repo o/n); rc=$?
q="$repo/.claude/afk-issues/$fp.md"
[ $rc = 3 ] && [ -f "$q" ] && printf '%s' "$out" | grep -q 'reason=no-gh-auth' && ok "no auth queues" || bad "no-auth queue (rc=$rc)"
[ "$(cat "$repo/.claude/afk-issues/.gitignore")" = "*" ] && ok "queue dir ignores itself" || bad "queue .gitignore"
grep -q '^title: hook crash <token>$' "$q" && ! grep -qF "$token" "$q" && ok "queue stores the redacted title" || bad "queued title: $(head -3 "$q")"
grep -q '^<!-- afk-issue-fp:0123456789ab -->$' "$q" && ok "draft carries meta + marker" || bad "draft shape"
unset FAKE_GH_AUTH
list=$(pub --list)
printf '%s' "$list" | grep -q "hook crash" && ok "--list names the draft" || bad "--list: $list"
pub --from-queue "$q" >/dev/null 2>&1; rc=$?
[ $rc = 2 ] && [ -f "$q" ] && ok "--from-queue without --approved exits 2" || bad "from-queue unapproved (rc=$rc)"
out=$(pub --from-queue "$q" --approved); rc=$?
[ $rc = 0 ] && [ ! -f "$q" ] && grep -q '^issue create .*--label bug --label agent-filed$' "$log" \
  && ok "--from-queue --approved publishes and deletes" || bad "from-queue (rc=$rc out=$out)"

echo "== incomplete body =="
reset
out=$(pub --body "$sandbox/nogoal.md" --title t --kind bug --fp $fp --repo o/n --approved); rc=$?
[ $rc = 3 ] && printf '%s' "$out" | grep -q 'reason=incomplete:Goal' && [ ! -s "$log" ] \
  && ok "a body missing a template section queues, even approved" || bad "incomplete (rc=$rc out=$out)"
reset
out=$(pub --body "$sandbox/clean.md" --title t --kind bug --fp 0123456789ac --repo o/n); rc=$?
[ $rc = 3 ] && printf '%s' "$out" | grep -q 'reason=incomplete:Fingerprint row' \
  && ok "a body without the Fingerprint row for --fp queues" || bad "fp row (rc=$rc out=$out)"

echo "== residual =="
reset
out=$(pub --body "$sandbox/residual.md" --title t --kind bug --fp $fp --repo o/n 2>/dev/null); rc=$?
[ $rc = 3 ] && printf '%s' "$out" | grep -q 'reason=residual' && [ ! -s "$log" ] && ok "unapproved run queues on residual" || bad "agent residual (rc=$rc)"
reset
pub --body "$sandbox/residual.md" --title t --kind bug --fp $fp --repo o/n --approved >/dev/null 2>&1; rc=$?
[ $rc = 4 ] && [ ! -s "$log" ] && ok "approved run refuses residual" || bad "human residual (rc=$rc)"
pub --body "$sandbox/residual.md" --title t --kind bug --fp $fp --repo o/n --accept-residual >/dev/null 2>&1; rc=$?
[ $rc = 2 ] && ok "--accept-residual without --approved exits 2" || bad "accept unapproved (rc=$rc)"
out=$(pub --body "$sandbox/residual.md" --title t --kind bug --fp $fp --repo o/n --approved --accept-residual 2>/dev/null); rc=$?
[ $rc = 0 ] && ok "accepted residual publishes" || bad "accept-residual (rc=$rc)"

echo "== config =="
reset
printf 'schema: 1\nreport-issue:\n  auto-publish: false\n' > "$sandbox/cfg.yaml"
out=$(AFK_CONFIG="$sandbox/cfg.yaml" pub --body "$sandbox/clean.md" --title t --kind bug --fp $fp --repo o/n); rc=$?
[ $rc = 3 ] && printf '%s' "$out" | grep -q 'reason=auto-publish-off' && ok "auto-publish off queues an unapproved run" || bad "auto-publish off (rc=$rc)"
reset
out=$(AFK_CONFIG="$sandbox/cfg.yaml" pub --body "$sandbox/clean.md" --title t --kind bug --fp $fp --repo o/n --approved); rc=$?
[ $rc = 0 ] && ok "an approved run still publishes" || bad "auto-publish off approved (rc=$rc)"
reset
out=$(AFK_CONFIG="$sandbox/cfg.yaml" pub --body "$sandbox/clean.md" --title t --kind bug --fp $fp --repo o/n --dry-run --approved); rc=$?
[ $rc = 0 ] && printf '%s' "$out" | grep -q '^--- body:' && ! printf '%s' "$out" | grep -q 'agent-filed' \
  && ok "a human preview shows the body with auto-publish off" || bad "human preview (rc=$rc out=$out)"
reset
printf 'schema: 1\nreport-issue: [x]\n' > "$sandbox/broken.yaml"
out=$(AFK_CONFIG="$sandbox/broken.yaml" pub --body "$sandbox/clean.md" --title t --kind bug --fp $fp 2>/dev/null); rc=$?
[ $rc = 3 ] && printf '%s' "$out" | grep -q 'reason=config-invalid' && [ ! -s "$log" ] \
  && ok "a malformed configuration queues an unapproved run" || bad "config-invalid (rc=$rc out=$out)"
grep -q '^repo: midnightblur/afk-driver$' "$repo/.claude/afk-issues/$fp.md" 2>/dev/null \
  && ok "the target falls back to the manifest when the configuration is unreadable" || bad "config-invalid target"

echo "== usage =="
pub --body "$sandbox/clean.md" --title t --kind nope --fp $fp >/dev/null 2>&1; [ $? = 2 ] && ok "bad kind exits 2" || bad "bad kind"
pub --body "$sandbox/clean.md" --title t --kind bug --fp XYZ >/dev/null 2>&1; [ $? = 2 ] && ok "bad fingerprint exits 2" || bad "bad fp"
pub --body "$sandbox/clean.md" --title t --kind bug --fp $fp --mode human >/dev/null 2>&1; [ $? = 2 ] && ok "the retired --mode exits 2" || bad "--mode accepted"

echo "== collect_env =="
mkdir -p "$sandbox/plan"; printf 'one\ntwo\n' > "$sandbox/plan/JOURNAL.md"
env_json=$(bash "$SCRIPT_DIR/../collect_env.sh" --plan-dir "$sandbox/plan" --journal-lines 1); rc=$?
py=python; command -v python >/dev/null 2>&1 || py=python3
printf '%s' "$env_json" | "$py" -c '
import json, sys
d = json.load(sys.stdin)
need = {"plugin_version", "provider", "os", "git", "gh", "python", "tracker", "forge", "notes", "build_gates", "journal_tail"}
sys.exit(0 if need <= set(d) and d["journal_tail"] == "two" else 1)' \
  && [ $rc = 0 ] && ok "environment JSON carries every field and the journal tail" || bad "collect_env (rc=$rc): $env_json"
bash "$SCRIPT_DIR/../collect_env.sh" --bogus >/dev/null 2>&1; [ $? = 2 ] && ok "collect_env bad argument exits 2" || bad "collect_env usage"

echo "publish-smoke: $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]

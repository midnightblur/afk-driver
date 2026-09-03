#!/usr/bin/env bash
# verify-contract.sh — deterministic grep-check of a subtask contract's
# `## Produces` / `## Consumes` bullets, bundled with the /afk-toolkit:execute skill
# (Step 2 consumer preflight + Step 9 producer self-preflight — CITED-MODE.md).
# Bullet grammar owned by skills/afk/to-subtasks/SUBTASK-CONTRACT.md:
#   ## Produces:  - {file-path}#{grep-anchor} — {contract}            [materialized]?
#   ## Consumes:  - {PRODUCER-ID} {file-path}#{grep-anchor} — {desc}  [materialized]?
#
# Usage: verify-contract.sh <contract-file> --direction produces|consumes [--root <worktree-root>]
#
#   <contract-file>   the subtask contract, e.g. plan/0003-slug.md
#   --direction       which section's bullets to verify
#   --root            dir the bullets' file paths resolve against (default: cwd)
#
# Per bullet: {file-path} must exist under root AND {grep-anchor} must match
# (fixed-string grep) inside it. Prints one pass/FAIL line per bullet + a
# summary. `[materialized]` bullets are grep-checked identically and the tag is
# REPORTED so the caller runs the compile check on top (execute/CITED-MODE.md)
# — this script never shells out to maven.
#
# A missing/empty `## Consumes` section is a legitimate leaf state → exit 0,
# nothing to verify. A missing/empty `## Produces` is a broken cited contract
# (the section is mandatory) → exit 2.
#
#   EXIT_OK=0      every bullet passed (or nothing to verify, consumes only)
#   EXIT_MISS=1    >=1 bullet failed — its FAIL line names the bullet + producer id
#   EXIT_USAGE=2   bad usage, unreadable contract, unparseable bullet, or
#                  `## Produces` absent/empty when demanded
set -u

EXIT_OK=0
EXIT_MISS=1
EXIT_USAGE=2

usage() {
  echo "usage: verify-contract.sh <contract-file> --direction produces|consumes [--root <worktree-root>]" >&2
}

CONTRACT=""
DIRECTION=""
ROOT="."

while [ $# -gt 0 ]; do
  case "$1" in
    --direction)
      if [ $# -lt 2 ]; then usage; exit "$EXIT_USAGE"; fi
      DIRECTION="$2"; shift 2 ;;
    --root)
      if [ $# -lt 2 ]; then usage; exit "$EXIT_USAGE"; fi
      ROOT="$2"; shift 2 ;;
    -*)
      usage; exit "$EXIT_USAGE" ;;
    *)
      if [ -z "$CONTRACT" ]; then CONTRACT="$1"; shift; else usage; exit "$EXIT_USAGE"; fi ;;
  esac
done

if [ -z "$CONTRACT" ] || [ -z "$DIRECTION" ]; then usage; exit "$EXIT_USAGE"; fi
case "$DIRECTION" in produces|consumes) ;; *) usage; exit "$EXIT_USAGE" ;; esac
if [ ! -f "$CONTRACT" ]; then echo "verify-contract: contract file not found: $CONTRACT" >&2; exit "$EXIT_USAGE"; fi
if [ ! -d "$ROOT" ]; then echo "verify-contract: root dir not found: $ROOT" >&2; exit "$EXIT_USAGE"; fi

if [ "$DIRECTION" = "produces" ]; then HEADING="## Produces"; else HEADING="## Consumes"; fi

# --- collect the section's bullets ------------------------------------------
section_found=0
in_section=0
bullets=()
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%$'\r'}"
  if [ "$line" = "$HEADING" ] || [[ "$line" == "$HEADING "* ]]; then
    section_found=1; in_section=1; continue
  fi
  if [ "$in_section" = 1 ] && [[ "$line" == "## "* ]]; then
    in_section=0; continue
  fi
  if [ "$in_section" = 1 ] && [[ "$line" == "- "* ]]; then
    bullets+=("$line")
  fi
done < "$CONTRACT"

if [ "$section_found" = 0 ] || [ "${#bullets[@]}" = 0 ]; then
  if [ "$DIRECTION" = "consumes" ]; then
    echo "verify-contract: no ${HEADING} bullets in ${CONTRACT} — nothing to verify"
    exit "$EXIT_OK"
  fi
  echo "verify-contract: no ${HEADING} bullets in ${CONTRACT} — a cited contract must declare ${HEADING} (skills/afk/to-subtasks/SUBTASK-CONTRACT.md)" >&2
  exit "$EXIT_USAGE"
fi

# --- verify each bullet ------------------------------------------------------
n_pass=0
n_fail=0
n_mat=0
first_fail=""

for bullet in "${bullets[@]}"; do
  raw="${bullet#- }"

  # trailing [materialized] tag (sits after the description)
  mat=""
  stripped="${raw%"${raw##*[![:space:]]}"}"          # rtrim
  if [[ "$stripped" == *"[materialized]" ]]; then
    mat=" [materialized]"
    n_mat=$((n_mat + 1))
    stripped="${stripped%\[materialized\]}"
    stripped="${stripped%"${stripped##*[![:space:]]}"}"
  fi
  raw="$stripped"

  # consumes bullets lead with {PRODUCER-ID}
  pid=""
  label=""
  if [ "$DIRECTION" = "consumes" ]; then
    pid="${raw%% *}"
    if [ "$pid" = "$raw" ] || [[ "$pid" == *"#"* ]]; then
      echo "verify-contract: unparseable ${HEADING} bullet (expected '{PRODUCER-ID} {file}#{anchor} — …'): ${bullet}" >&2
      exit "$EXIT_USAGE"
    fi
    raw="${raw#* }"
    label="[${pid}] "
  fi

  # split '{file}#{anchor}' off the ' — {description}' tail (first em-dash)
  spec="${raw%% — *}"
  spec="${spec%"${spec##*[![:space:]]}"}"
  if [[ "$spec" != *"#"* ]]; then
    echo "verify-contract: unparseable ${HEADING} bullet (no '{file}#{anchor}'): ${bullet}" >&2
    exit "$EXIT_USAGE"
  fi
  file="${spec%%#*}"
  anchor="${spec#*#}"
  if [ -z "$file" ] || [ -z "$anchor" ]; then
    echo "verify-contract: unparseable ${HEADING} bullet (empty file or anchor): ${bullet}" >&2
    exit "$EXIT_USAGE"
  fi

  target="${ROOT%/}/${file}"
  if [ ! -f "$target" ]; then
    echo "FAIL - ${label}${file}#${anchor}${mat} — file missing"
    n_fail=$((n_fail + 1))
    [ -z "$first_fail" ] && first_fail="${label}${file}#${anchor}"
    continue
  fi
  if grep -qF -- "$anchor" "$target"; then
    echo "pass - ${label}${file}#${anchor}${mat}"
    n_pass=$((n_pass + 1))
  else
    echo "FAIL - ${label}${file}#${anchor}${mat} — anchor not found in file"
    n_fail=$((n_fail + 1))
    [ -z "$first_fail" ] && first_fail="${label}${file}#${anchor}"
  fi
done

# --- summary -----------------------------------------------------------------
n_total=$((n_pass + n_fail))
echo "verify-contract: ${DIRECTION} — ${n_pass}/${n_total} pass, ${n_fail} fail"
if [ "$n_mat" -gt 0 ]; then
  echo "verify-contract: ${n_mat} [materialized] bullet(s) grep-checked only — caller must run the compile check (execute/CITED-MODE.md)"
fi
if [ "$n_fail" -gt 0 ]; then
  echo "verify-contract: first failing bullet: ${first_fail}" >&2
  exit "$EXIT_MISS"
fi
exit "$EXIT_OK"

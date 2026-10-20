#!/usr/bin/env bash
# The run's one wait job: `inbox-wait.sh <inbox-folder> [<park-until>]`, run in a background shell.
# Exits 0 on a message file (not .* or *.tmp), 3 once park-until passes, 2 on a usage error or lost inbox.
set -u

POLL_SEC=10

usage() {
  echo "inbox-wait: $1" >&2
  echo "usage: inbox-wait.sh <inbox-folder> [<park-until, UTC like 2026-01-31T09:30:00Z>]" >&2
  exit 2
}

# Epoch seconds of a UTC ISO 8601 time to the second; fails on any other form or a
# date that does not exist. Pure shell arithmetic, so no date(1) dialect matters.
park_until_utc() {
  local y m d hh mm ss era yoe doy doe
  local -a mdays=(31 28 31 30 31 30 31 31 30 31 30 31)
  [[ $1 =~ ^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z$ ]] || return 1
  y=$((10#${BASH_REMATCH[1]})) m=$((10#${BASH_REMATCH[2]})) d=$((10#${BASH_REMATCH[3]}))
  hh=$((10#${BASH_REMATCH[4]})) mm=$((10#${BASH_REMATCH[5]})) ss=$((10#${BASH_REMATCH[6]}))
  (( m >= 1 && m <= 12 && hh <= 23 && mm <= 59 && ss <= 59 )) || return 1
  (( y % 4 == 0 && (y % 100 != 0 || y % 400 == 0) )) && mdays[1]=29
  (( d >= 1 && d <= mdays[m - 1] )) || return 1
  (( m <= 2 )) && y=$((y - 1))
  era=$((y / 400)) yoe=$((y - era * 400))
  doy=$(( (153 * (m > 2 ? m - 3 : m + 9) + 2) / 5 + d - 1 ))
  doe=$((yoe * 365 + yoe / 4 - yoe / 100 + doy))
  echo $(( (era * 146097 + doe - 719468) * 86400 + hh * 3600 + mm * 60 + ss ))
}

[ $# -ge 1 ] && [ $# -le 2 ] || usage "expected 1 or 2 arguments, got $#"
inbox=$1
[ -n "$inbox" ] && [ -d "$inbox" ] || usage "inbox folder '$inbox' is not a directory"
until_epoch=''
if [ $# -eq 2 ]; then
  until_epoch=$(park_until_utc "$2") || usage "park-until '$2' is not a UTC time to the second"
fi

# Look before the first sleep, so a file that landed before the job started is not missed.
while :; do
  hit=$(find "$inbox" -mindepth 1 -maxdepth 1 -type f ! -name '.*' ! -name '*.tmp' -print -quit 2>/dev/null)
  if [ -z "$hit" ] && ! { [ -d "$inbox" ] && [ -r "$inbox" ] && [ -x "$inbox" ]; }; then
    echo "inbox-wait: inbox folder '$inbox' is gone or unreadable" >&2
    exit 2
  fi
  if [ -n "$hit" ]; then
    echo "INBOX-WAIT: message: a file is in $inbox"
    exit 0
  fi
  now=$(date +%s)
  nap=$POLL_SEC
  if [ -n "$until_epoch" ]; then
    if [ "$now" -ge "$until_epoch" ]; then
      echo "INBOX-WAIT: park-until: $2 has passed, no file in $inbox"
      exit 3
    fi
    [ $((until_epoch - now)) -lt "$nap" ] && nap=$((until_epoch - now))
  fi
  sleep "$nap"
done

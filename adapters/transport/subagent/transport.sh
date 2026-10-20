#!/usr/bin/env bash
# transport/subagent entry: `transport.sh <verb> '<json>'`; verbs and answers: CONTRACT.md beside this file.
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

_kind() { "${AFK_PYTHON:-afk-python}" "$here/subagent.py" "$@"; }

verb_agent_start()  { _kind agent-start "$@"; }
verb_agent_send()   { _kind agent-send "$@"; }
verb_agent_status() { _kind agent-status "$@"; }
verb_agent_read()   { _kind agent-read "$@"; }
verb_agent_stop()   { _kind agent-stop "$@"; }
verb_agent_list()   { _kind agent-list "$@"; }

case "${1:-}" in
  agent-start|agent-send|agent-status|agent-read|agent-stop|agent-list)
    fn="verb_${1//-/_}"; shift; "$fn" "$@" ;;
  *) _kind "$@" ;;
esac

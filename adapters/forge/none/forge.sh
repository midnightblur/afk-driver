#!/usr/bin/env bash
# forge/none — the repository named no forge.
#
# Every verb answers the same object and exits 3. A skill that reaches a forge
# verb stops and shows this reason; it never probes remotes to guess a forge,
# because guessing wrong pushes a draft change to the wrong service.
set -u

verb=${1:-}
printf '{"unsupported":true,"verb":"%s","reason":"forge: none — set forge: gitlab|github in .afk/config.yaml"}\n' "$verb"
exit 3

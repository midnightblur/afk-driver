"""The current harness's declarations from `hooks/lib/providers/<name>.json`, for Python callers.

`facts()` picks the provider the way `afk_provider` in `provider.sh` does: `AFK_PROVIDER` names it,
else the lowest `priority` whose `detect.any_env` variable is set; no match gives {}.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PROVIDERS = Path(__file__).resolve().parent / "providers"


def facts(environ: dict | None = None) -> dict:
    environ = os.environ if environ is None else environ
    found, chosen = {}, None
    forced = environ.get("AFK_PROVIDER")
    for path in sorted(PROVIDERS.glob("*.json")):
        try:
            declared = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        declared.setdefault("name", path.stem)
        if forced:
            hit = path.stem == forced
        else:
            hit = any(environ.get(name) for name in declared.get("detect", {}).get("any_env", []))
        if hit and (chosen is None or declared.get("priority", 100) < chosen):
            found, chosen = declared, declared.get("priority", 100)
    return found

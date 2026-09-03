#!/usr/bin/env python3
"""Load the configured tracker adapter's `api.py`.

A publishing script needs more than the nine `tracker_*` operations — it builds
rich bodies, uploads figures, and merges a managed block into an existing
description. Those live in the adapter, because their shape IS the tracker's.
This module is how such a script reaches them without naming a kind: it reads
`tracker:` from `.afk/config.yaml` and hands back that adapter's module.

`load(required=...)` fails with the missing names and the configuration key when
the selected tracker does not offer them, rather than raising an AttributeError
deep inside a publish that has already written half a page.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def configured_kind(root: Path | None = None) -> str:
    config = _load_module(PLUGIN_ROOT / "scripts" / "afk-config.py", "afk_config")
    return str(config.get(config.load(root or Path.cwd()), "tracker") or "none")


def load(required: tuple[str, ...] = ()):
    """The configured tracker adapter's api module, checked for `required`."""
    kind = configured_kind()
    path = PLUGIN_ROOT / "adapters" / "tracker" / kind / "api.py"
    if not path.is_file():
        sys.exit(f"ERROR: unknown tracker adapter `{kind}` (set by `tracker:` in "
                 f".afk/config.yaml); no {path}")
    module = _load_module(path, "afk_tracker_api")
    missing = [name for name in required if not hasattr(module, name)]
    if missing:
        sys.exit(f"ERROR: this publisher needs {', '.join(missing)} from the "
                 f"tracker adapter, and `tracker: {kind}` does not provide "
                 f"{'them' if len(missing) > 1 else 'it'}. Set `tracker:` in "
                 f".afk/config.yaml to a tracker that does.")
    return module

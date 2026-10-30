"""Recorded fake of the config reader `afkv2_config.py read`, until the S1 reader merges.

Finds `.afkv2/config.json` in the current folder. Answer fields as the S1 reader states them.
"""

import json
import sys
from pathlib import Path


def main():
    config = Path.cwd() / ".afkv2" / "config.json"
    if not config.is_file():
        print(json.dumps({"ok": False, "error": {"code": "no-config", "reason": f"no {config}"}}))
        return 1
    raw = json.loads(config.read_text("utf-8"))
    print(json.dumps({"ok": True, "repo_root": str(Path.cwd()), "config_file": str(config),
                      "spec_folder": str(Path.cwd() / raw["spec_folder"]), "tracker": raw.get("tracker"),
                      "ownership": raw.get("ownership"), "data_folder": str(Path.cwd() / "data")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

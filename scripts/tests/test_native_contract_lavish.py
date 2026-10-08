"""Check N of the native-contract gate: only `scripts/lavish_show.py` runs `lavish-axi`."""
from __future__ import annotations

import re
import subprocess

import pytest

from test_native_contract_events import BASH, GATE, tree  # noqa: F401  (fixture)

pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")

BLOCK = {
    "skills/afk/zz-probe/BLOCK.md": [
        "Run `lavish-axi poll page.html` next.",
        "```",
        "lavish-axi page.html --no-open",
        "```",
        "Then `npx -y lavish-axi@0.1.63 share x.html`.",
        "Or `LAVISH_AXI_HOST=1 lavish-axi x.html`.",
    ],
    "scripts/zz_block.sh": [
        "#!/bin/sh",
        'lavish-axi "$page" --no-open',
        "out=$(lavish-axi poll x.html)",
        "cd x && /usr/local/bin/lavish-axi end x.html",
    ],
    "scripts/zz_block.py": [
        "import subprocess",
        'subprocess.run(["lavish-axi", "poll", "x.html"])',
        "subprocess.run('lavish-axi stop', shell=True)",
    ],
}
PASS = {
    "skills/afk/zz-probe/PASS.md": [
        "The `lavish-axi` binary serves the page; state lives in `~/.lavish-axi/`.",
        'Run `afk-python "${AFK_PLUGIN_ROOT}/scripts/lavish_show.py" poll <file>`.',
        "Install with `npm i -g lavish-axi@0.1.63`; the pin is `lavish-axi@0.1.63`.",
        "```",
        "lavish-axi --version",
        "```",
    ],
    "scripts/zz_pass.sh": [
        "#!/bin/sh",
        "grep -n lavish-axi LAVISH.md",
        "command -v lavish-axi",
        "# lavish-axi share x.html stays a comment",
        '[ "$(lavish-axi --version)" = x ]',
    ],
    "scripts/zz_pass.py": [
        '"""Renders through ``lavish-axi`` via the wrapper."""',
        'NAME = "lavish-axi-notes"',
    ],
    "scripts/tests/zz_test_probe.py": ['subprocess.run(["lavish-axi", "share", "x.html"])'],
}


def test_direct_runs_block_and_mentions_pass(tree):  # noqa: F811
    for files in (BLOCK, PASS):
        for name, lines in files.items():
            path = tree / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    done = subprocess.run([str(BASH), "-c", GATE], cwd=tree, capture_output=True, text=True, timeout=300)
    found = {(m.group(1), int(m.group(2)))
             for m in re.finditer(r"^(\S+):(\d+): runs lavish-axi directly", done.stderr + done.stdout, re.M)}
    expected = {(name, number) for name, lines in BLOCK.items()
                for number, line in enumerate(lines, 1) if "lavish-axi" in line}
    assert done.returncode != 0
    assert found == expected, done.stderr

"""Check N of the native-contract gate: only `scripts/lavish_show.py` runs `lavish-axi`."""
from __future__ import annotations

import re
import subprocess

import pytest

from test_native_contract_events import BASH, GATE, tree  # noqa: F401  (fixture)

pytestmark = pytest.mark.skipif(BASH is None, reason="no POSIX shell on this machine")

# Every line naming lavish-axi in a BLOCK file must be reported; no PASS line may be.
BLOCK = {
    "skills/afk/zz-probe/BLOCK.md": [
        "Run `lavish-axi poll page.html` next.",
        "```",
        "lavish-axi page.html --no-open",
        "```",
        "Then `npx -y lavish-axi@0.1.63 share x.html`.",
        "Or `LAVISH_AXI_HOST=1 lavish-axi x.html`.",
        "Nested: `bash -c 'lavish-axi share page.html'`.",
        "Prefixed: `env -i PATH=/bin lavish-axi page.html`.",
    ],
    "scripts/zz_block.sh": [
        "#!/bin/sh",
        'lavish-axi "$page" --no-open',
        "out=$(lavish-axi poll x.html)",
        "cd x && /usr/local/bin/lavish-axi end x.html",
        "bash -c 'lavish-axi share page.html'",
        "env -i PATH=/bin lavish-axi page.html",
        'reply="$(lavish-axi poll x.html)"',
        "lavish-axi poll x.html \\",
        "  --agent-reply done",
    ],
    "scripts/zz_block.py": [
        "import os, subprocess",
        'subprocess.run(["lavish-axi", "poll", "x.html"])',
        "subprocess.run('lavish-axi stop', shell=True)",
        'subprocess.run(["bash", "-c", "lavish-axi share x.html"])',
        'subprocess.Popen(["env", "-i", "PATH=/bin", "lavish-axi", "x.html"])',
        'os.execvp("lavish-axi", ["lavish-axi", "end", "x.html"])',
        'os.system("npx -y lavish-axi@0.1.63 share x.html")',
    ],
    "hooks/lib/zz_guardish.py": ['subprocess.run(["lavish-axi", "share", "x.html"])'],
    ".github/workflows/zz-block.yml": [
        "on: push",
        "jobs:",
        "  a:",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - run: lavish-axi share x.html",
        "      - name: block",
        "        run: |",
        "          echo start",
        "          npx lavish-axi poll x.html",
        "      - run: \"bash -c 'lavish-axi x.html'\"",
    ],
}
PASS = {
    "skills/afk/zz-probe/PASS.md": [
        "The `lavish-axi` binary serves the page; state lives in `~/.lavish-axi/`.",
        'Run `afk-python "${AFK_PLUGIN_ROOT}/scripts/lavish_show.py" poll <file>`.',
        "Install with `npm i -g lavish-axi@0.1.63`; the pin is `lavish-axi@0.1.63`.",
        "Search with `rg -n lavish-axi .`; discover it with `shutil.which(\"lavish-axi\")`.",
        "```",
        "lavish-axi --version",
        "```",
    ],
    "scripts/zz_pass.sh": [
        "#!/bin/sh",
        "grep -n lavish-axi LAVISH.md",
        "rg 'lavish-axi share' .",
        "command -v lavish-axi",
        "# lavish-axi share x.html stays a comment",
        "echo ok # lavish-axi share x.html",
        '[ "$(lavish-axi --version)" = x ]',
        "echo 'lavish-axi share x.html'",
        "cat <<'EOF'",
        "lavish-axi share x.html is data here",
        "EOF",
    ],
    "scripts/zz_pass.py": [
        '"""Renders through ``lavish-axi`` via the wrapper."""',
        "import shutil, subprocess",
        'NAME = "lavish-axi-notes"',
        'PROGRAM = "lavish-axi"',
        'found = shutil.which("lavish-axi")',
        'subprocess.run(["lavish-axi", "--version"])',
        'subprocess.run(["rg", "-n", "lavish-axi", "."])',
        'subprocess.run("grep -n lavish-axi LAVISH.md", shell=True)',
        'print("run lavish-axi share x.html yourself")',
    ],
    ".github/workflows/zz-pass.yml": [
        "on: push",
        "jobs:",
        "  a:",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - run: grep -n lavish-axi LAVISH.md",
        "      - name: lavish-axi share x.html is forbidden",
        "        run: |",
        "          lavish-axi --version",
    ],
    "scripts/tests/zz_test_probe.py": ['subprocess.run(["lavish-axi", "share", "x.html"])'],
}


def gate_findings(tree) -> tuple[int, set, str]:  # noqa: F811
    done = subprocess.run([str(BASH), "-c", GATE], cwd=tree, capture_output=True, text=True, timeout=300)
    found = {(m.group(1), int(m.group(2)))
             for m in re.finditer(r"^(\S+):(\d+): runs lavish-axi directly", done.stderr + done.stdout, re.M)}
    return done.returncode, found, done.stderr + done.stdout


def write(tree, files: dict) -> None:  # noqa: F811
    for name, lines in files.items():
        path = tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def test_direct_runs_block_and_mentions_pass(tree):  # noqa: F811
    write(tree, BLOCK)
    write(tree, PASS)
    rc, found, output = gate_findings(tree)
    expected = {(name, number) for name, lines in BLOCK.items()
                for number, line in enumerate(lines, 1) if "lavish-axi" in line}
    assert rc != 0
    assert found == expected, output


def test_no_whole_file_exemption_outside_the_wrapper_and_tests(tree):  # noqa: F811
    added = {}
    # Each added run sits in a function nothing calls: the gate sources one file and imports another.
    for name, line in (("CHANGELOG.md", "- Run `lavish-axi share x.html` to publish."),
                       ("adr/zz-probe.md", "Run `lavish-axi share x.html` to publish."),
                       ("hooks/lib/lavish_direct.py", 'def _never(): __import__("subprocess").run(["lavish-axi", "x.html"])'),
                       ("hooks/native-contract-gate.sh", "_never() { lavish-axi share x.html; }")):
        (tree / name).parent.mkdir(parents=True, exist_ok=True)
        (tree / name).touch()
        path = tree / name
        text = path.read_text(encoding="utf-8")
        path.write_text(text + ("" if text.endswith("\n") else "\n") + line + "\n", encoding="utf-8")
        added[name] = len(path.read_text(encoding="utf-8").splitlines())
    rc, found, output = gate_findings(tree)
    assert rc != 0 and found == set(added.items()), output

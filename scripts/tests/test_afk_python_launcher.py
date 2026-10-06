"""The afk-python launcher must run code exactly as `python` would.

Each case runs the same invocation twice under the current interpreter: once
directly, once through a console-script wrapper around
`afk_runtime.launcher:main` (the shape the private environment installs), and
compares what the code observes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SOURCE = PLUGIN_ROOT / "runtime" / "src"

# What the generated console script does, minus its argv[0] suffix handling.
WRAPPER = "import sys\nfrom afk_runtime.launcher import main\nif __name__ == '__main__':\n    sys.exit(main())\n"

OBSERVE = r"""
import json, os, sys
spec = globals().get("__spec__")
print(json.dumps({
    "argv": sys.argv,
    "path0": sys.path[0],
    "name": __name__,
    "file": globals().get("__file__"),
    "spec": spec.name if spec else None,
    "package": globals().get("__package__"),
    "main_is_self": sys.modules["__main__"].__dict__ is globals(),
    "afk_python": os.environ.get("AFK_PYTHON"),
}))
"""


@pytest.fixture()
def place(tmp_path: Path) -> dict:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    wrapper = bin_dir / "afk-python"
    wrapper.write_text(WRAPPER, encoding="utf-8")
    work = tmp_path / "work"
    (work / "pkg").mkdir(parents=True)
    (work / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (work / "pkg" / "observe.py").write_text(OBSERVE, encoding="utf-8")
    (work / "observe.py").write_text(OBSERVE, encoding="utf-8")
    return {"wrapper": wrapper, "work": work}


def env() -> dict:
    out = dict(os.environ, PYTHONPATH=str(SOURCE), PYTHONIOENCODING="utf-8")
    for name in ("AFK_PYTHON", "PYTHONSAFEPATH", "PYTHONSTARTUP"):
        out.pop(name, None)
    return out


def go(place: dict, prefix: list[str], args: tuple, stdin: str | None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(prefix + list(args), cwd=place["work"], env=env(), input=stdin or "",
                          capture_output=True, text=True, encoding="utf-8", timeout=60)


def launch(place: dict, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return go(place, [sys.executable, str(place["wrapper"])], args, stdin)


def both(place: dict, *args: str, stdin: str | None = None) -> tuple:
    return go(place, [sys.executable], args, stdin), launch(place, *args, stdin=stdin)


def observed(done: subprocess.CompletedProcess[str]) -> dict:
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def same_except_afk_python(direct: dict, launched: dict, place: dict) -> None:
    assert launched.pop("afk_python") == os.path.abspath(place["wrapper"])
    assert direct.pop("afk_python") is None
    assert launched == direct


def test_script_sees_argv_path_and_main_namespace_as_python_sets_them(place):
    direct, launched = both(place, "observe.py", "a", "b c")
    d, l = observed(direct), observed(launched)
    assert d["argv"] == ["observe.py", "a", "b c"]
    assert d["path0"] == str(place["work"].resolve())
    same_except_afk_python(d, l, place)


def test_c_code_sees_argv_and_an_empty_path_entry(place):
    direct, launched = both(place, "-c", OBSERVE, "x")
    d, l = observed(direct), observed(launched)
    assert d["argv"] == ["-c", "x"] and d["path0"] == ""
    same_except_afk_python(d, l, place)


def test_indented_c_code_runs_or_fails_as_this_python_decides(place):
    direct, launched = both(place, "-c", "    print('ran')")
    assert launched.returncode == direct.returncode
    assert launched.stdout == direct.stdout


def test_m_module_runs_as_main_with_its_spec_and_the_working_directory_on_path(place):
    direct, launched = both(place, "-m", "pkg.observe", "y")
    d, l = observed(direct), observed(launched)
    assert d["spec"] == "pkg.observe" and d["package"] == "pkg"
    assert d["argv"][1:] == ["y"]
    same_except_afk_python(d, l, place)


def test_stdin_dash_reads_the_code_from_stdin(place):
    direct, launched = both(place, "-", "z", stdin=OBSERVE)
    d, l = observed(direct), observed(launched)
    assert d["argv"] == ["-", "z"] and d["file"] == "<stdin>"
    same_except_afk_python(d, l, place)


def test_version_prints_what_python_prints(place):
    direct, launched = both(place, "--version")
    assert launched.returncode == direct.returncode == 0
    assert launched.stdout == direct.stdout == f"Python {sys.version.split()[0]}\n"


@pytest.mark.parametrize("code, expected", [
    ("import sys; sys.exit(3)", 3),
    ("import sys; sys.exit('stopped')", 1),
    ("import sys; sys.exit(None)", 0),
    ("pass", 0),
])
def test_exit_codes_propagate(place, code, expected):
    direct, launched = both(place, "-c", code)
    assert direct.returncode == launched.returncode == expected
    assert launched.stderr == direct.stderr


def test_an_uncaught_exception_exits_1_with_the_same_traceback(place):
    (place["work"] / "fails.py").write_text("def f():\n    raise ValueError('boom')\nf()\n", encoding="utf-8")
    direct, launched = both(place, "fails.py")
    assert direct.returncode == launched.returncode == 1
    assert "ValueError: boom" in launched.stderr
    assert launched.stderr == direct.stderr


def test_an_excepthook_the_code_installs_reports_the_uncaught_exception(place):
    code = "import sys; sys.excepthook = lambda *a: print('hooked', a[0].__name__); raise KeyError(1)"
    direct, launched = both(place, "-c", code)
    assert direct.returncode == launched.returncode == 1
    assert launched.stdout == direct.stdout == "hooked KeyError\n"


def test_children_inherit_afk_python(place):
    code = ("import os, subprocess, sys; "
            "print(subprocess.run([sys.executable, '-c', 'import os; print(os.environ[\"AFK_PYTHON\"])'],"
            " capture_output=True, text=True).stdout.strip())")
    launched = launch(place, "-c", code)
    assert launched.returncode == 0, launched.stderr
    assert launched.stdout.strip() == os.path.abspath(place["wrapper"])


def test_a_symlinked_script_puts_the_directory_python_would_on_path(place, tmp_path):
    link = tmp_path / "link.py"
    try:
        link.symlink_to(place["work"] / "observe.py")
    except OSError:
        pytest.skip("symlinks need privileges on this platform")
    direct, launched = both(place, str(link))
    d, l = observed(direct), observed(launched)
    # POSIX resolves the link; Windows keeps the link's own directory.
    assert d["path0"] == str((tmp_path if os.name == "nt" else place["work"]).resolve())
    same_except_afk_python(d, l, place)


def test_the_launcher_module_compiles_code_without_its_own_future_flags(place):
    # `from __future__ import annotations` in launcher.py must not leak into run code.
    code = "def f(x: int): pass\nprint(type(f.__annotations__['x']).__name__)"
    direct, launched = both(place, "-c", code)
    assert launched.stdout == direct.stdout == "type\n"


@pytest.mark.parametrize("args", [[], ["-c"], ["-m"], ["-X", "dev", "-c", "pass"]])
def test_unsupported_or_incomplete_invocations_exit_2_with_usage(place, args):
    launched = launch(place, *args)
    assert launched.returncode == 2
    assert "usage: afk-python" in launched.stderr

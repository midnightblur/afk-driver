"""The `afk-python` command: run code in this interpreter, the way `python` would.

    afk-python <script> [args...]
    afk-python -c <code> [args...]
    afk-python -m <module> [args...]
    afk-python - [args...]          (code read from stdin)
    afk-python --version

No child process: the code runs in the interpreter that runs this module, so the
private environment's packages are importable. `sys.argv`, `sys.path[0]` and the
`__main__` namespace match what CPython 3.14 sets for the same form. An uncaught
exception prints its traceback and exits 1; `SystemExit` exits as it says.
`AFK_PYTHON` is set to this command's own path, for children to run Python.
"""
from __future__ import annotations

import builtins
import importlib.machinery
import io
import os
import sys
import types

USAGE = (
    "usage: afk-python <script> [args...] | -c <code> [args...] | "
    "-m <module> [args...] | - [args...] | --version"
)


def launcher_path(argv0: str) -> str:
    """The absolute path of the command that started this process."""
    path = os.path.abspath(argv0)
    # A Windows console-script wrapper strips ".exe" from argv[0].
    if os.name == "nt" and not os.path.isfile(path) and os.path.isfile(path + ".exe"):
        path += ".exe"
    return path


def fresh_main(**attrs: object) -> dict:
    """Replace `__main__` with an empty module, as the interpreter starts with one."""
    module = types.ModuleType("__main__")
    module.__dict__.update(
        __builtins__=builtins, __loader__=importlib.machinery.BuiltinImporter,
        __package__=None, __spec__=None,
    )
    module.__dict__.update(attrs)
    sys.modules["__main__"] = module
    return module.__dict__


def run_source(source: bytes | str, filename: str, namespace: dict) -> None:
    exec(compile(source, filename, "exec", dont_inherit=True), namespace)


def run_script(path: str) -> None:
    full = os.path.abspath(path)
    # CPython resolves a symlinked script only where readlink exists (not Windows).
    set_path0(os.path.dirname(full if os.name == "nt" else os.path.realpath(full)))
    if not os.path.isfile(full):
        import runpy  # a directory or zip archive carrying __main__.py

        runpy.run_path(path, run_name="__main__")
        return
    loader = importlib.machinery.SourceFileLoader("__main__", full)
    namespace = fresh_main(__file__=full, __cached__=None, __loader__=loader)
    with io.open_code(full) as handle:
        source = handle.read()
    run_source(source, full, namespace)


def set_path0(entry: str) -> None:
    # Safe-path mode (-P, PYTHONSAFEPATH) prepends nothing, so slot 0 is not ours.
    if not sys.flags.safe_path:
        sys.path[0] = entry


def report(exc: Exception) -> int:
    """Print an uncaught exception as the interpreter would, minus this module's frames."""
    tb = exc.__traceback__
    while tb is not None and tb.tb_frame.f_code.co_filename == __file__:
        tb = tb.tb_next
    # The default hook prints the exception's own traceback, not the argument.
    sys.excepthook(type(exc), exc.with_traceback(tb), tb)
    return 1


def main(argv: list[str] | None = None) -> int:
    try:
        return dispatch(list(sys.argv if argv is None else argv))
    except Exception as exc:  # SystemExit and KeyboardInterrupt keep their own exit
        return report(exc)


def dispatch(args: list[str]) -> int:
    os.environ["AFK_PYTHON"] = launcher_path(args[0])
    rest = args[1:]
    if not rest:
        print(USAGE, file=sys.stderr)
        return 2
    flag = rest[0]
    if flag in ("--version", "-V"):
        # `platform` costs ~15 ms to import on Windows; sys.version carries the same text.
        print(f"Python {sys.version.split()[0]}")
        return 0
    if flag in ("-c", "-m") and len(rest) < 2:
        print(f"afk-python: argument expected for the {flag} option\n{USAGE}", file=sys.stderr)
        return 2
    if flag == "-c":
        sys.argv = ["-c"] + rest[2:]
        set_path0("")
        code = rest[1]
        if sys.version_info >= (3, 14) and code[:1] in (" ", "	"):
            import textwrap  # 3.14 dedents -c code

            code = textwrap.dedent(code)
        run_source(code, "<string>", fresh_main())
    elif flag == "-m":
        sys.argv = ["-m"] + rest[2:]
        set_path0(os.getcwd())
        import runpy

        fresh_main()
        runpy._run_module_as_main(rest[1], alter_argv=True)
    elif flag == "-":
        sys.argv = rest
        # CPython treats "-" as a script path: Windows makes it absolute, POSIX finds no directory.
        set_path0(os.getcwd() if os.name == "nt" else "")
        run_source(sys.stdin.buffer.read(), "<stdin>", fresh_main(__file__="<stdin>"))
    elif flag.startswith("-"):
        print(f"afk-python: unsupported option {flag}\n{USAGE}", file=sys.stderr)
        return 2
    else:
        sys.argv = rest
        run_script(flag)
    return 0

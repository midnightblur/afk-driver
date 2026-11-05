"""Engine diagrams: the picture or the text of one diagram text (ADR-0006 design).

A diagram text renders through mermaid-cli once per theme, dark and default, into the data folder's
`diagram-cache/`; a picture is named by a hash of the renderer version, the theme and the text, so a text
that did not change costs no renderer call. The page CSS shows the picture of the page's theme
(`shell/diagram.css`). A missing renderer or browser config, a failure or a 60 s timeout shows the text
in a code block with 1 line that says why; a failure is not cached, so the next render tries again. A page build
gives the renderer 90 s in all: a call waits only for what is left, and after a timeout or once the time is spent
each diagram left shows as text, so the build stays inside the 120 s its caller allows.

Each picture holds its own SVG id: `<element id>--dark` and `--light`, or `afkv2-diagram--…` for a diagram
with no id, with a number when the id repeats on the page. An element id that is not safe in HTML and CSS takes
`afkv2-diagram-<hash>` instead (`svg_base`). Every other id inside a picture starts with
that SVG id; an id that nothing in the picture names is dropped, so a note on the picture lands on its
diagram. A page build counts each diagram as rendered, cached or shown as text (`page_run`).
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from contextlib import contextmanager
from html import escape
from pathlib import Path

from afkv2_config import Refusal, data_folder

# The pin of setup (`skills/setup/scripts/tools.py` MERMAID_VERSION); a test keeps the two equal.
RENDERER_VERSION = "12.0.0"
RENDERER = "mmdc"
CONFIG_FILE = "puppeteer-config.json"
CACHE_FOLDER = "diagram-cache"
TIMEOUT_S = 60
# The renderer time of one page build, under the 120 s that present gives one engine call.
PAGE_BUDGET_S = 90
MIN_CALL_S = 1
SETUP = "/afkv2:setup"
# The page theme, and the renderer theme that draws it.
THEMES = (("dark", "dark"), ("light", "default"))
TOKEN = "afkv2svgtoken"
NO_ID_BASE = "afkv2-diagram"
WHY_LIMIT = 200
ID_ATTR = re.compile(r'(\sid=")([^"]+)(")')
SAFE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
HASH_CHARS = 12
clock = time.monotonic

_run: dict | None = None


@contextmanager
def page_run():
    """The run of one page build: `{rendered, cached, as_text}`, and the SVG ids already used. A run inside a run
    is the same run, so a caller around the page build reads the counts."""
    global _run
    if _run is not None:
        yield _run["counts"]
        return
    _run = {"counts": {"rendered": 0, "cached": 0, "as_text": 0}, "ids": set(), "spent": 0.0, "stopped": None}
    try:
        yield _run["counts"]
    finally:
        _run = None


def find_renderer() -> str | None:
    return shutil.which(RENDERER)


def call_renderer(argv: list[str], timeout: float) -> tuple[int, str]:
    """(exit code, error output) of one renderer run; `subprocess.TimeoutExpired` past `timeout`. A run past the time
    is stopped with every process it started, so no browser stays behind."""
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               start_new_session=os.name != "nt")
    try:
        _, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _stop_tree(process)
        raise
    return process.returncode, err.decode("utf-8", "replace")


def _stop_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, timeout=30)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.communicate()


def cache_name(theme: str, text: str) -> str:
    return hashlib.sha256("\0".join([RENDERER_VERSION, theme, text]).encode("utf-8")).hexdigest() + ".svg"


def _data() -> Path | None:
    try:
        return data_folder()
    except Refusal as refusal:
        if refusal.code != "no-data-folder":
            raise
        return None


def _own_ids(svg: str) -> str:
    """Every id the picture keeps starts with TOKEN, and each reference follows its id. An id that nothing in the
    picture names is dropped, and so is a repeat of an id."""
    names, seen = {}, set()

    def rename(match: re.Match) -> str:
        found = match.group(2)
        if found in seen or (found != TOKEN and f"#{found}" not in svg):
            return ""
        seen.add(found)
        if found.startswith(TOKEN):
            return match.group(0)
        names[found] = f"{TOKEN}-{len(names)}-{found}"
        return f"{match.group(1)}{names[found]}{match.group(3)}"

    svg = ID_ATTR.sub(rename, svg)
    for old, new in sorted(names.items(), key=lambda pair: -len(pair[0])):
        svg = re.sub(rf"#{re.escape(old)}(?![\w-])", f"#{new}", svg)
    return svg


class _NoPicture(Exception):
    """The why of a diagram that shows as text."""


def _time_left(run: dict) -> float:
    """The seconds the next renderer call may wait; `_NoPicture` once the page may call the renderer no more."""
    if run["stopped"]:
        raise _NoPicture(run["stopped"])
    left = PAGE_BUDGET_S - run["spent"]
    if left < MIN_CALL_S:
        run["stopped"] = f"the diagrams of this page used their {PAGE_BUDGET_S} s of renderer time"
        raise _NoPicture(run["stopped"])
    return min(TIMEOUT_S, left)


def _render(text: str, theme: str, renderer: str, config: Path, run: dict) -> str:
    wait = _time_left(run)
    with tempfile.TemporaryDirectory(prefix="afkv2-diagram-") as work:
        source, out = Path(work) / "diagram.mmd", Path(work) / "diagram.svg"
        source.write_text(text, encoding="utf-8")
        argv = [renderer, "-p", str(config), "-i", str(source), "-o", str(out), "-t", theme, "-b", "transparent",
                "-I", TOKEN, "-q"]
        start = clock()
        try:
            code, err = call_renderer(argv, wait)
        except subprocess.TimeoutExpired:
            run["stopped"] = f"the diagram renderer gave no answer in {wait:g} s"
            raise _NoPicture(run["stopped"]) from None
        except OSError as error:
            raise _NoPicture(f"the diagram renderer did not start: {error}") from None
        finally:
            run["spent"] += clock() - start
        svg = out.read_text(encoding="utf-8") if code == 0 and out.is_file() else ""
    if "<svg" not in svg:
        lines = [line.strip() for line in err.splitlines() if line.strip()]
        last = lines[-1][:WHY_LIMIT] if lines else "it wrote no picture"
        raise _NoPicture(f"the diagram renderer failed (exit {code}): {last}")
    return _own_ids(svg[svg.index("<svg"):])


def _picture(text: str, theme: str, cache: Path | None, renderer: str, config: Path, run: dict) -> tuple[str, bool]:
    """(the SVG of one theme with TOKEN as its id, whether the renderer ran)."""
    path = cache / cache_name(theme, text) if cache else None
    if path and path.is_file():
        return path.read_text(encoding="utf-8"), False
    svg = _render(text, theme, renderer, config, run)
    if path:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            scratch = path.with_name(f"{path.name}.{os.getpid()}.tmp")
            scratch.write_text(svg, encoding="utf-8")
            os.replace(scratch, path)
        except OSError:
            pass  # no file: the next render renders again
    return svg, True


def _pictures(text: str, run: dict) -> tuple[list[tuple[str, str]], bool]:
    data = _data()
    renderer = find_renderer()
    if not renderer:
        raise _NoPicture(f"the diagram renderer {RENDERER} is not on the path; run {SETUP}")
    config = data / CONFIG_FILE if data else None
    if not config or not config.is_file():
        raise _NoPicture(f"the diagram renderer has no browser config {CONFIG_FILE} in the data folder; run {SETUP}")
    cache = data / CACHE_FOLDER
    found, ran = [], False
    for page_theme, renderer_theme in THEMES:
        svg, new = _picture(text, renderer_theme, cache, renderer, config, run)
        found.append((page_theme, svg))
        ran = ran or new
    return found, ran


def svg_base(element: str | None) -> str:
    """The SVG id base of a diagram: its element id when that is safe in an HTML attribute and a CSS selector."""
    if not element:
        return NO_ID_BASE
    if SAFE_ID.fullmatch(element):
        return element
    return f"{NO_ID_BASE}-{hashlib.sha256(element.encode('utf-8')).hexdigest()[:HASH_CHARS]}"


def svg_id(base: str, page_theme: str) -> str:
    return f"{base}--{page_theme}"


def _base(element: str | None, run: dict) -> str:
    """The id base of this diagram on the page, with a number when it is already used. Element ids are unique on a
    page and never start with `afkv2-`, so only a diagram with no id takes a number."""
    first = svg_base(element)
    base, n = first, 1
    while base in run["ids"]:
        n += 1
        base = f"{first}-{n}"
    run["ids"].add(base)
    return base


def diagram_picture(text: str, element: str | None = None) -> str:
    """The HTML of one diagram text: a picture per theme, or the text in a code block with 1 line that says why."""
    with page_run():
        run = _run
        try:
            pictures, ran = _pictures(text, run)
        except _NoPicture as why:
            run["counts"]["as_text"] += 1
            return (f'<pre class="afkv2-diagram-text"><code>{escape(text)}</code></pre>'
                    f'<p class="afkv2-diagram-why">The diagram shows as text: {escape(str(why))}.</p>')
        run["counts"]["rendered" if ran else "cached"] += 1
        base = _base(element, run)
        drawn = "".join(f'<div class="afkv2-diagram-theme afkv2-diagram-theme--{page_theme}">'
                        f'{svg.replace(TOKEN, svg_id(base, page_theme))}</div>' for page_theme, svg in pictures)
        return f'<div class="afkv2-diagram-picture">{drawn}</div>'

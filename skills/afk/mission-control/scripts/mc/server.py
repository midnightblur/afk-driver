"""The watch -> render -> serve loop, and the shared `render_once` path used
by both `--once` (retro mode, AC-013) and watch mode (AC-011) — ADR-0001.

Binds 127.0.0.1 only; `http.server`'s default handler answers GET/HEAD and
responds 501 to any other verb, satisfying the GET-only / read-only
requirement (SDD §5 authz table) with no extra code.
"""
from __future__ import annotations

import http.server
import threading
import time
from pathlib import Path

from . import template

_DEBOUNCE_DEFAULT = 2.0
_POLL_INTERVAL = 0.5


def render_once(spec_dir: Path, out_dir: Path, panel_parsers: list, live_reload: bool) -> str:
    panels = [parser(spec_dir) for parser in panel_parsers]
    html_text = template.render_page(panels, live_reload=live_reload)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html_text, encoding="utf-8")
    return html_text


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Serves the rendered `out_dir` plus a tiny GET-only reload-token
    endpoint. No other verb is implemented, so the base class's default
    501 response covers POST/PUT/DELETE/etc. (AC-012).
    """

    def do_GET(self):  # noqa: N802 (stdlib handler naming)
        if self.path == "/__mc_token":
            payload = str(self.server.mc_token[0]).encode("ascii")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def log_message(self, fmt, *args):  # noqa: A003 - stdlib override
        pass  # keep CLI/test output quiet; not a correctness concern


def _snapshot_mtimes(spec_dir: Path, out_dir: Path) -> dict:
    snapshot = {}
    try:
        for path in spec_dir.rglob("*"):
            if path == out_dir or out_dir in path.parents:
                continue  # never watch our own output directory
            try:
                if path.is_file():
                    snapshot[str(path)] = path.stat().st_mtime
            except OSError:
                continue
    except OSError:
        pass
    return snapshot


def watch_and_serve(
    spec_dir: Path,
    out_dir: Path,
    port: int,
    panel_parsers: list,
    debounce: float = _DEBOUNCE_DEFAULT,
    stop_event: "threading.Event | None" = None,
) -> http.server.HTTPServer:
    """Renders once, starts the debounced mtime watcher in a daemon thread,
    and returns a bound (not yet serving) `HTTPServer`. Call `serve_forever()`
    on the result to actually serve.
    """
    render_once(spec_dir, out_dir, panel_parsers, live_reload=True)
    token = [0]

    def _handler_factory(*args, **kwargs):
        return _Handler(*args, directory=str(out_dir), **kwargs)

    httpd = http.server.HTTPServer(("127.0.0.1", port), _handler_factory)
    httpd.mc_token = token

    def _watch_loop():
        last = _snapshot_mtimes(spec_dir, out_dir)
        while not (stop_event and stop_event.is_set()):
            time.sleep(_POLL_INTERVAL)
            try:
                current = _snapshot_mtimes(spec_dir, out_dir)
                if current != last:
                    # Debounce: wait for the burst to settle, then take one
                    # more snapshot so a slow render coalesces instead of
                    # queuing re-renders (SDD §5 retry/timeout table).
                    time.sleep(debounce)
                    current = _snapshot_mtimes(spec_dir, out_dir)
                    render_once(spec_dir, out_dir, panel_parsers, live_reload=True)
                    token[0] += 1
                    last = current
            except Exception:
                continue  # watcher must never crash the serving process

    watcher = threading.Thread(target=_watch_loop, name="mc-watch", daemon=True)
    watcher.start()
    return httpd

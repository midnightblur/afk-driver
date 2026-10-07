"""Open one generated Lavish session URL in the current Wave tab.

The helper never starts Lavish. The agent runs the literal ``lavish-axi``
command first so the registered injection hooks can see it, then passes the
exact generated session URL here.

Exit codes:
    0  Wave opened or reused one Web block
    1  Wave definitely did not open the URL; the normal browser may open it
    2  Wave may have opened the URL; do not open a second view
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence
from urllib.parse import urlsplit


LIST_TIMEOUT_SECONDS = 8
OPEN_TIMEOUT_SECONDS = 12


@dataclass(frozen=True)
class WaveScope:
    wsh: str
    tab_id: str
    block_id: str


@dataclass(frozen=True)
class Outcome:
    status: str
    message: str

    @property
    def exit_code(self) -> int:
        return 0 if self.status in {"opened", "reused"} else 2 if self.status == "opened-unconfirmed" else 1


def _resolve_scope_candidate(
    env: Mapping[str, str],
    platform: str = sys.platform,
    which: Callable[[str], str | None] = shutil.which,
) -> WaveScope | None:
    """Resolve the local Wave scope before testing whether ``wsh`` works."""
    if platform != "win32":
        return None
    if env.get("WAVETERM") != "1" or env.get("WAVETERM_CONN", "") != "":
        return None
    tab_id = env.get("WAVETERM_TABID", "").strip()
    block_id = env.get("WAVETERM_BLOCKID", "").strip()
    if not tab_id or not block_id:
        return None
    wsh = which("wsh")
    if not wsh:
        local = env.get("LOCALAPPDATA", "").strip()
        if local:
            candidate = Path(local) / "waveterm" / "Data" / "bin" / "wsh.exe"
            if candidate.is_file():
                wsh = str(candidate)
    if not wsh:
        return None
    return WaveScope(wsh=wsh, tab_id=tab_id, block_id=block_id)


def validate_lavish_url(value: str) -> str:
    """Return an exact safe loopback URL or raise ``ValueError``."""
    if not value or any(char.isspace() or ord(char) == 127 for char in value):
        raise ValueError("whitespace, control character, or empty URL")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid URL") from exc
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1":
        raise ValueError("not an HTTP IPv4 loopback URL")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise ValueError("credentials or fragment are not allowed")
    if port is None or not (1 <= port <= 65535):
        raise ValueError("an explicit valid port is required")
    if parsed.netloc != f"127.0.0.1:{port}":
        raise ValueError("the authority is not canonical loopback")
    return value


def _run(argv: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        shell=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _blocks(stdout: str) -> list[dict[str, str]]:
    """Read only the fields needed from the documented JSON list."""
    if stdout == "No blocks found\n":
        return []
    try:
        payload = json.loads(stdout)
    except (TypeError, ValueError) as exc:
        raise ValueError("unusable block list") from exc
    if not isinstance(payload, list):
        raise ValueError("unusable block list")
    blocks: list[dict[str, str]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError("unusable block entry")
        block_id = entry.get("blockid")
        meta = entry.get("meta")
        if not isinstance(block_id, str) or not block_id or not isinstance(meta, dict):
            raise ValueError("unusable block entry")
        url = meta.get("url")
        if url is not None and not isinstance(url, str):
            raise ValueError("unusable block URL")
        blocks.append({"blockid": block_id, "url": url or ""})
    return blocks


def _list(scope: WaveScope, run: Callable[..., subprocess.CompletedProcess[str]]) -> list[dict[str, str]]:
    result = run(
        [scope.wsh, "blocks", "list", "--view", "web", "--json", "--tab", scope.tab_id],
        timeout=LIST_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise RuntimeError("list-failed")
    return _blocks(result.stdout)


def working_scope(
    env: Mapping[str, str],
    platform: str = sys.platform,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., subprocess.CompletedProcess[str]] = _run,
) -> WaveScope | None:
    """Return an eligible scope only when ``wsh`` returns usable block JSON."""
    scope = _resolve_scope_candidate(env, platform, which)
    if not scope:
        return None
    try:
        _list(scope, run)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired, OSError):
        return None
    return scope


def open_in_wave(
    url: str,
    scope: WaveScope,
    run: Callable[..., subprocess.CompletedProcess[str]] = _run,
) -> Outcome:
    """Reuse a matching Web block or open one, then confirm one exact URL."""
    try:
        safe_url = validate_lavish_url(url)
    except ValueError:
        return Outcome("definitely-not-opened", "Wave did not open the invalid Lavish URL.")

    try:
        before = _list(scope, run)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired, OSError):
        return Outcome("definitely-not-opened", "Wave block discovery failed. Use the normal browser render.")

    match = next((block for block in before if block["url"] == safe_url), None)
    command = [scope.wsh, "web", "open", safe_url]
    if match:
        command.extend(["--replace", match["blockid"]])

    try:
        opened = run(command, timeout=OPEN_TIMEOUT_SECONDS)
    except (subprocess.TimeoutExpired, OSError):
        return Outcome("opened-unconfirmed", "Wave may have opened the Lavish page. Do not open another view.")
    if opened.returncode != 0:
        return Outcome("opened-unconfirmed", "Wave may have opened the Lavish page. Do not open another view.")

    try:
        after = _list(scope, run)
    except (RuntimeError, ValueError, subprocess.TimeoutExpired, OSError):
        return Outcome("opened-unconfirmed", "Wave may have opened the Lavish page. Do not open another view.")
    if not any(block["url"] == safe_url for block in after):
        return Outcome("opened-unconfirmed", "Wave may have opened the Lavish page. Do not open another view.")
    if match:
        return Outcome("reused", "Wave reused the Lavish Web block.")
    return Outcome("opened", "Wave opened the Lavish Web block.")


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] = os.environ) -> int:
    parser = argparse.ArgumentParser(prog="wave_host.py")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("eligible", help="check whether this is a local Wave block")
    opener = sub.add_parser("open", help="open one generated Lavish session URL")
    opener.add_argument("url")
    args = parser.parse_args(argv)

    if args.command == "eligible":
        scope = working_scope(env)
        if scope:
            print("eligible")
            return 0
        print("ineligible")
        return 1
    scope = _resolve_scope_candidate(env)
    if not scope:
        print("definitely-not-opened: Wave is not eligible. Use the normal browser render.")
        return 1
    outcome = open_in_wave(args.url, scope)
    print(f"{outcome.status}: {outcome.message}")
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

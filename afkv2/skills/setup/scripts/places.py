"""Every path setup reads or writes, resolved once from an environment map."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

PROVIDERS = ("claude", "codex")


@dataclass(frozen=True)
class Places:
    home: Path
    data: Path
    claude_dir: Path
    codex_dir: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Places":
        home = Path(env.get("USERPROFILE") or env.get("HOME") or Path.home())
        local = env.get("LOCALAPPDATA")
        data_root = Path(local) if local else home / ".local" / "share"
        return cls(
            home=home,
            data=data_root / "afkv2",
            claude_dir=Path(env.get("CLAUDE_CONFIG_DIR") or home / ".claude"),
            codex_dir=Path(env.get("CODEX_HOME") or home / ".codex"),
        )

    @property
    def install_record(self) -> Path:
        return self.data / "install.txt"

    def fired_record(self, provider: str) -> Path:
        return self.data / f"hook-fired-{provider}.txt"

    @property
    def backup(self) -> Path:
        return self.data / "backup"

    @property
    def published_tickets(self) -> Path:
        return self.data / "published-tickets.txt"

    @property
    def ownership_skips(self) -> Path:
        return self.data / "ownership-skipped.txt"

    def instruction_file(self, provider: str) -> Path:
        if provider == "claude":
            return self.claude_dir / "CLAUDE.md"
        return self.codex_dir / "AGENTS.md"

    @property
    def claude_user_settings(self) -> Path:
        return self.claude_dir / "settings.json"

    @property
    def claude_user_config(self) -> Path:
        return self.home / ".claude.json"

    @property
    def codex_config(self) -> Path:
        return self.codex_dir / "config.toml"


def place_key(path: Path) -> str:
    text = os.path.normcase(str(Path(path).resolve()))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def write_atomic(path: Path, data: bytes) -> None:
    """Replace the file in one step; a symlink stays a link, a file keeps its mode."""
    if path.is_symlink():
        path = Path(os.path.realpath(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".afkv2-tmp")
    _drop_temp(tmp)
    exists = path.exists()
    # Private until the mode is copied: the file can hold a secret. New files take the umask.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(tmp, flags, 0o600 if exists else 0o666), "wb") as out:
        out.write(data)
    try:
        if exists:
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    except OSError:
        _drop_temp(tmp)
        raise


def _drop_temp(tmp: Path) -> None:
    if tmp.exists():
        os.chmod(tmp, stat.S_IWRITE)  # Windows refuses to delete a read-only file
        tmp.unlink()


def backup_once(source: Path, saved: Path) -> bool:
    """Copy `source` to `saved`, or mark it absent. A present backup is kept."""
    absent = saved.with_name(saved.name + ".absent")
    if saved.exists() or absent.exists():
        return False
    saved.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        shutil.copy2(source, saved)
    else:
        absent.write_bytes(b"")
    return True


def has_backup(saved: Path) -> bool:
    return saved.exists() or saved.with_name(saved.name + ".absent").exists()

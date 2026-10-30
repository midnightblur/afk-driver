"""Every path setup reads or writes, resolved once from an environment map."""

from __future__ import annotations

import hashlib
import os
import shutil
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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".afkv2-tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


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


def restore(saved: Path, target: Path) -> str:
    """Put the backup back, delete it, and say what happened."""
    absent = saved.with_name(saved.name + ".absent")
    if absent.exists():
        if target.exists():
            target.unlink()
        absent.unlink()
        return "removed"
    if saved.exists():
        write_atomic(target, saved.read_bytes())
        saved.unlink()
        return "restored"
    return "no-backup"

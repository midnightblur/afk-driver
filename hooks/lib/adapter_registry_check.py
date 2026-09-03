#!/usr/bin/env python3
"""Check E of the registry gate: an adapter kind is coherent across four files.

    python adapter_registry_check.py <plugin-root>

Prints one line per drift and nothing when every adapter agrees. It never
exits non-zero on a finding — the gate decides the verdict from the output, so
a crash and a finding stay distinguishable.

The four places a kind is described (`ADAPTERS.md`, "Adding a kind"):

1. `adapters/<family>/<kind>/adapter.json` — its operations and its runner
2. `adapters/<family>/<kind>/CONTRACT.md` — what each operation answers
3. `CONFIG.md` — the family's enum, and every configuration key the kind reads
4. `skills/afk/setup/MANIFEST.md` — a register row per runtime the kind needs,
   which the kind names itself in adapter.json's `register` array

A kind present in three of them is a kind nobody can select, or one that fails
on a machine the register never told anyone to prepare.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    adapters = root / "adapters"
    if not adapters.is_dir():
        return 0

    config_md = read(root / "CONFIG.md")
    register = read(root / "skills" / "afk" / "setup" / "MANIFEST.md")
    findings: list[str] = []

    for family_dir in sorted(d for d in adapters.iterdir() if d.is_dir()):
        family = family_dir.name
        enum = family_enum(config_md, family)
        for kind_dir in sorted(d for d in family_dir.iterdir() if d.is_dir()):
            kind = kind_dir.name
            name = f"{family}/{kind}"
            manifest_path = kind_dir / "adapter.json"

            if not manifest_path.is_file():
                findings.append(f"{name}: no adapter.json")
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as exc:
                findings.append(f"{name}: adapter.json does not parse ({exc})")
                continue

            # 1. the runner entry has to be on disk, and its type has to match
            # what the entry IS: `instruction` means the agent reads the file,
            # so it must be prose; `cli` means dispatch runs it, so it must not
            # be. A `none` kind stubbed as `instruction` while carrying a real
            # refusal script answers the agent instead of refusing, which is how
            # this check was earned.
            runner = manifest.get("runner") or {}
            entry = runner.get("entry") or ""
            rtype = runner.get("type") or ""
            if not entry:
                findings.append(f"{name}: adapter.json declares no runner.entry")
            elif not (kind_dir / entry).is_file():
                findings.append(f"{name}: runner.entry `{entry}` is not in {name}/")
            if rtype not in ("cli", "instruction"):
                findings.append(
                    f"{name}: runner.type `{rtype}` is neither `cli` nor `instruction`")
            elif entry:
                is_md = entry.lower().endswith(".md")
                if rtype == "instruction" and not is_md:
                    findings.append(
                        f"{name}: runner.type is `instruction`, so the agent reads "
                        f"`{entry}` - but it is a script, not a Markdown procedure")
                elif rtype == "cli" and is_md:
                    findings.append(
                        f"{name}: runner.type is `cli`, so dispatch runs `{entry}` - "
                        f"but it is Markdown, not a script")

            # 2. CONTRACT.md has to name every operation
            contract = read(kind_dir / "CONTRACT.md")
            if not contract:
                findings.append(f"{name}: no CONTRACT.md")
            else:
                missing = [op for op in manifest.get("operations", []) if op not in contract]
                if missing:
                    findings.append(
                        f"{name}: CONTRACT.md never names {', '.join(missing)} "
                        f"(declared in adapter.json)")

            # 3. CONFIG.md has to offer the kind, and document every key it reads
            if enum is None:
                findings.append(f"`{family}` has no enum row in CONFIG.md")
            elif kind not in enum:
                findings.append(
                    f"{name}: CONFIG.md's `{family}` enum does not offer `{kind}` "
                    f"(offers {', '.join(sorted(enum)) or 'nothing'})")
            for key in manifest.get("configKeys", []):
                head = key.split(".")[0]
                if f"`{key}`" not in config_md and f"`{head}`" not in config_md:
                    findings.append(f"{name}: configuration key `{key}` is not in CONFIG.md")

            # 4. every register row the kind names has to exist
            for row in manifest.get("register", []):
                if not re.search(rf"^### {re.escape(row)} · ", register, re.M):
                    findings.append(
                        f"{name}: names register row {row}, which "
                        f"skills/afk/setup/MANIFEST.md does not have")

    for line in findings:
        print(line)
    return 0


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def family_enum(config_md: str, family: str) -> set[str] | None:
    """The kinds CONFIG.md's table offers for a family, or None when it has no row.

    The row is `| `tracker` | `jira` \\| `github-issues` \\| `none` | … |`, and a
    list-valued family reads `list of `maven` \\| `npm``.
    """
    for candidate in (family, family + "s"):
        match = re.search(rf"^\|\s*`{re.escape(candidate)}`\s*\|(.*)$", config_md, re.M)
        if not match:
            continue
        # The cell separator is an UNESCAPED pipe: the enum itself is written
        # `jira` \| `github-issues`, and splitting on every pipe would keep only
        # the first kind.
        cell = re.split(r"(?<![\\])[|]", match.group(1))[0]
        return set(re.findall(r"`([a-z0-9][a-z0-9-]*)`", cell))
    return None


if __name__ == "__main__":
    sys.exit(main(sys.argv))
